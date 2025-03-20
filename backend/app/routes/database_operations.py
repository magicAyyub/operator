import os
from flask import Blueprint, request, jsonify, Response
import json
import pandas as pd
import re
from typing import Union
from sqlalchemy import text
from app.utils.helpers import clean_sql_results, detect_encoding, clean_datetime
from app import engine
from app import socketio
from app.config import Config

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
    

@db_bp.route('/api/load_data', methods=['POST'])
def load_data():
    """ Load processed CSV data into a MySQL table """
    table_name = request.form.get('table_name')
    if not table_name:
        return jsonify({'error': 'Table name is required'}), 400
    
    csv_path = os.path.join(Config.UPLOAD_FOLDER, Config.PROCESSED_CSV)
    if not os.path.exists(csv_path):
        return jsonify({'error': 'CSV traité introuvable'}), 404

    try:
        encoding = detect_encoding(csv_path)
        df_headers = pd.read_csv(csv_path, nrows=0, encoding=encoding)
        columns = df_headers.columns.tolist()

        with engine.connect() as connection:
            columns_def = []
            for col in columns:
                if col in ['ID_CCU', 'UUID']:
                    col_type = "VARCHAR(255)"
                elif col in ['BIRTH_DATE', 'CREATED_DATE', 'ARCHIVED_DATE', 'VERIFICATION_DATE',
                           'DATE_MODF_TEL', 'EXPIRATION', 'EMISSION']:
                    col_type = "DATETIME"
                else:
                    col_type = "VARCHAR(255)"
                columns_def.append(f"`{col}` {col_type}")
            
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                {', '.join(columns_def)}
            )
            """
            connection.execute(text(create_table_query))

        total_rows = sum(1 for _ in open(csv_path, encoding=encoding)) - 1  # Subtract 1 for header
        processed_rows = 0

        for chunk in pd.read_csv(csv_path, chunksize=1000, encoding=encoding, low_memory=False):
            chunk = chunk.replace({pd.NA: None, np.nan: None})
            
            date_columns = ['BIRTH_DATE', 'CREATED_DATE', 'ARCHIVED_DATE', 'VERIFICATION_DATE',
                          'DATE_MODF_TEL', 'EXPIRATION', 'EMISSION']

            for col in date_columns:
                            if col in chunk.columns:
                                chunk[col] = pd.to_datetime(chunk[col], errors='coerce')
                                chunk[col] = chunk[col].apply(clean_datetime)

            for col in ['ID_CCU', 'UUID']:
                if col in chunk.columns:
                    chunk[col] = chunk[col].astype(str)

            chunk.to_sql(
                name=table_name, 
                con=engine, 
                if_exists='append', 
                index=False,
                method='multi'
            )
            
            processed_rows += len(chunk)
            progress = int((processed_rows / total_rows) * 100)
            socketio.emit('load_progress', {'progress': progress})

        return jsonify({
            'success': True,
            'message': f'Données chargées avec succès dans la table {table_name}',
            'total_rows': total_rows
        }), 200

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return jsonify({
            'error': str(e),
            'details': error_details
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