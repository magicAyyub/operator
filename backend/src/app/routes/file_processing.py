import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List
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
    idx: int,
    total_files: int,
    upload_dir: Path,
    mapping_path: Path,
    executable_cmd: list
) -> dict:
    """Process a single file and return result dictionary"""
    file_result = {
        'filename': file.filename,
        'success': False,
        'error': None,
        'processing_time': None
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
            # Increased timeout to 10 minutes (600 seconds)
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
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
            file_result['output_file'] = Path(processed_output).name
            return file_result

        except subprocess.TimeoutExpired:
            file_result['error'] = "Processing timed out after 10 minutes"
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
    dataFiles: List[UploadFile] = File(...),
    mappingFile: UploadFile = File(...)
):
    """Endpoint for processing multiple data files with a mapping file"""
    start_time = datetime.now()
    logger.info(f"Process files endpoint called at {start_time}")

    # Validate input files
    if not dataFiles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data files provided"
        )

    # Validate file extensions
    for file in dataFiles:
        if not file.filename.lower().endswith('.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid file format for {file.filename}. Only .txt files allowed.'
            )

    if not mappingFile.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid mapping file format. Only .csv files allowed.'
        )

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

    # Process files
    results = []
    combined_df = None

    # Process files with progress logging
    for idx, file in enumerate(dataFiles, 1):
        logger.info(f"Processing file {idx}/{len(dataFiles)}: {file.filename}")
        result = await process_single_file(
            file=file,
            idx=idx,
            total_files=len(dataFiles),
            upload_dir=upload_dir,
            mapping_path=mapping_path,
            executable_cmd=executable_cmd
        )
        results.append(result)
        logger.info(f"Completed file {idx}/{len(dataFiles)}: {file.filename} - Success: {result['success']}")

        # If successful, add to combined output
        if result['success']:
            try:
                output_path = upload_dir / result['output_file']
                # Use low_memory=False to avoid DtypeWarning for mixed types
                file_df = pd.read_csv(output_path, low_memory=False)
                
                # Log dataframe size for debugging
                logger.info(f"File {file.filename} produced {len(file_df)} rows")
                
                # Combine dataframes
                if combined_df is not None:
                    combined_df = pd.concat([combined_df, file_df], ignore_index=True)
                    logger.info(f"Combined dataframe now has {len(combined_df)} rows")
                else:
                    combined_df = file_df
                    logger.info(f"Started combined dataframe with {len(combined_df)} rows")
                
                # Allow other tasks to run between file processing
                await asyncio.sleep(0)
                
            except Exception as e:
                logger.error(f"Error combining output for {file.filename}: {str(e)}")
                result['success'] = False
                result['error'] = f"Output combination failed: {str(e)}"

    # Save combined output
    combined_output_path = upload_dir / 'input.csv'
    if combined_df is not None and not combined_df.empty:
        try:
            logger.info(f"Saving combined output with {len(combined_df)} rows to {combined_output_path}")
            # Use chunks for large dataframes
            if len(combined_df) > 100000:  # If more than 100k rows
                logger.info("Large dataframe detected, using chunked CSV writing")
                # Write in chunks to avoid memory issues
                chunk_size = 50000
                for i in range(0, len(combined_df), chunk_size):
                    mode = 'w' if i == 0 else 'a'
                    header = i == 0
                    chunk = combined_df.iloc[i:i+chunk_size]
                    chunk.to_csv(combined_output_path, mode=mode, header=header, index=False)
                    logger.info(f"Wrote chunk {i//chunk_size + 1} with {len(chunk)} rows")
                    await asyncio.sleep(0)  # Allow other tasks to run between chunks
            else:
                combined_df.to_csv(combined_output_path, index=False)
                
            logger.info(f"Successfully saved combined output to {combined_output_path}")
        except Exception as e:
            logger.error(f"Failed to save combined output: {str(e)}")
            traceback.print_exc()

    # Clean all files in upload_dir except combined output (input.csv)
    for file in upload_dir.iterdir():
        if file != combined_output_path:
            try:
                file.unlink()
                logger.debug(f"Deleted temporary file: {file}")
            except Exception as e:
                logger.error(f"Failed to delete temporary file {file}: {str(e)}")

    # Prepare response
    success_count = sum(1 for r in results if r['success'])
    processing_time = str(datetime.now() - start_time)

    response_data = {
        'success': success_count > 0,
        'files_processed': success_count,
        'total_files': len(dataFiles),
        'processing_time': processing_time,
        'details': results,
        'combined_output': 'input.csv' if combined_df is not None else None,
        'environment': {
            'system': platform.system(),
            'release': platform.release(),
            'is_wsl': is_wsl(),
            'executable': str(c_executable),
            'command_used': ' '.join(executable_cmd),
        }
    }

    logger.info(f"Processing completed in {processing_time}. Success: {success_count}/{len(dataFiles)}")
    return JSONResponse(content=response_data)

# Ajouter un endpoint pour l'upload direct de CSV (pour la compatibilité avec l'interface Next.js)
@router.post("/csv/upload", response_model=dict)
async def upload_csv_endpoint(
    file: UploadFile = File(...)
):
    """Endpoint pour télécharger directement un fichier CSV"""
    try:
        # Vérifier que c'est un fichier CSV
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier doit être au format CSV"
            )
        
        # Créer le répertoire de données s'il n'existe pas
        data_dir = Path("src/data")
        data_dir.mkdir(exist_ok=True, parents=True)
        
        # Chemin du fichier de destination
        file_path = data_dir / "input.csv"
        
        # Sauvegarder le fichier avec chunking
        if not await save_upload_file_chunked(file, file_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la sauvegarde du fichier"
            )
        
        return {
            "success": True,
            "message": "Fichier CSV importé avec succès"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'upload du CSV: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Une erreur est survenue lors de l'importation du fichier: {str(e)}"
        )
