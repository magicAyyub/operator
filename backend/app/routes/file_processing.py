from pathlib import Path
import os
from flask import Blueprint, request, jsonify, current_app
import subprocess
from werkzeug.utils import secure_filename
from app.config import Config
import time
import traceback
import logging
import pandas as pd
import numpy as np
from app import engine, socketio
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

file_bp = Blueprint('file_processing', __name__)

def join_operator_data(output_path, mapping_path):
    """
    Join operator data from the mapping file to the output CSV
    
    Args:
        output_path: Path to the output CSV file from the C executable
        mapping_path: Path to the MAJNUM.csv file with operator information
    
    Returns:
        Path to the processed file with operator information
    """
    try:
        logger.info(f"Joining operator data to {output_path} using {mapping_path}")
        
        # Read the output CSV
        df = pd.read_csv(output_path, low_memory=False)
        
        # Ensure TELEPHONE column exists
        if 'TELEPHONE' not in df.columns:
            logger.error(f"TELEPHONE column not found in {output_path}")
            return None
            
        df['TELEPHONE'] = df['TELEPHONE'].astype(str)
        df['TELEPHONE'] = df['TELEPHONE'].str.replace('+', '')
        df['TELEPHONE'] = df['TELEPHONE'].str.replace('.0', '')
        
        # Read the operator data
        operateur = pd.read_csv(
            mapping_path,
            encoding='ISO-8859-1',
            sep=';'
        )
        
        # Check if required columns exist in the mapping file
        required_columns = ["Tranche_Debut", "Tranche_Fin", "Date_Attribution", "EZABPQM", "Mnémo"]
        missing_columns = [col for col in required_columns if col not in operateur.columns]
        if missing_columns:
            logger.error(f"Missing columns in mapping file: {missing_columns}")
            return None
            
        df_operateur_fr = operateur.drop(columns=["Tranche_Debut", "Tranche_Fin", "Date_Attribution"])
        df_operateur_fr.rename(columns={"EZABPQM": "Prefixe"}, inplace=True)
        df_operateur_fr.rename(columns={"Mnémo": "Operateur"}, inplace=True)
        
        # Create a list of phone number prefixes
        liste_numeros_idrh = df["TELEPHONE"]
        liste_numeros_idrh = liste_numeros_idrh.astype(str)
        liste_numeros_idrh = [numero[:2] for numero in liste_numeros_idrh]
        
        # Filter French numbers (starting with "33")
        liste_numeros_fr_idrh = [code for code in liste_numeros_idrh if code == "33"]
        
        # Split into French and non-French numbers
        df_numeros_fr_idrh = df[df["TELEPHONE"].str[:2].isin(liste_numeros_fr_idrh)]
        df_numero_etrangers = df[~df["TELEPHONE"].str[:2].isin(liste_numeros_fr_idrh)]
        
        # Remove the country code from French numbers
        df_numeros_fr_idrh['TELEPHONE'] = df_numeros_fr_idrh['TELEPHONE'].str.replace(r'^33', '', regex=True)
        
        # Add length of phone numbers
        df_numeros_fr_idrh["Longueur_numero_telephone"] = df_numeros_fr_idrh["TELEPHONE"].str.len()
        df_operateur_fr['Prefixe'] = df_operateur_fr['Prefixe'].astype(str)
        
        # Split operators by prefix length
        df_operateur_fr_7 = df_operateur_fr[df_operateur_fr["Prefixe"].str.len() == 7]
        df_operateur_fr_6 = df_operateur_fr[df_operateur_fr["Prefixe"].str.len() == 6]
        df_operateur_fr_5 = df_operateur_fr[df_operateur_fr["Prefixe"].str.len() == 5]
        df_operateur_fr_4 = df_operateur_fr[df_operateur_fr["Prefixe"].str.len() == 4]
        df_operateur_fr_3 = df_operateur_fr[df_operateur_fr["Prefixe"].str.len() == 3]
        
        # Extract prefixes of different lengths
        df_numeros_fr_idrh['Prefixe_7'] = df_numeros_fr_idrh['TELEPHONE'].str[:7]
        df_numeros_fr_idrh['Prefixe_6'] = df_numeros_fr_idrh['TELEPHONE'].str[:6]
        df_numeros_fr_idrh['Prefixe_5'] = df_numeros_fr_idrh['TELEPHONE'].str[:5]
        df_numeros_fr_idrh['Prefixe_4'] = df_numeros_fr_idrh['TELEPHONE'].str[:4]
        df_numeros_fr_idrh['Prefixe_3'] = df_numeros_fr_idrh['TELEPHONE'].str[:3]
        
        # Match each prefix length
        result_idrh_7 = df_numeros_fr_idrh.merge(df_operateur_fr_7, left_on='Prefixe_7', right_on='Prefixe', how='inner')
        result_idrh_6 = df_numeros_fr_idrh.merge(df_operateur_fr_6, left_on='Prefixe_6', right_on='Prefixe', how='inner')
        result_idrh_5 = df_numeros_fr_idrh.merge(df_operateur_fr_5, left_on='Prefixe_5', right_on='Prefixe', how='inner')
        result_idrh_4 = df_numeros_fr_idrh.merge(df_operateur_fr_4, left_on='Prefixe_4', right_on='Prefixe', how='inner')
        result_idrh_3 = df_numeros_fr_idrh.merge(df_operateur_fr_3, left_on='Prefixe_3', right_on='Prefixe', how='inner')
        
        # Combine all results
        result_idrh = pd.concat([result_idrh_3, result_idrh_4, result_idrh_5], axis=0)
        
        # Add foreign numbers (without operator information)
        if not df_numero_etrangers.empty:
            # Add 'Operateur' column with 'Étranger' value for foreign numbers
            df_numero_etrangers['Operateur'] = 'Étranger'
            result_idrh = pd.concat([result_idrh, df_numero_etrangers], axis=0)
        
        # Keep only the original columns plus the Operateur column
        original_columns = df.columns.tolist()
        if 'Operateur' not in original_columns:
            columns_to_keep = original_columns + ['Operateur']
        else:
            columns_to_keep = original_columns
            
        # Filter to keep only necessary columns
        result_columns = [col for col in columns_to_keep if col in result_idrh.columns]
        result_idrh = result_idrh[result_columns]
        
        # Save the result
        processed_output_path = str(output_path).replace('.csv', '_with_operators.csv')
        result_idrh.to_csv(processed_output_path, index=False)
        
        logger.info(f"Operator data joined successfully, saved to {processed_output_path}")
        return processed_output_path
    
    except Exception as e:
        logger.error(f"Error joining operator data: {str(e)}")
        logger.error(traceback.format_exc())
        return None

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
    
    # Save mapping file - we'll use this for all data files
    mapping_path = Config.UPLOAD_FOLDER / secure_filename(mapping_file.filename)
    mapping_file.save(mapping_path)
    logger.info(f"Mapping file saved to {mapping_path}")
    
    # Emit initial status
    if hasattr(current_app, 'socketio'):
        current_app.socketio.emit('processing_status', {
            'status': 'Initialisation...',
        })
    
    results = []
    total_files = len(data_files)
    processed_files = 0
    
    # Create a combined output file for all processed data
    combined_output_path = Config.UPLOAD_FOLDER / 'combined_output.csv'
    combined_df = None
    
    # Process each data file
    for idx, file in enumerate(data_files, 1):
        try:
            # Update status with simple file count
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit('processing_status', {
                    'status': 'Traitement en cours',
                    'file': file.filename,
                    'fileIndex': idx,
                    'totalFiles': total_files
                })
            
            input_path = Config.UPLOAD_FOLDER / secure_filename(file.filename)
            output_path = Config.UPLOAD_FOLDER / f'output_{secure_filename(file.filename)}.csv'
            
            # Save the data file
            file.save(input_path)
            logger.info(f"Data file saved to {input_path}")
            
            # Convert Path objects to strings for subprocess
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
                
                # Join operator data to the output file
                processed_output_path = join_operator_data(output_path, mapping_path)
                
                if processed_output_path:
                    results.append({
                        'filename': file.filename,
                        'success': True,
                        'output_file': os.path.basename(processed_output_path)
                    })
                    
                    # Add to combined output
                    file_df = pd.read_csv(processed_output_path)
                    if combined_df is None:
                        combined_df = file_df
                    else:
                        combined_df = pd.concat([combined_df, file_df], ignore_index=True)
                    
                    # We keep the final CSV with operator data
                    # But delete the intermediate CSV
                    if os.path.exists(str(output_path)):
                        os.remove(str(output_path))
                        logger.info(f"Cleaned up intermediate CSV file: {output_path}")
                else:
                    results.append({
                        'filename': file.filename,
                        'success': False,
                        'error': "Failed to join operator data"
                    })
                    # Clean up the intermediate CSV if joining failed
                    if os.path.exists(str(output_path)):
                        os.remove(str(output_path))
                        logger.info(f"Cleaned up intermediate CSV file: {output_path}")
        
            # Clean up input file
            if os.path.exists(str(input_path)):
                os.remove(str(input_path))
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
    
    # Save the combined output if we have processed files
    if combined_df is not None:
        combined_df.to_csv(combined_output_path, index=False)
        logger.info(f"Combined output saved to {combined_output_path}")
        # Set this as the processed CSV for database loading
        Config.PROCESSED_CSV = 'combined_output.csv'
    
    # Final status update
    if hasattr(current_app, 'socketio'):
        current_app.socketio.emit('processing_status', {
            'status': 'Terminé',
        })
    
    # Clean up mapping file after all files are processed
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

