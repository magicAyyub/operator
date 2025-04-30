import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import subprocess
from pathlib import Path
import traceback
import pandas as pd
from datetime import datetime
import shutil
import platform
import asyncio
import time
import uuid
import tempfile
from src.utils.settings import Config
from src.utils.helpers import join_operator_data
import warnings
from src.utils.helpers import clean_error_message
import logging
import json
import sys
import colorlog

# Silence all pandas warnings
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

# Configure logging with colors and ensure absolute paths for log files
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'logs'))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'file_processing.log')

# Create a custom formatter with colors
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s [%(levelname)s] %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

# Create a file handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

# Configure the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.addHandler(file_handler)

# Silence the noisy python_multipart.multipart debug logs
logging.getLogger("python_multipart.multipart").setLevel(logging.WARNING)

# Log startup information
logger.info("=" * 80)
logger.info("FILE PROCESSING MODULE STARTING")
logger.info(f"Log file: {LOG_FILE}")
logger.info("=" * 80)

router = APIRouter(
    prefix="/api",
    tags=["file_processing"],
    responses={404: {"description": "Not found"}}
)

# Chemin vers le fichier CSV
CSV_FILE_PATH = "src/data/input.csv"
# Chemin vers le fichier d'index pour optimiser les appends
CSV_INDEX_PATH = "src/data/input_index.json"

# Verrou pour éviter les traitements simultanés
processing_lock = False
current_job_id = None
# Dictionnaire pour stocker les informations sur les jobs en cours
JOBS: Dict[str, Dict[str, Any]] = {}

def inspect_csv_file(file_path: str, description: str = "CSV file"):
    """Inspect a CSV file and log key information for debugging"""
    if not os.path.exists(file_path):
        logger.warning(f"{description} not found: {file_path}")
        return False
    
    try:
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Try to read the header to get column names
        df = pd.read_csv(file_path, nrows=1)
        
        logger.info("-" * 50)
        logger.info(f"{description.upper()} INSPECTION: {file_path}")
        logger.info(f"File size: {file_size / 1024:.2f} KB")
        logger.info(f"Columns ({len(df.columns)}): {', '.join(df.columns)}")
        
        # Check for potential issues with column names
        problematic_columns = [col for col in df.columns if any(c in col for c in '"\',.()[]{}+-*/=<>!@#$%^&*')]
        if problematic_columns:
            logger.warning(f"Columns with special characters that may need quoting: {', '.join(problematic_columns)}")
        
        logger.info("-" * 50)
        return True
    except Exception as e:
        logger.error(f"Error inspecting {description}: {str(e)}")
        return False

def is_wsl() -> bool:
    """Check if running in WSL environment"""
    wsl_check = 'microsoft' in platform.uname().release.lower()
    logger.debug(f"WSL environment check: {wsl_check}")
    return wsl_check

def get_executable_command(executable_path: Path) -> list:
    """Get the appropriate command for the executable based on environment"""
    if is_wsl():
        # If running in WSL but executable is Windows binary
        if '.exe' in executable_path.suffix.lower():
            logger.debug(f"Using WSL with Windows executable: {executable_path}")
            return ['wsl', str(executable_path)]
        logger.debug(f"Using WSL with Linux executable: {executable_path}")
        return [str(executable_path)]
    logger.debug(f"Using native executable: {executable_path}")
    return [str(executable_path)]

