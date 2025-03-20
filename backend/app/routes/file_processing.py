from pathlib import Path
import os
from flask import Blueprint, request, jsonify, current_app
import subprocess
from werkzeug.utils import secure_filename
from app.config import Config
import time
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

file_bp = Blueprint('file_processing', __name__)

@file_bp.route('/api/process_files', methods=['POST'])
def process_files_endpoint():
    logger.info("Process files endpoint called")
    
    if 'dataFiles' not in request.files:
        logger.error("No data files provided")
        return jsonify({'error': 'No data files provided'}), 400
    
    if 'mappingFile' not in request.files:
        logger.error("No mapping file provided")
        return jsonify({'error': 'No mapping file provided'}), 400
    
    # Get all data files (multiple files)
    data_files = request.files.getlist('dataFiles')
    mapping_file = request.files['mappingFile']
    
    logger.info(f"Received {len(data_files)} data files and 1 mapping file")
    
    # Validate files
    for file in data_files:
        if not file.filename.endswith('.txt'):
            logger.error(f"Invalid file format for {file.filename}")
            return jsonify({'error': f'Invalid file format for {file.filename}. Only .txt files are allowed.'}), 400
    
    if not mapping_file.filename.endswith('.csv'):
        logger.error(f"Invalid mapping file format: {mapping_file.filename}")
        return jsonify({'error': 'Invalid mapping file format. Only .csv files are allowed.'}), 400
    
    # Ensure upload directory exists
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    
    # Save mapping file - we'll still save it even though we don't pass it to the executable
    # It might be used for other purposes or future enhancements
    mapping_path = Config.UPLOAD_FOLDER / secure_filename(mapping_file.filename)
    mapping_file.save(mapping_path)
    logger.info(f"Mapping file saved to {mapping_path}")
    
    results = []
    total_files = len(data_files)
    processed_files = 0
    
    # Process each data file
    for file in data_files:
        try:
            input_path = Config.UPLOAD_FOLDER / secure_filename(file.filename)
            output_path = Config.UPLOAD_FOLDER / f'output_{secure_filename(file.filename)}.csv'
            
            # Save the data file
            file.save(input_path)
            logger.info(f"Data file saved to {input_path}")
            
            # Emit progress update via Socket.IO if available
            if hasattr(current_app, 'socketio'):
                progress = int((processed_files / total_files) * 100)
                current_app.socketio.emit('load_progress', {
                    'progress': progress,
                    'file': file.filename
                })
                logger.info(f"Emitted progress: {progress}%")
            
            # Convert Path objects to strings for subprocess
            # Only pass the two required arguments: input file and output file
            cmd = [
                str(Config.C_EXECUTABLE_PATH), 
                str(input_path), 
                str(output_path)
            ]
            logger.info(f"Running command: {' '.join(cmd)}")
            
            # Run the C executable
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            # Log the process output
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
            else:
                logger.info(f"Processing successful for {file.filename}")
                results.append({
                    'filename': file.filename,
                    'success': True,
                    'output_file': f'output_{secure_filename(file.filename)}.csv'
                })
            
            # Clean up input file
            if os.path.exists(str(input_path)):
                os.remove(str(input_path))
                logger.info(f"Cleaned up input file: {input_path}")
            
            processed_files += 1
            
            # Emit progress update
            if hasattr(current_app, 'socketio'):
                progress = int((processed_files / total_files) * 100)
                current_app.socketio.emit('load_progress', {
                    'progress': progress,
                    'file': file.filename
                })
                logger.info(f"Emitted progress: {progress}%")
            
        except Exception as e:
            logger.error(f"Exception processing {file.filename}: {str(e)}")
            logger.error(traceback.format_exc())
            results.append({
                'filename': file.filename,
                'success': False,
                'error': str(e)
            })
    
    # Clean up mapping file
    if os.path.exists(str(mapping_path)):
        os.remove(str(mapping_path))
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
    
    return jsonify(response_data)
