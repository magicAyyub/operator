from flask import Blueprint, request, jsonify, send_file, Response, Request 
import os
import pandas as pd
from app.config import Config
from app import engine
from typing import Union

csv_bp = Blueprint('csv', __name__)

@csv_bp.route('/api/fill_csv', methods=['POST'])
def fill_csv() -> Union[Response, Exception]:
    """ Fill the CSV file with the data from the database """
    if 'csv_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file: Request = request.files['csv_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.endswith('.csv'):
        try:
            # Save search csv file
            file_path = os.path.join(Config.UPLOAD_FOLDER, file.filename)
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
            output_path = os.path.join(Config.UPLOAD_FOLDER, Config.PROCESSED_CSV)
            final_df.to_csv(output_path, index=False)
            os.remove(file_path)
 
            return send_file(output_path, as_attachment=True, download_name="filtered_results.csv")
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Format de fichier non valide'}), 400
    
@csv_bp.route('/api/download_csv', methods=['GET'])
def download_csv() -> Response:
    """ Download the processed CSV file """
    csv_path = os.path.join(Config.UPLOAD_FOLDER, Config.PROCESSED_CSV)
    print(csv_path)
    if os.path.exists(csv_path):
        return send_file(csv_path, as_attachment=True, download_name=Config.PROCESSED_CSV)
    return jsonify({'error': 'CSV traité introuvable'}), 404