async def process_single_file(
    file: UploadFile,
    mapping_path: Path,
    upload_dir: Path,
    executable_cmd: list,
    append_mode: bool = False,
    job_id: str = None
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
    
    logger.info("=" * 80)
    logger.info(f"🔄 PROCESSING FILE: {file.filename}")
    logger.info(f"Mode: {'APPEND' if append_mode else 'NEW'}, Job ID: {job_id}")
    logger.info("=" * 80)
    
    try:
        # Update job status if job_id is provided
        if job_id and job_id in JOBS:
            JOBS[job_id]["status"] = "processing"
            JOBS[job_id]["progress"] = 5
            JOBS[job_id]["message"] = f"Préparation du fichier {file.filename}..."
        
        # Save input file with chunking for large files
        input_path = upload_dir / Path(file.filename).name
        logger.info(f"📥 Saving uploaded file to: {input_path}")
        
        if not await save_upload_file_chunked(file, input_path):
            file_result['error'] = "Could not save input file"
            logger.error(f"❌ Failed to save input file: {input_path}")
            return file_result

        # Check if the file was saved correctly
        if input_path.exists():
            file_size = input_path.stat().st_size
            logger.info(f"✅ Input file saved successfully. Size: {file_size / 1024:.2f} KB")
        else:
            logger.error(f"❌ Input file does not exist after save operation: {input_path}")
            file_result['error'] = "Input file not found after save operation"
            return file_result

        # Prepare output path with unique identifier to avoid conflicts
        output_filename = f'output_{uuid.uuid4().hex}_{Path(file.filename).stem}.csv'
        output_path = upload_dir / output_filename
        logger.info(f"📤 Output path set to: {output_path}")
        
        # Update job status
        if job_id and job_id in JOBS:
            JOBS[job_id]["progress"] = 20
            JOBS[job_id]["message"] = f"Exécution du traitement pour {file.filename}..."
        
        # Execute processing with increased timeout
        cmd = executable_cmd + [str(input_path), str(output_path)]
        logger.info(f"🚀 Executing command: {' '.join(cmd)}")

        try:
            # Increased timeout to 20 minutes (1200 seconds)
            logger.info(f"⏱️ Running subprocess with timeout of 1200 seconds")
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1200
            )

            # Log process output for debugging
            if process.stdout:
                logger.info(f"Process stdout: {process.stdout[:100]}..." if len(process.stdout) > 100 else f"Process stdout: {process.stdout}")
            if process.stderr:
                logger.error(f"Process stderr: {process.stderr[:100]}..." if len(process.stderr) > 100 else f"Process stderr: {process.stderr}")
            
            logger.info(f"Process completed with return code: {process.returncode}")

            # Check process results
            if process.returncode != 0:
                error_msg = process.stderr or "Unknown processing error"
                file_result['error'] = clean_error_message(error_msg)
                logger.error(f"❌ Process failed with error: {file_result['error']}")
                return file_result

            # Check if output file was created
            if not output_path.exists():
                file_result['error'] = "Output file was not created by the process"
                logger.error(f"❌ Output file not found: {output_path}")
                return file_result
            
            # Log output file details
            output_file_size = output_path.stat().st_size
            logger.info(f"✅ Output file created successfully. Size: {output_file_size / 1024:.2f} KB")

            # Update job status
            if job_id and job_id in JOBS:
                JOBS[job_id]["progress"] = 60
                JOBS[job_id]["message"] = f"Traitement des données pour {file.filename}..."

            # Process output with mapping
            logger.info(f"🔄 Joining operator data with mapping file: {mapping_path}")
            processed_output = join_operator_data(str(output_path), str(mapping_path))
            
            if not processed_output:
                file_result['error'] = "Failed to join operator data - returned None"
                logger.error("❌ join_operator_data returned None")
                return file_result
                
            if not Path(processed_output).exists():
                file_result['error'] = "Failed to join operator data - output file not found"
                logger.error(f"❌ Processed output file not found: {processed_output}")
                return file_result
            
            # Log processed output file details
            processed_file_size = Path(processed_output).stat().st_size
            logger.info(f"✅ Processed output file created successfully: {processed_output} ({processed_file_size / 1024:.2f} KB)")
            
            # Verify processed output file
            inspect_csv_file(processed_output, "Processed output file")

            # Update job status
            if job_id and job_id in JOBS:
                JOBS[job_id]["progress"] = 80
                JOBS[job_id]["message"] = f"Finalisation du traitement pour {file.filename}..."

            file_result['success'] = True
            file_result['output_file'] = processed_output
            logger.info(f"✅ File processing completed successfully: {processed_output}")
            return file_result

        except subprocess.TimeoutExpired:
            file_result['error'] = "Processing timed out after 20 minutes"
            logger.error("❌ Subprocess timed out after 20 minutes")
        except subprocess.CalledProcessError as e:
            file_result['error'] = f"Processing failed: {str(e)}"
            logger.error(f"❌ Subprocess failed with CalledProcessError: {e}")
        except Exception as e:
            file_result['error'] = f"Unexpected error: {str(e)}"
            logger.error(f"❌ Unexpected error during subprocess execution: {e}")
            traceback.print_exc()

    except Exception as e:
        logger.error(f"❌ Error processing {file.filename}: {str(e)}")
        traceback.print_exc()
        file_result['error'] = f"Processing error: {str(e)}"
    finally:
        file_result['processing_time'] = str(datetime.now() - start_time)
        logger.info(f"⏱️ Total processing time: {file_result['processing_time']}")
        
        # Clean up temporary files
        if 'input_path' in locals() and input_path.exists():
            try:
                logger.debug(f"🧹 Cleaning up input file: {input_path}")
                input_path.unlink()
            except Exception as e:
                logger.error(f"❌ Failed to delete input file {input_path}: {str(e)}")
        
        if 'output_path' in locals() and output_path.exists() and file_result['success']:
            try:
                # Only delete if processing was successful and we have the processed output
                logger.debug(f"🧹 Cleaning up output file: {output_path}")
                output_path.unlink()
            except Exception as e:
                logger.error(f"❌ Failed to delete output file {output_path}: {str(e)}")
        
        logger.info("=" * 80)
        logger.info(f"FILE PROCESSING {'COMPLETED ✅' if file_result['success'] else 'FAILED ❌'}")
        logger.info("=" * 80)
      
    return file_result

