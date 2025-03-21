import os
from flask import Blueprint, request, jsonify, Response
import json
import pandas as pd
import numpy as np
import re
from typing import Union
from sqlalchemy import text
from app.utils.helpers import clean_sql_results, detect_encoding, clean_datetime
from app import engine
from app import socketio
from app.config import Config
import logging
import traceback
import tempfile
import csv
import pymysql
from sqlalchemy.engine.url import make_url
import subprocess

# Set up logging
logger = logging.getLogger(__name__)

db_bp = Blueprint('database', __name__)

@db_bp.route('/api/search', methods=['POST'])
def search() -> Union[Response, Exception]:
    """ Search for records in the database based on the provided form data """
    form_data = request.json
    page = form_data.get("page", 1)
    limit = form_data.get("limit", 100)
    table_name = form_data.get("table", "data")
 
    with open('utils/db_search_columns.json') as json_file:
        db_columns = json.load(json_file)
    query_conditions = []
    like_checkbox = form_data.get("like", False)
    regex_pattern = form_data.get("regex")
    if 'regex' in form_data:
        del form_data['regex']
    if 'like' in form_data:
        del form_data['like']
    for key, value in form_data.items():
        if value:
            db_column = db_columns.get(key)
            if db_column:
                if like_checkbox or like_checkbox == "1":
                    query_conditions.append(f"{db_column} LIKE '%%{value}%%'")
                else:
                    query_conditions.append(f"{db_column} = '{value}'")
    if regex_pattern:
        try:
            re.compile(regex_pattern)
            mysql_compatible_pattern = regex_pattern.replace("%", "%%").replace("\\\\", "\\")
            query_conditions.append(f"EMAIL REGEXP '{mysql_compatible_pattern}'")
        except re.error:
            return jsonify({'error': 'Invalid regex pattern'}), 400
    if not query_conditions:
        return jsonify({'error': 'Au moins un champ de recherche doit être rempli.'}), 400
    where_clause = " AND ".join(query_conditions)
    offset = (page - 1) * limit
 
    # Query to get the total count of matching results
    count_query = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
    total_count = pd.read_sql(count_query, engine).iloc[0, 0]
 
    # Query to get the paginated results
    query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT {limit} OFFSET {offset}"

    if not re.match("^[a-zA-Z0-9_]+$", table_name):
        return jsonify({'error': 'Nom de table invalide'}), 400
    try:
        results_df = pd.read_sql(query, engine)
        results = results_df.to_dict(orient='records')
        cleaned_results = clean_sql_results(results)
        return jsonify({
            'results': cleaned_results,
            'page': page,
            'limit': limit,
            'total_count': int(total_count)  # Convert to standard Python int
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

def get_db_connection_params():
    """Extract database connection parameters from SQLAlchemy engine"""
    url = make_url(str(engine.url))
    return {
        'host': url.host,
        'user': url.username,
        'password': url.password,
        'database': url.database,
        'port': url.port or 3306
    }


@db_bp.route('/api/load_data', methods=['POST'])
def load_data():
    """ Load processed CSV data into a MySQL table using faster bulk loading methods """
    logger.info("Load data endpoint called")
    
    table_name = request.form.get('table_name', 'phone_data')
    if not table_name:
        return jsonify({'error': 'Table name is required'}), 400
    
    csv_path = os.path.join(Config.UPLOAD_FOLDER, Config.PROCESSED_CSV)
    if not os.path.exists(csv_path):
        return jsonify({'error': 'CSV traité introuvable'}), 404

    try:
        # Detect encoding and read CSV headers
        encoding = detect_encoding(csv_path)
        df_headers = pd.read_csv(csv_path, nrows=0, encoding=encoding)
        columns = df_headers.columns.tolist()
        
        # Create table if it doesn't exist
        logger.info("Creating table structure if needed")
        socketio.emit('load_progress', {'progress': 10, 'message': 'Création de la structure de table...'})
        
        with engine.connect() as connection:
            columns_def = []
            for col in columns:
                if col in ['ID_CCU', 'UUID']:
                    col_type = "VARCHAR(255)"
                elif col in ['BIRTH_DATE', 'CREATED_DATE', 'ARCHIVED_DATE', 'VERIFICATION_DATE',
                           'DATE_MODF_TEL', 'EXPIRATION', 'EMISSION']:
                    col_type = "DATETIME NULL"  # Explicitly allow NULL
                else:
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
        
        # Load data directly using pandas with proper NULL handling
        logger.info("Loading data using pandas with optimized settings")
        socketio.emit('load_progress', {'progress': 20, 'message': 'Chargement des données...'})
        
        # Read the CSV in chunks to avoid memory issues
        total_rows = sum(1 for _ in open(csv_path, encoding=encoding)) - 1  # Subtract 1 for header
        processed_rows = 0
        
        # Process in chunks of 1000 rows
        for chunk_idx, chunk in enumerate(pd.read_csv(csv_path, chunksize=1000, encoding=encoding, low_memory=False)):
            # Replace NaN values with None for SQL compatibility
            chunk = chunk.replace({pd.NA: None, np.nan: None})
            
            # Replace '\N' strings with None
            chunk = chunk.replace('\\N', None)
            
            # Process date columns
            date_columns = ['BIRTH_DATE', 'CREATED_DATE', 'ARCHIVED_DATE', 'VERIFICATION_DATE',
                          'DATE_MODF_TEL', 'EXPIRATION', 'EMISSION']
            
            for col in date_columns:
                if col in chunk.columns:
                    # Convert to datetime and handle NaT values
                    chunk[col] = pd.to_datetime(chunk[col], errors='coerce')
                    # Convert NaT to None
                    chunk[col] = chunk[col].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(x) else None)
            
            # Convert ID columns to strings
            for col in ['ID_CCU', 'UUID']:
                if col in chunk.columns:
                    chunk[col] = chunk[col].astype(str).replace('nan', None)
            
            # Insert into database
            try:
                chunk.to_sql(
                    name=table_name, 
                    con=engine, 
                    if_exists='append', 
                    index=False,
                    method='multi'  # Use multi-row insert for better performance
                )
            except Exception as e:
                logger.error(f"Error inserting chunk {chunk_idx}: {str(e)}")
                # Try inserting row by row as a last resort
                for _, row in chunk.iterrows():
                    try:
                        pd.DataFrame([row]).to_sql(
                            name=table_name,
                            con=engine,
                            if_exists='append',
                            index=False
                        )
                    except Exception as row_error:
                        logger.error(f"Error inserting row: {str(row_error)}")
                        # Continue with next row
            
            # Update progress
            processed_rows += len(chunk)
            progress = min(int((processed_rows / total_rows) * 80) + 20, 99)  # 20-99% progress
            socketio.emit('load_progress', {
                'progress': progress, 
                'message': f'Chargement: {processed_rows}/{total_rows} lignes'
            })
        
        # Get final row count
        with engine.connect() as connection:
            result = connection.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
            row_count = result.fetchone()[0]
        
        logger.info(f"Data loading complete. {row_count} rows in table.")
        socketio.emit('load_progress', {'progress': 100, 'message': 'Terminé!'})
        
        return jsonify({
            'success': True,
            'message': f'Données chargées avec succès dans la table {table_name}',
            'total_rows': row_count
        }), 200

    except Exception as e:
        logger.error(f"Error loading data to database: {str(e)}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            'error': str(e),
            'details': traceback.format_exc()
        }), 500
    
@db_bp.route('/api/tables', methods=['GET'])
def get_tables():
    """ Get a list of tables in the current database """
    try:
        query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query)
            tables = [row[0] for row in result]
        
        if not tables:
            # Au lieu de considérer cela comme une erreur, nous renvoyons un statut spécial
            return jsonify({
                'tables': [],
                'status': 'empty',
                'message': 'Aucune table trouvée. Veuillez d\'abord charger des données via la page d\'ajout.'
            })
            
        return jsonify({
            'tables': tables,
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500