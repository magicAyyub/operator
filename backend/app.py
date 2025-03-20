import os
import re
import json
import pandas as pd
import numpy as np
import math
import subprocess
import datetime
import chardet
from flask import Flask, request, render_template, send_file, jsonify, Response
from flask_cors import CORS
from sqlalchemy import create_engine, text
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit
from typing import Union

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

engine = create_engine("mysql://user:password@localhost:3306/db")
UPLOAD_FOLDER = "./tmp"
PROCESSED_CSV = "processed_data.csv"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def clear_tmp_folder(tmp_folder: str) -> None:
    for filename in os.listdir(tmp_folder):
        file_path = os.path.join(tmp_folder, filename)
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)

def clean_sql_results(results):
    cleaned = []
    for row in results:
        clean_row = {}
        for key, value in row.items():
            # Convertir les valeurs numpy.int64 et numpy.float64 en types Python natifs
            if hasattr(value, 'item'):
                value = value.item()
            # Gérer les NaN et les valeurs infinies
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                value = None
            clean_row[key] = value
        cleaned.append(clean_row)
    return cleaned


def clean_datetime(value):
    """
    Nettoie et valide les valeurs de date.
    Gère les cas spéciaux comme les dates avec mois ou jours à 0.
    """
    if pd.isna(value) or value is None:
        return None
        
    try:
        # Si c'est une chaîne de caractères
        if isinstance(value, str):
            # Retirer le timezone s'il est présent
            if '+' in value:
                value = value.split('+')[0].strip()
            elif '-' in value and value.count('-') > 2:
                value = value.rsplit('-', 1)[0].strip()
            
            # Gérer les cas où le mois ou le jour sont à 0
            if '-00-' in value or value.endswith('-00'):
                parts = value.split('-')
                year = parts[0]
                month = '01' if parts[1] == '00' else parts[1]
                day = '01' if len(parts) > 2 and parts[2] == '00' else parts[2]
                value = f"{year}-{month}-{day}"
                
            # Vérifier si la date est valide
            try:
                parsed_date = pd.to_datetime(value)
                if parsed_date.year < 1900:  # Gérer les dates trop anciennes
                    return None
                return parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                return None
                
        # Si c'est déjà un objet datetime
        elif isinstance(value, (pd.Timestamp, datetime.datetime)):
            if value.year < 1900:  # Gérer les dates trop anciennes
                return None
            return value.strftime('%Y-%m-%d %H:%M:%S')
            
        return None
    except:
        return None

@app.route("/", methods=["GET"])
def index() -> str:
    clear_tmp_folder(UPLOAD_FOLDER)
    return jsonify({'access':True}), 500

# CSV search
@app.route('/api/fill_csv', methods=['POST'])
def fill_csv() -> Union[Response, Exception]:
    if 'csv_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.endswith('.csv'):
        try:
            # Save search csv file
            file_path = os.path.join("./tmp", file.filename)
            file.save(file_path)
 
            # extract data search
            input_df = pd.read_csv(file_path)
            column_names = input_df.columns.tolist()
            union_queries = []
 
            for _, row in input_df.iterrows():
                conditions = [f"{col} = '{row[col]}'" for col in column_names]
                where_clause = " AND ".join(conditions)
                union_queries.append(f"SELECT * FROM data WHERE {where_clause}")
 
            full_query = " UNION ALL ".join(union_queries)
            final_df = pd.read_sql(full_query, engine)
            final_df = final_df.drop_duplicates(subset=[
             'EMAIL', 'BIRTH_DATE', 'ID_CCU'])
            output_path = "./tmp/filtered_results.csv"
            final_df.to_csv(output_path, index=False)
            os.remove(file_path)
 
            return send_file(output_path, as_attachment=True, download_name="filled_data.csv")
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Format de fichier non valide'}), 400
        

# Simple search
@app.route('/api/search', methods=['POST'])
def search() -> Union[Response, Exception]:
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
        

@app.route('/api/process_file', methods=['POST'])
def process_file_endpoint():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file.filename.endswith('.txt'):
        return jsonify({'error': 'Invalid file format'}), 400

    input_path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    output_path = os.path.join(UPLOAD_FOLDER, PROCESSED_CSV)
    
    try:
        file.save(input_path)
        # Run the C executable directly
        subprocess.run(['./utils/data_processor.exe', input_path, output_path], check=True)
        os.remove(input_path)  # Clean up input file
        return jsonify({'message': 'Success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

 
@app.route('/api/download_csv', methods=['GET'])
def download_csv() -> Response:
    csv_path = os.path.join(UPLOAD_FOLDER, PROCESSED_CSV)
    print(csv_path)
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name=PROCESSED_CSV)
    return jsonify({'error': 'CSV traité introuvable'}), 404

@app.route('/api/tables', methods=['GET'])
def get_tables():
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

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    return chardet.detect(raw_data)['encoding']

@app.route('/api/load_data', methods=['POST'])
def load_data():
    table_name = request.form.get('table_name')
    if not table_name:
        return jsonify({'error': 'Table name is required'}), 400
    
    csv_path = os.path.join(UPLOAD_FOLDER, PROCESSED_CSV)
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

if __name__ == '__main__':
    print("Démarrage de l'application Flask...")
    socketio.run(app, debug=True)