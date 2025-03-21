import pandas as pd
import datetime
import math
import chardet

def clean_sql_results(results):
    cleaned = []
    for row in results:
        clean_row = {}
        for key, value in row.items():
            if hasattr(value, 'item'):
                value = value.item()
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                value = None
            clean_row[key] = value
        cleaned.append(clean_row)
    return cleaned

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    return chardet.detect(raw_data)['encoding']

def clean_datetime(value):
    """
    Nettoie et valide les valeurs de date.
    Gère les cas spéciaux comme les dates avec mois ou jours à 0.
    """
    if pd.isna(value) or value is None:
        return None
        
    try:
        # Si c'est déjà un objet datetime ou Timestamp
        if isinstance(value, (pd.Timestamp, datetime.datetime)):
            if value.year < 1900:  # Gérer les dates trop anciennes
                return None
            return value.strftime('%Y-%m-%d %H:%M:%S')
            
        # Si c'est une chaîne de caractères
        elif isinstance(value, str):
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
                
        return None
    except:
        return None