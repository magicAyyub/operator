import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List, Optional
import subprocess
from pathlib import Path
import traceback
import logging
import pandas as pd
from datetime import datetime
import shutil
import platform
import asyncio
from src.utils.settings import Config
from src.utils.helpers import join_operator_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["file_processing"],
    responses={404: {"description": "Not found"}}
)

# Chemin vers le fichier CSV
CSV_FILE_PATH = "src/data/input.csv"

def is_wsl() -> bool:
    """Check if running in WSL environment"""
    return 'microsoft' in platform.uname().release.lower()

def get_executable_command(executable_path: Path) -> list:
    """Get the appropriate command for the executable based on environment"""
    if is_wsl():
        # If running in WSL but executable is Windows binary
        if '.exe' in executable_path.suffix.lower():
            return ['wsl', str(executable_path)]
        return [str(executable_path)]
    return [str(executable_path)]

async def process_single_file(
    file: UploadFile,
    mapping_path: Path,
    upload_dir: Path,
    executable_cmd: list
) -> dict:
    """Process a single file and return result dictionary"""
    file_result = {
        'filename': file.filename,
        'success': False,
        'error': None,
        'processing_time': None,
        'output_file': None
    }
    start_time = datetime.now()
    
    try:
        # Save input file with chunking for large files
        input_path = upload_dir / Path(file.filename).name
        if not await save_upload_file_chunked(file, input_path):
            file_result['error'] = "Could not save input file"
            return file_result

        # Prepare output path
        output_path = upload_dir / f'output_{Path(file.filename).stem}.csv'
        
        # Execute processing with increased timeout
        cmd = executable_cmd + [str(input_path), str(output_path)]
        logger.info(f"Executing: {' '.join(cmd)}")

        try:
            # Increased timeout to 5 minutes (300 seconds)
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            # Check process results
            if process.returncode != 0:
                error_msg = process.stderr or "Unknown processing error"
                file_result['error'] = clean_error_message(error_msg)
                return file_result

            # Process output with mapping
            processed_output = join_operator_data(str(output_path), str(mapping_path))
            if not processed_output or not Path(processed_output).exists():
                file_result['error'] = "Failed to join operator data"
                return file_result

            file_result['success'] = True
            file_result['output_file'] = processed_output
            return file_result

        except subprocess.TimeoutExpired:
            file_result['error'] = "Processing timed out after 5 minutes"
        except subprocess.CalledProcessError as e:
            file_result['error'] = f"Processing failed: {str(e)}"
        except Exception as e:
            file_result['error'] = f"Unexpected error: {str(e)}"

    except Exception as e:
        logger.error(f"Error processing {file.filename}: {str(e)}")
        file_result['error'] = f"Processing error: {str(e)}"
    finally:
        file_result['processing_time'] = str(datetime.now() - start_time)
        # Clean up temporary files
        if 'input_path' in locals() and input_path.exists():
            input_path.unlink()
        if 'output_path' in locals() and output_path.exists():
            output_path.unlink()
      
    return file_result

def clean_error_message(error_msg: str) -> str:
    """Clean and truncate error messages"""
    error_msg = error_msg.replace('\n', ' ').strip()
    return error_msg[:500]  # Truncate long error messages

async def save_upload_file_chunked(upload_file: UploadFile, destination: Path) -> bool:
    """Save uploaded file to destination using chunked approach for large files"""
    try:
        # Use a larger chunk size for better performance
        chunk_size = 1024 * 1024  # 1MB chunks
        
        with destination.open("wb") as buffer:
            # Read and write in chunks
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                buffer.write(chunk)
                # Allow other tasks to run between chunks
                await asyncio.sleep(0)
              
        return True
    except Exception as e:
        logger.error(f"Error saving file {upload_file.filename}: {str(e)}")
        return False

