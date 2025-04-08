import datetime
import pandas as pd
import traceback
import logging
import chardet
# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    return chardet.detect(raw_data)['encoding']