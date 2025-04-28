import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import subprocess
from pathlib import Path
import traceback
import logging
import pandas as pd
from datetime import datetime
import shutil
import platform
import asyncio
import time
import uuid
from src.utils.settings import Config
from src.utils.helpers import join_operator_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("file_processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["file_processing"],
    responses={404: {"description": "Not found"}}
)

# Chemin vers le fichier CSV
CSV_FILE_PATH = "src/data/input.csv"

# Verrou pour éviter les traitements simultanés
processing_lock = False
current_job_id = None
# Dictionnaire pour stocker les informations sur les jobs en cours
JOBS: Dict[str, Dict[str, Any]] = {}

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
    
    try:
        # Update job status if job_id is provided
        if job_id and job_id in JOBS:
            JOBS[job_id]["status"] = "processing"
            JOBS[job_id]["progress"] = 5
            JOBS[job_id]["message"] = f"Préparation du fichier {file.filename}..."
        
        # Save input file with chunking for large files
        input_path = upload_dir / Path(file.filename).name
        if not await save_upload_file_chunked(file, input_path):
            file_result['error'] = "Could not save input file"
            return file_result

        # Prepare output path with unique identifier to avoid conflicts
        output_filename = f'output_{uuid.uuid4().hex}_{Path(file.filename).stem}.csv'
        output_path = upload_dir / output_filename
        
        # Update job status
        if job_id and job_id in JOBS:
            JOBS[job_id]["progress"] = 20
            JOBS[job_id]["message"] = f"Exécution du traitement pour {file.filename}..."
        
        # Execute processing with increased timeout
        cmd = executable_cmd + [str(input_path), str(output_path)]
        if append_mode:
            cmd.append("--append")
        
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

            # Update job status
            if job_id and job_id in JOBS:
                JOBS[job_id]["progress"] = 60
                JOBS[job_id]["message"] = f"Traitement des données pour {file.filename}..."

            # Process output with mapping
            processed_output = join_operator_data(str(output_path), str(mapping_path))
            if not processed_output or not Path(processed_output).exists():
                file_result['error'] = "Failed to join operator data"
                return file_result

            # Update job status
            if job_id and job_id in JOBS:
                JOBS[job_id]["progress"] = 80
                JOBS[job_id]["message"] = f"Finalisation du traitement pour {file.filename}..."

            file_result['success'] = True
            file_result['output_file'] = processed_output
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
            try:
                input_path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete input file {input_path}: {str(e)}")
        
        if 'output_path' in locals() and output_path.exists() and file_result['success']:
            try:
                # Only delete if processing was successful and we have the processed output
                output_path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete output file {output_path}: {str(e)}")
      
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
    appendMode: Optional[str] = Form("false"),
    background_tasks: BackgroundTasks = None
):
    """Endpoint for processing a single data file with a mapping file and appending to existing data"""
    global processing_lock, current_job_id
    
    start_time = datetime.now()
    logger.info(f"Process files endpoint called at {start_time}")

    # Vérifier si un traitement est déjà en cours
    if processing_lock:
        logger.warning(f"Tentative de traitement alors qu'un job est déjà en cours: {current_job_id}")
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": "Un traitement est déjà en cours. Veuillez réessayer plus tard."}
        )

    # Générer un ID unique pour ce job
    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    current_job_id = job_id
    processing_lock = True
    
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data file provided"
        )

    # Validate file extensions
    if not dataFiles.filename.lower().endswith('.txt'):
        processing_lock = False
        current_job_id = None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid file format for {dataFiles.filename}. Only .txt files allowed.'
        )

    if not mappingFile.filename.lower().endswith('.csv'):
        processing_lock = False
        current_job_id = None
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
        processing_lock = False
        current_job_id = None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing service unavailable"
        )

    try:
        # Save mapping file with chunking for large files
        mapping_path = upload_dir / f"{uuid.uuid4().hex}_{Path(mappingFile.filename).name}"
        if not await save_upload_file_chunked(mappingFile, mapping_path):
            processing_lock = False
            current_job_id = None
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save mapping file"
            )

        # Get appropriate command for the environment
        executable_cmd = get_executable_command(c_executable)
        logger.info(f"Using command: {executable_cmd}")

        # Update job status
        JOBS[job_id]["status"] = "processing"
        JOBS[job_id]["progress"] = 10
        JOBS[job_id]["message"] = "Traitement du fichier..."

        # Process the file
        result = await process_single_file(
            file=dataFiles,
            mapping_path=mapping_path,
            upload_dir=upload_dir,
            executable_cmd=executable_cmd,
            append_mode=append_mode,
            job_id=job_id
        )
        
        logger.info(f"File processing result: {result}")

        if not result['success']:
            processing_lock = False
            current_job_id = None
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process file: {result['error']}"
            )

        # Handle the processed output
        try:
            # Update job status
            JOBS[job_id]["progress"] = 85
            JOBS[job_id]["message"] = "Sauvegarde des résultats..."
            
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
                    # Utiliser un verrou de fichier pour éviter les conflits
                    lock_file = combined_output_path.with_suffix('.lock')
                    
                    # Attendre si un autre processus utilise le fichier
                    max_wait = 60  # secondes
                    wait_time = 0
                    while lock_file.exists() and wait_time < max_wait:
                        await asyncio.sleep(1)
                        wait_time += 1
                    
                    if lock_file.exists():
                        raise Exception(f"Lock file still exists after {max_wait}s, cannot proceed")
                    
                    # Créer le verrou
                    with lock_file.open('w') as f:
                        f.write(f"{job_id} - {datetime.now().isoformat()}")
                    
                    try:
                        existing_df = pd.read_csv(combined_output_path, low_memory=False)
                        logger.info(f"Existing file has {len(existing_df)} rows")
                        
                        # Désactivation complète de la détection des doublons
                        # Simplement concaténer les dataframes sans aucune vérification
                        combined_df = pd.concat([existing_df, processed_df], ignore_index=True)
                        logger.info(f"Combined dataframe has {len(combined_df)} rows (no duplicate detection)")
                        
                        # Information sur les doublons (toujours à 0 car désactivé)
                        duplicates_info = {"duplicates_found": 0, "duplicates_removed": 0}
                    except Exception as e:
                        logger.error(f"Error reading existing file: {e}")
                        # If there's an error reading the existing file, just use the processed data
                        combined_df = processed_df
                        duplicates_info = {"error": str(e)}
                finally:
                        # Supprimer le verrou
                        if lock_file.exists():
                            lock_file.unlink()
            else:
                    # If not appending or the file doesn't exist, just use the processed data
                    combined_df = processed_df
                    duplicates_info = {"duplicates_found": 0, "duplicates_removed": 0}
            
            # Update job status
            JOBS[job_id]["progress"] = 90
            JOBS[job_id]["message"] = "Écriture des données..."
            
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
            
            # Update job status
            JOBS[job_id]["progress"] = 95
            JOBS[job_id]["message"] = "Nettoyage des fichiers temporaires..."
            
            # Clean up temporary files
            try:
                # Clean up the mapping file
                if mapping_path.exists():
                    mapping_path.unlink()
                
                # Clean up the processed output file
                if processed_output_path.exists():
                    processed_output_path.unlink()
                
                # Clean up any other temporary files
                for file_path in upload_dir.iterdir():
                    if file_path != combined_output_path and file_path.is_file():
                        try:
                            file_path.unlink()
                            logger.debug(f"Deleted temporary file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to delete temporary file {file_path}: {str(e)}")
            except Exception as e:
                logger.error(f"Error cleaning up temporary files: {e}")
            
            # Update job status
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["progress"] = 100
            JOBS[job_id]["message"] = "Traitement terminé avec succès"

            # Release the lock
            processing_lock = False
            current_job_id = None

            return {
                "success": True,
                "message": f"File processed and {'added to' if append_mode else 'saved as'} input.csv",
                "rows_processed": len(processed_df),
                "total_rows": len(combined_df),
                "duplicates_info": duplicates_info if 'duplicates_info' in locals() else {"duplicates_found": 0},
                "job_id": job_id
            }
            
        except Exception as e:
            logger.error(f"Error handling processed output: {e}")
            traceback.print_exc()
            
            # Update job status
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)
            
            # Release the lock
            processing_lock = False
            current_job_id = None
            
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
        
        logger.error(f"Error in process_files_endpoint: {e}")
        traceback.print_exc()
        raise

@router.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Vérifier le statut d'un job de traitement"""
    if job_id not in JOBS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return JOBS[job_id]

@router.post("/reset-processing-lock")
async def reset_processing_lock():
    """Réinitialiser le verrou de traitement (pour les administrateurs uniquement)"""
    global processing_lock, current_job_id
    
    # Dans un environnement de production, ajoutez une authentification ici
    
    old_status = {"was_locked": processing_lock, "previous_job": current_job_id}
    
    processing_lock = False
    current_job_id = None
    
    return {"message": "Verrou réinitialisé avec succès", "previous_status": old_status}

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