async def save_upload_file_chunked(upload_file: UploadFile, destination: Path) -> bool:
    """Save uploaded file to destination using chunked approach for large files"""
    logger.info(f"📥 Starting chunked save of file {upload_file.filename}")
    
    try:
        # Use a larger chunk size for better performance
        chunk_size = 4 * 1024 * 1024  # 4MB chunks for better performance
        total_size = 0
        chunks_count = 0
        
        with destination.open("wb") as buffer:
            # Read and write in chunks
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break
                buffer.write(chunk)
                total_size += len(chunk)
                chunks_count += 1
                # Log progress for large files
                if chunks_count % 10 == 0:
                    logger.debug(f"Saved {chunks_count} chunks ({total_size / (1024*1024):.2f} MB)")
                # Allow other tasks to run between chunks
                await asyncio.sleep(0)
        
        logger.info(f"✅ File saved successfully: {destination}. Total size: {total_size / (1024*1024):.2f} MB in {chunks_count} chunks")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving file {upload_file.filename}: {str(e)}")
        traceback.print_exc()
        return False

async def append_to_csv_optimized(processed_df: pd.DataFrame, combined_output_path: Path, job_id: str) -> dict:
    """
    Optimized function to append data to existing CSV file
    Uses a temporary file approach to avoid memory issues with large files
    """
    logger.info("=" * 80)
    logger.info(f"🔄 APPEND OPERATION: {combined_output_path.name}")
    logger.info(f"Data to append: {len(processed_df)} rows, {len(processed_df.columns)} columns")
    logger.info("=" * 80)
    
    try:
        # Update job status
        if job_id in JOBS:
            JOBS[job_id]["progress"] = 85
            JOBS[job_id]["message"] = "Sauvegarde des résultats..."
        
        # Create a temporary file for the new data
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / f"temp_append_{uuid.uuid4().hex}.csv"
        logger.info(f"📄 Created temporary file for append: {temp_file}")
        
        # Save the processed data to the temporary file
        processed_df.to_csv(temp_file, index=False)
        logger.info(f"✅ Saved processed data to temporary file. Size: {temp_file.stat().st_size / 1024:.2f} KB")
        
        # If the combined output file doesn't exist, just rename the temp file
        if not combined_output_path.exists():
            logger.info(f"📄 Target file doesn't exist, creating new file: {combined_output_path}")
            # Ensure the directory exists
            combined_output_path.parent.mkdir(exist_ok=True, parents=True)
            logger.info(f"📤 Moving temporary file to final destination")
            shutil.move(str(temp_file), str(combined_output_path))
            logger.info(f"✅ Created new file with {len(processed_df)} rows")
            
            # Verify the newly created file
            inspect_csv_file(str(combined_output_path), "Newly created CSV file")
            
            return {
                "success": True,
                "rows_added": len(processed_df),
                "total_rows": len(processed_df)
            }
        
        # For append operations, use a more efficient approach
        # Create a lock file to prevent concurrent access
        lock_file = combined_output_path.with_suffix('.lock')
        logger.info(f"🔒 Using lock file: {lock_file}")
        
        # Wait if another process is using the file
        max_wait = 60  # seconds
        wait_time = 0
        while lock_file.exists() and wait_time < max_wait:
            logger.debug(f"Lock file exists, waiting... ({wait_time}s)")
            await asyncio.sleep(1)
            wait_time += 1
        
        if lock_file.exists():
            logger.error(f"❌ Lock file still exists after {max_wait}s, cannot proceed")
            raise Exception(f"Lock file still exists after {max_wait}s, cannot proceed")
        
        # Create the lock
        with lock_file.open('w') as f:
            f.write(f"{job_id} - {datetime.now().isoformat()}")
        logger.info(f"🔒 Created lock file")
        
        try:
            # Log the existing file details
            existing_file_size = combined_output_path.stat().st_size
            logger.info(f"📄 Existing file size: {existing_file_size / 1024:.2f} KB")
            
            # Verify the existing file
            inspect_csv_file(str(combined_output_path), "Existing CSV file before append")
            
            # Instead of reading the entire file into memory, we'll use a streaming approach
            # Create a new file that will contain both the existing data and the new data
            final_output = combined_output_path.with_suffix('.new.csv')
            logger.info(f"📄 Creating new combined file: {final_output}")
            
            # First, copy the header from the processed data
            with open(temp_file, 'r') as src, open(final_output, 'w') as dest:
                # Copy the header
                header = src.readline()
                dest.write(header)
                logger.info(f"✅ Wrote header to new file")
            
            # Now append the existing data (skipping the header)
            logger.info(f"🔄 Appending existing data from {combined_output_path.name}")
            existing_rows = 0
            with open(combined_output_path, 'r') as src, open(final_output, 'a') as dest:
                # Skip the header
                src.readline()
                # Copy the rest line by line
                for line in src:
                    dest.write(line)
                    existing_rows += 1
                    # Log progress for large files
                    if existing_rows % 100000 == 0:
                        logger.info(f"Progress: Copied {existing_rows} existing rows")
            
            logger.info(f"✅ Appended {existing_rows} existing rows")
            
            # Now append the new data (skipping the header)
            logger.info(f"🔄 Appending new data")
            new_rows = 0
            with open(temp_file, 'r') as src, open(final_output, 'a') as dest:
                # Skip the header
                src.readline()
                # Copy the rest line by line
                for line in src:
                    dest.write(line)
                    new_rows += 1
                    # Log progress for large files
                    if new_rows % 100000 == 0:
                        logger.info(f"Progress: Copied {new_rows} new rows")
            
            logger.info(f"✅ Appended {new_rows} new rows")
            
            # Count the total number of rows (approximate)
            total_rows = existing_rows + new_rows
            logger.info(f"📊 Total rows in combined file: {total_rows}")
            
            # Replace the original file with the new one
            logger.info(f"🔄 Replacing original file with combined file")
            shutil.move(str(final_output), str(combined_output_path))
            logger.info(f"✅ Successfully replaced original file with combined file")
            
            # Verify the final file
            final_file_size = combined_output_path.stat().st_size
            logger.info(f"📄 Final file size: {final_file_size / 1024:.2f} KB")
            
            # Verify the final combined file
            inspect_csv_file(str(combined_output_path), "Final combined CSV file")
            
            logger.info("=" * 80)
            logger.info(f"APPEND OPERATION COMPLETED SUCCESSFULLY ✅")
            logger.info(f"Added {new_rows} rows to existing {existing_rows} rows")
            logger.info("=" * 80)
            
            return {
                "success": True,
                "rows_added": new_rows,
                "total_rows": total_rows
            }
        finally:
            # Clean up
            logger.info("🧹 Cleaning up temporary files")
            if lock_file.exists():
                logger.info(f"🔓 Removing lock file")
                lock_file.unlink()
            if temp_file.exists():
                logger.info(f"🧹 Removing temporary file")
                temp_file.unlink()
            if 'final_output' in locals() and final_output.exists():
                logger.info(f"🧹 Removing temporary output file")
                final_output.unlink()
    
    except Exception as e:
        logger.error(f"❌ Error in append operation: {e}")
        traceback.print_exc()
        logger.info("=" * 80)
        logger.info(f"APPEND OPERATION FAILED ❌")
        logger.info("=" * 80)
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/process_files", response_model=dict)
async def process_files_endpoint(
    dataFiles: UploadFile = File(...),
    mappingFile: UploadFile = File(...),
    appendMode: Optional[str] = Form("false"),
    background_tasks: BackgroundTasks = None
):
    """Endpoint for processing a single data file with a mapping file and appending to existing data"""
    global processing_lock, current_job_id
    
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"🚀 PROCESS FILES ENDPOINT CALLED")
    logger.info(f"Data file: {dataFiles.filename}, Mapping file: {mappingFile.filename}, Append mode: {appendMode}")
    logger.info("=" * 80)

    # Vérifier si un traitement est déjà en cours
    if processing_lock:
        logger.warning(f"⚠️ Processing already in progress: job_id={current_job_id}")
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": "Un traitement est déjà en cours. Veuillez réessayer plus tard."}
        )

    # Générer un ID unique pour ce job
    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    current_job_id = job_id
    processing_lock = True
    logger.info(f"🆔 Created new job with ID: {job_id}")
    
    # Initialiser le statut du job
    JOBS[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "En attente de traitement...",
        "createdAt": time.time(),
        "file": dataFiles.filename
    }

    # Validate input files
    if not dataFiles:
        processing_lock = False
        current_job_id = None
        logger.error("❌ No data file provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data file provided"
        )

    # Validate file extensions
    if not dataFiles.filename.lower().endswith('.txt'):
        processing_lock = False
        current_job_id = None
        logger.error(f"❌ Invalid file format: {dataFiles.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid file format for {dataFiles.filename}. Only .txt files allowed.'
        )

    if not mappingFile.filename.lower().endswith('.csv'):
        processing_lock = False
        current_job_id = None
        logger.error(f"❌ Invalid mapping file format: {mappingFile.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid mapping file format. Only .csv files allowed.'
        )

    # Convert appendMode string to boolean
    append_mode = appendMode.lower() == "true"
    logger.info(f"Mode: {'APPEND' if append_mode else 'NEW'}")

    # Setup working directory
    upload_dir = Path(Config.UPLOAD_FOLDER)
    upload_dir.mkdir(exist_ok=True, parents=True)
    logger.info(f"📁 Using upload directory: {upload_dir}")
    
    # Verify executable
    c_executable = Path(Config.C_EXECUTABLE_PATH)
    logger.info(f"🔍 Checking executable: {c_executable}")
    if not c_executable.exists():
        processing_lock = False
        current_job_id = None
        logger.error(f"❌ Executable not found: {c_executable}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing service unavailable"
        )
    else:
        logger.info(f"✅ Executable found: {c_executable}")

    try:
        # Save mapping file with chunking for large files
        mapping_path = upload_dir / f"{uuid.uuid4().hex}_{Path(mappingFile.filename).name}"
        logger.info(f"📥 Saving mapping file to: {mapping_path}")
        
        if not await save_upload_file_chunked(mappingFile, mapping_path):
            processing_lock = False
            current_job_id = None
            logger.error("❌ Failed to save mapping file")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save mapping file"
            )
        
        # Verify the mapping file
        inspect_csv_file(str(mapping_path), "Mapping file")

        # Get appropriate command for the environment
        executable_cmd = get_executable_command(c_executable)
        logger.info(f"🔧 Using command: {' '.join(executable_cmd)}")

        # Update job status
        JOBS[job_id]["status"] = "processing"
        JOBS[job_id]["progress"] = 10
        JOBS[job_id]["message"] = "Traitement du fichier..."

        # Process the file
        logger.info(f"🔄 Starting file processing for {dataFiles.filename}")
        result = await process_single_file(
            file=dataFiles,
            mapping_path=mapping_path,
            upload_dir=upload_dir,
            executable_cmd=executable_cmd,
            append_mode=append_mode,
            job_id=job_id
        )
        
        logger.info(f"Result: {'SUCCESS ✅' if result['success'] else 'FAILED ❌'}")

        if not result['success']:
            processing_lock = False
            current_job_id = None
            logger.error(f"❌ File processing failed: {result['error']}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process file: {result['error']}"
            )

        # Handle the processed output
        try:
            # Path to the combined output file
            combined_output_path = Path(CSV_FILE_PATH)
            logger.info(f"📄 Combined output path: {combined_output_path}")
            
            # Path to the processed output file
            processed_output_path = Path(result['output_file'])
            logger.info(f"📄 Processed output path: {processed_output_path}")
            
            # Check if processed output file exists
            if not processed_output_path.exists():
                raise Exception(f"Processed output file not found: {processed_output_path}")
            
            # Read the processed data
            logger.info(f"📊 Reading processed data")
            processed_df = pd.read_csv(processed_output_path, low_memory=False)
            logger.info(f"✅ Processed file has {len(processed_df)} rows and {len(processed_df.columns)} columns")
            
            # Use the optimized append function
            if append_mode and combined_output_path.exists():
                logger.info(f"🔄 Appending to existing file: {combined_output_path}")
                append_result = await append_to_csv_optimized(processed_df, combined_output_path, job_id)
                
                if not append_result["success"]:
                    error_msg = append_result.get('error', 'Unknown error')
                    logger.error(f"❌ Failed to append data: {error_msg}")
                    raise Exception(f"Failed to append data: {error_msg}")
                
                total_rows = append_result["total_rows"]
                logger.info(f"✅ Append successful. Total rows: {total_rows}")
                duplicates_info = {"duplicates_found": 0, "duplicates_removed": 0}
            else:
                # If not appending or the file doesn't exist, just save the processed data
                logger.info(f"📄 Saving processed data as new file: {combined_output_path}")
                combined_output_path.parent.mkdir(exist_ok=True, parents=True)
                processed_df.to_csv(combined_output_path, index=False)
                total_rows = len(processed_df)
                logger.info(f"✅ Saved new file with {total_rows} rows")
                duplicates_info = {"duplicates_found": 0, "duplicates_removed": 0}
                
                # Verify the newly created file
                inspect_csv_file(str(combined_output_path), "Newly created CSV file")
            
            # Update job status
            JOBS[job_id]["progress"] = 95
            JOBS[job_id]["message"] = "Nettoyage des fichiers temporaires..."
            
            # Clean up temporary files
            try:
                # Clean up the mapping file
                if mapping_path.exists():
                    logger.info(f"🧹 Removing mapping file")
                    mapping_path.unlink()
                
                # Clean up the processed output file
                if processed_output_path.exists():
                    logger.info(f"🧹 Removing processed output file")
                    processed_output_path.unlink()
            except Exception as e:
                logger.error(f"❌ Error cleaning up temporary files: {e}")
            
            # Update job status
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["progress"] = 100
            JOBS[job_id]["message"] = "Traitement terminé avec succès"

            # Release the lock
            processing_lock = False
            current_job_id = None
            logger.info(f"🔓 Released processing lock. Job {job_id} completed successfully")

            logger.info("=" * 80)
            logger.info(f"PROCESS FILES ENDPOINT COMPLETED SUCCESSFULLY ✅")
            logger.info(f"Total processing time: {datetime.now() - start_time}")
            logger.info("=" * 80)

            return {
                "success": True,
                "message": f"File processed and {'added to' if append_mode else 'saved as'} input.csv",
                "rows_processed": len(processed_df),
                "total_rows": total_rows,
                "duplicates_info": duplicates_info,
                "job_id": job_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error handling processed output: {e}")
            traceback.print_exc()
            
            # Update job status
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)
            
            # Release the lock
            processing_lock = False
            current_job_id = None
            logger.info(f"🔓 Released processing lock due to error. Job {job_id} failed")
            
            logger.info("=" * 80)
            logger.info(f"PROCESS FILES ENDPOINT FAILED ❌")
            logger.info("=" * 80)
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error handling processed output: {str(e)}"
            )
    except Exception as e:
        # Update job status
        if job_id in JOBS:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)
        
        # Release the lock
        processing_lock = False
        current_job_id = None
        logger.info(f"🔓 Released processing lock due to error. Job {job_id} failed")
        
        logger.error(f"❌ Error in process_files_endpoint: {e}")
        traceback.print_exc()
        
        logger.info("=" * 80)
        logger.info(f"PROCESS FILES ENDPOINT FAILED ❌")
        logger.info("=" * 80)
        
        raise

