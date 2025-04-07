import os
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List
import subprocess
from pathlib import Path
import traceback
import logging
import pandas as pd
from src.utils.helpers import join_operator_data
from src.utils.settings import Config

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["file_processing"])

@router.post("/process_files")
async def process_files_endpoint(
    dataFiles: List[UploadFile] = File(...),
    mappingFile: UploadFile = File(...)
):
    """
    Endpoint to process files and join operator data.
    """
    logger.info("Process files endpoint called")
    
    # Validate files
    for file in dataFiles:
        if not file.filename.endswith('.txt'):
            logger.error(f"Invalid file format for {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid file format for {file.filename}. Only .txt files are allowed.'
            )
    
    if not mappingFile.filename.endswith('.csv'):
        logger.error(f"Invalid mapping file format: {mappingFile.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid mapping file format. Only .csv files are allowed.'
        )
    
    logger.info(f"Received {len(dataFiles)} data files and 1 mapping file")
    
    # Ensure upload directory exists
    os.makedirs(Path(Config.UPLOAD_FOLDER), exist_ok=True)
    
    # Save mapping file
    mapping_path = Path(Config.UPLOAD_FOLDE) / Path(mappingFile.filename).name
    try:
        with open(mapping_path, "wb") as f:
            f.write(await mappingFile.read())
        logger.info(f"Mapping file saved to {mapping_path}")
    except Exception as e:
        logger.error(f"Error saving mapping file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save mapping file"
        )
    
    results = []
    total_files = len(dataFiles)
    processed_files = 0
    combined_df = None
    combined_output_path = Path(Config.UPLOAD_FOLDER) / 'input.csv'
    
    # Process each data file
    for idx, file in enumerate(dataFiles, 1):
        try:
            logger.info(f"Processing file {idx}/{total_files}: {file.filename}")
            
            input_path = Path(Config.UPLOAD_FOLDER) / Path(file.filename).name
            output_path = Path(Config.UPLOAD_FOLDER) / f'output_{Path(file.filename).name}.csv'
            
            # Save the data file
            try:
                with open(input_path, "wb") as f:
                    f.write(await file.read())
                logger.info(f"Data file saved to {input_path}")
            except Exception as e:
                logger.error(f"Error saving data file: {str(e)}")
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'error': "Could not save file"
                })
                continue
            
            # Run the C executable
            cmd = [
                str(Path(Config.C_EXECUTABLE_PATH)), 
                str(input_path), 
                str(output_path)
            ]
            logger.info(f"Running command: {' '.join(cmd)}")
            
            try:
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )
                
                logger.info(f"Process return code: {process.returncode}")
                if process.stdout:
                    logger.info(f"Process stdout: {process.stdout}")
                if process.stderr:
                    logger.error(f"Process stderr: {process.stderr}")
                
                if process.returncode != 0:
                    error_msg = process.stderr or "Unknown error during file processing"
                    logger.error(f"Processing failed for {file.filename}: {error_msg}")
                    results.append({
                        'filename': file.filename,
                        'success': False,
                        'error': error_msg
                    })
                    continue
                
                logger.info(f"Processing successful for {file.filename}")
                
                # Join operator data to the output file
                processed_output_path = join_operator_data(output_path, mapping_path)
                
                if processed_output_path:
                    results.append({
                        'filename': file.filename,
                        'success': True,
                        'output_file': Path(processed_output_path).name
                    })
                    
                    # Add to combined output
                    file_df = pd.read_csv(processed_output_path)
                    if combined_df is None:
                        combined_df = file_df
                    else:
                        combined_df = pd.concat([combined_df, file_df], ignore_index=True)
                    
                    # Clean up intermediate CSV
                    if output_path.exists():
                        output_path.unlink()
                        logger.info(f"Cleaned up intermediate CSV file: {output_path}")
                else:
                    results.append({
                        'filename': file.filename,
                        'success': False,
                        'error': "Failed to join operator data"
                    })
                    # Clean up intermediate CSV if joining failed
                    if output_path.exists():
                        output_path.unlink()
                        logger.info(f"Cleaned up intermediate CSV file: {output_path}")
            
            except Exception as e:
                logger.error(f"Error running subprocess for {file.filename}: {str(e)}")
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'error': str(e)
                })
                continue
            
            # Clean up input file
            if input_path.exists():
                input_path.unlink()
                logger.info(f"Cleaned up input file: {input_path}")
            
            processed_files += 1
        
        except Exception as e:
            logger.error(f"Exception processing {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            results.append({
                'filename': file.filename,
                'success': False,
                'error': str(e)
            })
    
    # Save combined output if we have processed files
    if combined_df is not None:
        combined_df.to_csv(combined_output_path, index=False)
        logger.info(f"Combined output saved to {combined_output_path}")
        Config.PROCESSED_CSV = 'input.csv'
    
    # Clean up mapping file after all files are processed
    if mapping_path.exists():
        mapping_path.unlink()
        logger.info(f"Cleaned up mapping file: {mapping_path}")
    
    # Count successful files
    success_count = sum(1 for result in results if result['success'])
    logger.info(f"Processing complete. {success_count}/{total_files} files processed successfully")
    
    response_data = {
        'success': success_count > 0,
        'filesProcessed': success_count,
        'totalFiles': total_files,
        'details': results
    }
    logger.info(f"Returning response: {response_data}")
    
    return JSONResponse(content=response_data)