@file_bp.route('/api/load_data', methods=['POST'])
def load_data_endpoint():
    """
    Load processed CSV files into the database
    This function is compatible with the existing database loading code
    """
    logger.info("Load data endpoint called")
    
    table_name = request.form.get('table_name', 'phone_data')
    if not table_name:
        return jsonify({'error': 'Table name is required'}), 400
    
    # Use the combined CSV file that was created during processing
    csv_path = os.path.join(Config.UPLOAD_FOLDER, Config.PROCESSED_CSV)
    if not os.path.exists(csv_path):
        return jsonify({'error': 'CSV traité introuvable'}), 404

    try:
        # Use the detect_encoding function from app.utils.helpers if available
        try:
            from app.utils.helpers import detect_encoding, clean_datetime
            encoding = detect_encoding(csv_path)
        except ImportError:
            encoding = 'utf-8'  # Default to UTF-8 if helper function not available
            
            # Define a simple clean_datetime function if not available
            def clean_datetime(dt):
                if pd.isna(dt):
                    return None
                return dt
        
        # Read CSV headers to get column names
        df_headers = pd.read_csv(csv_path, nrows=0, encoding=encoding)
        columns = df_headers.columns.tolist()

        # Create table if it doesn't exist
        with engine.connect() as connection:
            columns_def = []
            for col in columns:
                # Use VARCHAR for all columns since we're dealing with phone data
                col_type = "VARCHAR(255)"
                columns_def.append(f"`{col}` {col_type}")
            
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                {', '.join(columns_def)},
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            connection.execute(text(create_table_query))

        # Count total rows for progress tracking
        total_rows = sum(1 for _ in open(csv_path, encoding=encoding)) - 1  # Subtract 1 for header
        processed_rows = 0

        # Process in chunks to avoid memory issues
        for chunk in pd.read_csv(csv_path, chunksize=1000, encoding=encoding, low_memory=False):
            # Replace NaN values with None for SQL compatibility
            chunk = chunk.replace({pd.NA: None, np.nan: None})
            
            # Convert all columns to string for consistency
            for col in chunk.columns:
                chunk[col] = chunk[col].astype(str)

            # Insert into database
            chunk.to_sql(
                name=table_name, 
                con=engine, 
                if_exists='append', 
                index=False,
                method='multi'
            )
            
            # Update progress
            processed_rows += len(chunk)
            progress = int((processed_rows / total_rows) * 100)
            socketio.emit('load_progress', {'progress': progress})

        return jsonify({
            'success': True,
            'message': f'Données chargées avec succès dans la table {table_name}',
            'total_rows': total_rows
        }), 200

    except Exception as e:
        logger.error(f"Error loading data to database: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'error': str(e),
            'details': traceback.format_exc()
        }), 500