@router.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Vérifier le statut d'un job de traitement"""
    logger.info(f"🔍 Checking status for job: {job_id}")
    
    if job_id not in JOBS:
        logger.warning(f"❌ Job not found: {job_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    logger.info(f"✅ Job status: {JOBS[job_id]['status']}, progress: {JOBS[job_id]['progress']}%")
    return JOBS[job_id]

@router.post("/reset-processing-lock")
async def reset_processing_lock():
    """Réinitialiser le verrou de traitement (pour les administrateurs uniquement)"""
    global processing_lock, current_job_id
    
    logger.info("🔄 Reset processing lock requested")
    # Dans un environnement de production, ajoutez une authentification ici
    
    old_status = {"was_locked": processing_lock, "previous_job": current_job_id}
    
    processing_lock = False
    current_job_id = None
    logger.info("✅ Processing lock reset successfully")
    
    return {"message": "Verrou réinitialisé avec succès", "previous_status": old_status}

@router.get("/csv/check")
def check_file():
    """Vérifie si un fichier de données existe déjà"""
    logger.info("🔍 Checking if CSV file exists")
    exists = os.path.exists(CSV_FILE_PATH)
    
    if exists:
        file_size = os.path.getsize(CSV_FILE_PATH)
        logger.info(f"✅ CSV file exists: {CSV_FILE_PATH} ({file_size / 1024:.2f} KB)")
        
        # Verify the existing file
        inspect_csv_file(CSV_FILE_PATH, "Existing CSV file")
    else:
        logger.info("❌ CSV file does not exist")
    
    return {"exists": exists}

@router.delete("/csv/purge")
def purge_data():
    """Supprime le fichier de données existant"""
    logger.info("🗑️ Purging CSV data")
    
    try:
        if os.path.exists(CSV_FILE_PATH):
            file_size = os.path.getsize(CSV_FILE_PATH)
            logger.info(f"🗑️ Deleting CSV file: {CSV_FILE_PATH} ({file_size / 1024:.2f} KB)")
            
            os.remove(CSV_FILE_PATH)
            logger.info(f"✅ CSV file deleted")
            
            # Also remove the index file if it exists
            if os.path.exists(CSV_INDEX_PATH):
                logger.info(f"🗑️ Deleting index file: {CSV_INDEX_PATH}")
                os.remove(CSV_INDEX_PATH)
                logger.info(f"✅ Index file deleted")
                
            return {"success": True, "message": "Données purgées avec succès"}
        else:
            logger.info("No CSV file to purge")
            return {"success": True, "message": "Aucun fichier à purger"}
    except Exception as e:
        logger.error(f"❌ Error purging data: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur lors de la purge des données: {str(e)}"}
        )

@router.get("/health")
async def health_check():
    """Simple health check endpoint to verify server availability"""
    logger.info("🔍 Health check requested")
    
    # Check if CSV file exists and log its status
    csv_exists = os.path.exists(CSV_FILE_PATH)
    if csv_exists:
        file_size = os.path.getsize(CSV_FILE_PATH)
        logger.info(f"✅ CSV file exists: {CSV_FILE_PATH} ({file_size / 1024:.2f} KB)")
    else:
        logger.info("❌ CSV file does not exist")
    
    return {
        "status": "ok",
        "message": "Server is running",
        "timestamp": datetime.now().isoformat(),
        "csv_file_exists": csv_exists
    }

# Log module loaded
logger.info("=" * 80)
logger.info("FILE PROCESSING MODULE LOADED SUCCESSFULLY")
logger.info("=" * 80)