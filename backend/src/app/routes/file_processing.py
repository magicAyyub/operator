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
        # Save input file
        input_path = upload_dir / Path(file.filename).name
        if not await save_upload_file(file, input_path):
            file_result['error'] = "Could not save input file"
            return file_result

        # Prepare output path
        output_path = upload_dir / f'output_{Path(file.filename).stem}.csv'
        
        # Execute processing
        cmd = executable_cmd + [str(input_path), str(output_path)]
        logger.info(f"Executing: {' '.join(cmd)}")

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            # Check process results
            if process.returncode != 0:
                error_msg = process.stderr or "Unknown processing error"
                file_result['error'] = clean_error_message(error_msg)
                return file_result

            # Process output with mapping
            processed_output = join_operator_data(output_path, mapping_path)
            if not processed_output or not Path(processed_output).exists():
                file_result['error'] = "Failed to join operator data"
                return file_result

            file_result['success'] = True
            file_result['output_file'] = Path(processed_output).name
            return file_result

        except subprocess.TimeoutExpired:
            file_result['error'] = "Processing timed out"
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

async def save_upload_file(upload_file: UploadFile, destination: Path) -> bool:
    """Save uploaded file to destination"""
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

    # Save mapping file
    mapping_path = upload_dir / Path(mappingFile.filename).name
    if not await save_upload_file(mappingFile, mapping_path):
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

    for idx, file in enumerate(dataFiles, 1):
        result = await process_single_file(
            file=file,
            idx=idx,
            total_files=len(dataFiles),
            upload_dir=upload_dir,
            mapping_path=mapping_path,
            executable_cmd=executable_cmd
        )
        results.append(result)

        # If successful, add to combined output
        if result['success']:
            try:
                output_path = upload_dir / result['output_file']
                file_df = pd.read_csv(output_path)
                combined_df = pd.concat([combined_df, file_df], ignore_index=True) if combined_df is not None else file_df
            except Exception as e:
                logger.error(f"Error combining output for {file.filename}: {str(e)}")
                result['success'] = False
                result['error'] = f"Output combination failed: {str(e)}"

    # Save combined output
    combined_output_path = upload_dir / 'input.csv'
    if combined_df is not None and not combined_df.empty:
        try:
            combined_df.to_csv(combined_output_path, index=False)
            Config.PROCESSED_CSV = 'input.csv'
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
        'environment': {
            'system': platform.system(),
            'release': platform.release(),
            'is_wsl': is_wsl(),
            'executable': str(c_executable),
            'command_used': ' '.join(executable_cmd)
        }
    }

    return JSONResponse(content=response_data)