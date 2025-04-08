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
from src.utils.settings import Config
from src.utils.helpers import join_operator_data

# Set up logging
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

def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def clean_directory(directory: Path, exclude: list = None):
    """Clean up directory except excluded files"""
    exclude = exclude or []
    for item in directory.iterdir():
        if item.name not in exclude:
            if item.is_file():
                item.unlink()
            else:
                shutil.rmtree(item)

async def save_upload_file(upload_file: UploadFile, destination: Path) -> bool:
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
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
        logger.error("No data files provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data files provided"
        )

    # Validate file extensions
    for file in dataFiles:
        if not validate_file_extension(file.filename, {'txt'}):
            logger.error(f"Invalid file format for {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid file format for {file.filename}. Only .txt files are allowed.'
            )

    if not validate_file_extension(mappingFile.filename, {'csv'}):
        logger.error(f"Invalid mapping file format: {mappingFile.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid mapping file format. Only .csv files are allowed.'
        )

    # Verify and prepare working directory
    upload_dir = Path(Config.UPLOAD_FOLDER)
    upload_dir.mkdir(exist_ok=True, parents=True)
    clean_directory(upload_dir, exclude=['input.csv'])  # Keep combined output if exists

    # Verify C executable
    c_executable = Path(Config.C_EXECUTABLE_PATH)
    if not c_executable.exists():
        logger.error(f"C executable not found at {c_executable}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing service unavailable"
        )

    if not os.access(c_executable, os.X_OK):
        logger.error(f"C executable not executable at {c_executable}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing service not executable"
        )

    # Save mapping file
    mapping_path = upload_dir / Path(mappingFile.filename).name
    if not await save_upload_file(mappingFile, mapping_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save mapping file"
        )
    logger.info(f"Mapping file saved to {mapping_path}")

    # Process files
    results = []
    combined_df = None
    combined_output_path = upload_dir / 'input.csv'

    for idx, file in enumerate(dataFiles, 1):
        file_start = datetime.now()
        file_result = {
            'filename': file.filename,
            'success': False,
            'error': None,
            'processing_time': None
        }

        try:
            logger.info(f"Processing file {idx}/{len(dataFiles)}: {file.filename}")
            
            # Save input file
            input_path = upload_dir / Path(file.filename).name
            if not await save_upload_file(file, input_path):
                file_result['error'] = "Could not save input file"
                results.append(file_result)
                continue

            # Prepare output path
            output_path = upload_dir / f'output_{Path(file.filename).stem}.csv'

            # Execute processing
            cmd = [str(c_executable), str(input_path), str(output_path)]
            logger.info(f"Executing: {' '.join(cmd)}")

            try:
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                # Log process output
                if process.stdout:
                    logger.debug(f"STDOUT: {process.stdout[:200]}...")
                if process.stderr:
                    logger.warning(f"STDERR: {process.stderr[:200]}...")

                if process.returncode != 0:
                    error_msg = process.stderr or "Unknown error during processing"
                    file_result['error'] = error_msg[:200]
                    results.append(file_result)
                    continue

                # Process output with mapping
                processed_output = join_operator_data(output_path, mapping_path)
                if not processed_output or not Path(processed_output).exists():
                    file_result['error'] = "Failed to join operator data"
                    results.append(file_result)
                    continue

                # Add to combined output
                try:
                    file_df = pd.read_csv(processed_output)
                    if combined_df is None:
                        combined_df = file_df
                    else:
                        combined_df = pd.concat([combined_df, file_df], ignore_index=True)
                    
                    file_result['success'] = True
                    file_result['output_file'] = Path(processed_output).name
                except Exception as e:
                    file_result['error'] = f"Data processing error: {str(e)}"

            except subprocess.TimeoutExpired:
                file_result['error'] = "Processing timed out"
            except subprocess.CalledProcessError as e:
                file_result['error'] = f"Processing failed: {str(e)}"
            except Exception as e:
                file_result['error'] = f"Unexpected error: {str(e)}"

        except Exception as e:
            logger.error(f"Error processing {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            file_result['error'] = f"Processing error: {str(e)}"
        finally:
            # Clean up temporary files
            if input_path.exists():
                input_path.unlink()
            if output_path.exists():
                output_path.unlink()
            
            file_result['processing_time'] = str(datetime.now() - file_start)
            results.append(file_result)

    # Save combined output if successful
    if combined_df is not None and not combined_df.empty:
        try:
            combined_df.to_csv(combined_output_path, index=False)
            Config.PROCESSED_CSV = 'input.csv'
            logger.info(f"Combined output saved to {combined_output_path}")
        except Exception as e:
            logger.error(f"Failed to save combined output: {str(e)}")

    # Clean up mapping file
    if mapping_path.exists():
        mapping_path.unlink()

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
        'system_info': {
            'executable': str(c_executable),
            'system': os.name,
            'platform': os.uname().sysname if hasattr(os, 'uname') else 'Windows'
        }
    }

    logger.info(f"Processing completed in {processing_time}. Success: {success_count}/{len(dataFiles)}")
    return JSONResponse(content=response_data)