@router.post("/process_files", response_model=dict)
async def process_files_endpoint(
    dataFiles: UploadFile = File(...),
    mappingFile: UploadFile = File(...),
    appendMode: Optional[str] = Form("false")
):
    """Endpoint for processing a single data file with a mapping file and appending to existing data"""
    start_time = datetime.now()
    logger.info(f"Process files endpoint called at {start_time}")

    # Validate input files
    if not dataFiles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data file provided"
        )

    # Validate file extensions
    if not dataFiles.filename.lower().endswith('.txt'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid file format for {dataFiles.filename}. Only .txt files allowed.'
        )

    if not mappingFile.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid mapping file format. Only .csv files allowed.'
        )

    # Convert appendMode string to boolean
    append_mode = appendMode.lower() == "true"
    logger.info(f"Append mode: {append_mode}")

    # Setup working directory
    upload_dir = Path(Config.UPLOAD_FOLDER)
    upload_dir.mkdir(exist_ok=True, parents=True)
    
    # Verify executable
    c_executable = Path(Config.C_EXECUTABLE_PATH)
    if not c_executable.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing service unavailable"
        )

    # Save mapping file with chunking for large files
    mapping_path = upload_dir / Path(mappingFile.filename).name
    if not await save_upload_file_chunked(mappingFile, mapping_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save mapping file"
        )

    # Get appropriate command for the environment
    executable_cmd = get_executable_command(c_executable)
    logger.info(f"Using command: {executable_cmd}")

    # Process the file
    result = await process_single_file(
        file=dataFiles,
        mapping_path=mapping_path,
        upload_dir=upload_dir,
        executable_cmd=executable_cmd
    )
    
    logger.info(f"File processing result: {result}")

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {result['error']}"
        )

    # Handle the processed output
    try:
        # Path to the combined output file
        combined_output_path = Path(CSV_FILE_PATH)
        data_dir = combined_output_path.parent
        data_dir.mkdir(exist_ok=True, parents=True)
        
        # Path to the processed output file
        processed_output_path = Path(result['output_file'])
        
        # Read the processed data
        processed_df = pd.read_csv(processed_output_path, low_memory=False)
        logger.info(f"Processed file has {len(processed_df)} rows")
        
        if append_mode and combined_output_path.exists():
            # If appending and the file exists, read existing data and append
            logger.info(f"Appending to existing file: {combined_output_path}")
            try:
                existing_df = pd.read_csv(combined_output_path, low_memory=False)
                logger.info(f"Existing file has {len(existing_df)} rows")
                
                # Combine dataframes
                combined_df = pd.concat([existing_df, processed_df], ignore_index=True)
                logger.info(f"Combined dataframe has {len(combined_df)} rows")
            except Exception as e:
                logger.error(f"Error reading existing file: {e}")
                # If there's an error reading the existing file, just use the processed data
                combined_df = processed_df
        else:
            # If not appending or the file doesn't exist, just use the processed data
            combined_df = processed_df
        
        # Save the combined data
        logger.info(f"Saving combined data with {len(combined_df)} rows to {combined_output_path}")
        
        # Use chunks for large dataframes
        if len(combined_df) > 50000:  # If more than 50k rows
            logger.info("Large dataframe detected, using chunked CSV writing")
            # Write in chunks to avoid memory issues
            chunk_size = 10000
            for i in range(0, len(combined_df), chunk_size):
                mode = 'w' if i == 0 else 'a'
                header = i == 0
                chunk = combined_df.iloc[i:i+chunk_size]
                chunk.to_csv(combined_output_path, mode=mode, header=header, index=False)
                logger.info(f"Wrote chunk {i//chunk_size + 1} with {len(chunk)} rows")
                await asyncio.sleep(0)  # Allow other tasks to run between chunks
        else:
            combined_df.to_csv(combined_output_path, index=False)
        
        logger.info(f"Successfully saved combined data to {combined_output_path}")
        
        # Clean up temporary files
        for file_path in upload_dir.iterdir():
            if file_path != combined_output_path and file_path.is_file():
                try:
                    file_path.unlink()
                    logger.debug(f"Deleted temporary file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to delete temporary file {file_path}: {str(e)}")
        
        return {
            "success": True,
            "message": f"File processed and {'added to' if append_mode else 'saved as'} input.csv",
            "rows_processed": len(processed_df),
            "total_rows": len(combined_df)
        }
        
    except Exception as e:
        logger.error(f"Error handling processed output: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error handling processed output: {str(e)}"
        )

@router.get("/csv/check")
def check_file():
    """Vérifie si un fichier de données existe déjà"""
    exists = os.path.exists(CSV_FILE_PATH)
    return {"exists": exists}

@router.delete("/csv/purge")
def purge_data():
    """Supprime le fichier de données existant"""
    try:
        if os.path.exists(CSV_FILE_PATH):
            os.remove(CSV_FILE_PATH)
            return {"success": True, "message": "Données purgées avec succès"}
        else:
            return {"success": True, "message": "Aucun fichier à purger"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur lors de la purge des données: {str(e)}"}
        )
