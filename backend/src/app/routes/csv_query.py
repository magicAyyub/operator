from fastapi import APIRouter, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from typing import Optional, List
import duckdb
import pandas as pd
import os
import shutil
from io import StringIO
from datetime import datetime, timedelta
import time
import logging
import traceback
import sys
import colorlog
import warnings

# Silence pandas warnings
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")

# Configure logging with colors and ensure absolute paths for log files
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'logs'))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'csv_query.log')

# Create a custom formatter with colors
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s [%(levelname)s] %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
))

# Create a file handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

# Configure the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.addHandler(file_handler)

# Silence the noisy python_multipart.multipart debug logs
logging.getLogger("python_multipart.multipart").setLevel(logging.WARNING)

# Log startup information
logger.info("=" * 80)
logger.info("CSV QUERY MODULE STARTING")
logger.info(f"Log file: {LOG_FILE}")
logger.info("=" * 80)

router = APIRouter(
    prefix="/api",
    tags=["csv_query"],
    responses={404: {"description": "Not found"}}
)

CSV_FILE_PATH = "src/data/input.csv"

def inspect_csv_structure():
    """Inspect and log the CSV structure once to help with debugging"""
    if not os.path.exists(CSV_FILE_PATH):
        logger.warning(f"CSV file not found: {CSV_FILE_PATH}")
        return False
    
    try:
        # Read just the header to get column names
        df = pd.read_csv(CSV_FILE_PATH, nrows=1)
        
        # Log critical information for debugging
        logger.info("-" * 50)
        logger.info(f"CSV FILE INSPECTION: {CSV_FILE_PATH}")
        logger.info(f"File size: {os.path.getsize(CSV_FILE_PATH) / 1024:.2f} KB")
        logger.info(f"Columns ({len(df.columns)}): {', '.join(df.columns)}")
        
        # Check for special characters in column names that might cause SQL issues
        problematic_columns = [col for col in df.columns if any(c in col for c in '"\',.()[]{}+-*/=<>!@#$%^&*')]
        if problematic_columns:
            logger.warning(f"Columns with special characters that need quoting: {', '.join(problematic_columns)}")
        
        logger.info("-" * 50)
        return True
    except Exception as e:
        logger.error(f"Error inspecting CSV structure: {str(e)}")
        return False

@router.get("/csv/stats")
def get_stats(type: str = Query("operators", enum=["operators", "status", "2fa"])):
    """Get statistics based on the specified type"""
    logger.info(f"🔍 Getting stats for type: {type}")
    
    if not os.path.exists(CSV_FILE_PATH):
        logger.warning("CSV file not found, returning empty data")
        return {"data": [], "message": "no_data"}
    
    try:
        # Inspect CSV structure if needed
        inspect_csv_structure()
        
        # Connect to DuckDB
        conn = duckdb.connect(":memory:")
        
        # Build the appropriate query based on the type
        if type == 'operators':
            query = f"""
                SELECT "Operateur" as name, COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM '{CSV_FILE_PATH}'), 2) as value
                FROM '{CSV_FILE_PATH}'
                WHERE "Operateur" IS NOT NULL
                GROUP BY "Operateur"
                ORDER BY count DESC
                LIMIT 5
            """
        elif type == 'status':
            query = f"""
                SELECT "USER_STATUS" as name, COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM '{CSV_FILE_PATH}'), 2) as value
                FROM '{CSV_FILE_PATH}'
                WHERE "USER_STATUS" IS NOT NULL
                GROUP BY "USER_STATUS"
                ORDER BY count DESC
            """
        elif type == '2fa':
            query = f"""
                SELECT "2FA_STATUS" as name, COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM '{CSV_FILE_PATH}'), 2) as value
                FROM '{CSV_FILE_PATH}'
                WHERE "2FA_STATUS" IS NOT NULL
                GROUP BY "2FA_STATUS"
                ORDER BY count DESC
            """
        else:
            logger.warning(f"Invalid stats type requested: {type}")
            return []
        
        # Log the query for debugging
        logger.info(f"Executing query for {type} stats")
        
        try:
            # Execute the query
            result = conn.execute(query).fetchall()
            logger.info(f"✅ Stats query returned {len(result)} rows")
            
            # Transform the results
            data = []
            for row in result:
                data.append({
                    "name": row[0] or "Non défini",
                    "value": row[2]
                })
            
            # Close the connection
            conn.close()
            
            return data
        except Exception as e:
            logger.error(f"❌ Error executing stats query: {str(e)}")
            logger.error(f"Query that failed: {query}")
            traceback.print_exc()
            return {"data": [], "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_stats: {str(e)}")
        traceback.print_exc()
        return {"data": [], "error": str(e)}

@router.get("/csv/filter-options")
def get_filter_options():
    """Get filter options for the UI"""
    logger.info("🔍 Getting filter options")
    
    if not os.path.exists(CSV_FILE_PATH):
        logger.warning("CSV file not found, returning empty options")
        return {
            "statuts": [],
            "fa_statuts": [],
            "annees": [],
            "message": "no_data"
        }
    
    try:
        # Connect to DuckDB
        conn = duckdb.connect(":memory:")
        
        # Define queries for each filter option
        statuts_query = f"""
            SELECT DISTINCT "USER_STATUS" as statut
            FROM '{CSV_FILE_PATH}'
            WHERE "USER_STATUS" IS NOT NULL
            ORDER BY "USER_STATUS"
        """
        
        fa_statuts_query = f"""
            SELECT DISTINCT "2FA_STATUS" as fa_statut
            FROM '{CSV_FILE_PATH}'
            WHERE "2FA_STATUS" IS NOT NULL
            ORDER BY "2FA_STATUS"
        """
        
        annees_query = f"""
            SELECT DISTINCT EXTRACT(YEAR FROM "CREATED_DATE")::VARCHAR as annee
            FROM '{CSV_FILE_PATH}'
            WHERE "CREATED_DATE" IS NOT NULL
            ORDER BY annee
        """
        
        # Execute queries and handle potential errors for each
        try:
            statuts = [row[0] for row in conn.execute(statuts_query).fetchall()]
            logger.info(f"Found {len(statuts)} distinct user statuses")
        except Exception as e:
            logger.error(f"❌ Error getting user statuses: {str(e)}")
            statuts = []
        
        try:
            fa_statuts = [row[0] for row in conn.execute(fa_statuts_query).fetchall()]
            logger.info(f"Found {len(fa_statuts)} distinct 2FA statuses")
        except Exception as e:
            logger.error(f"❌ Error getting 2FA statuses: {str(e)}")
            fa_statuts = []
        
        try:
            annees = [row[0] for row in conn.execute(annees_query).fetchall()]
            logger.info(f"Found {len(annees)} distinct years")
        except Exception as e:
            logger.error(f"❌ Error getting years: {str(e)}")
            annees = []
        
        # Close the connection
        conn.close()
        
        logger.info(f"✅ Filter options retrieved successfully")
        
        return {
            "statuts": statuts,
            "fa_statuts": fa_statuts,
            "annees": annees
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_filter_options: {str(e)}")
        traceback.print_exc()
        return {
            "statuts": [],
            "fa_statuts": [],
            "annees": [],
            "error": str(e)
        }

@router.get("/csv/data")
def get_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    statut: Optional[str] = None,
    fa_statut: Optional[str] = None,
    limite_type: Optional[str] = None,
    limite_valeur: Optional[float] = None,
    filtre_global: Optional[bool] = False,
    date_min: Optional[str] = None,
    date_max: Optional[str] = None,
    annee: Optional[str] = None
):
    """Get filtered data with pagination"""
    logger.info(f"🔍 Getting data: page={page}, filters applied: {bool(statut or fa_statut or date_min or date_max or annee)}")
    
    if not os.path.exists(CSV_FILE_PATH):
        logger.warning("CSV file not found, returning empty data")
        return {
            "data": [],
            "total_pages": 0,
            "total_count": 0,
            "message": "no_data"
        }
    
    try:
        # Connect to DuckDB
        conn = duckdb.connect(":memory:")
        
        # Get total count
        try:
            total_count_query = f"SELECT COUNT(*) as total FROM '{CSV_FILE_PATH}'"
            total_count = conn.execute(total_count_query).fetchone()[0]
            logger.info(f"Total records in CSV: {total_count}")
        except Exception as e:
            logger.error(f"❌ Error getting total count: {str(e)}")
            total_count = 0
        
        # Get operator counts
        try:
            operator_count_query = f"""
                SELECT "Operateur" as operateur, COUNT(*) as count
                FROM '{CSV_FILE_PATH}'
                GROUP BY "Operateur"
            """
            operator_counts = {row[0]: row[1] for row in conn.execute(operator_count_query).fetchall()}
            logger.info(f"Found data for {len(operator_counts)} operators")
        except Exception as e:
            logger.error(f"❌ Error getting operator counts: {str(e)}")
            operator_counts = {}
        
        # Calculate global percentages
        global_percentages = {}
        for operateur, count in operator_counts.items():
            global_percentages[operateur] = round((count / total_count * 100), 2) if total_count > 0 else 0
        
        # Build filter conditions
        conditions = []
        
        if statut and statut != 'all':
            conditions.append(f"\"USER_STATUS\" = '{statut}'")
        
        if fa_statut and fa_statut != 'all':
            conditions.append(f"\"2FA_STATUS\" = '{fa_statut}'")
        
        if date_min:
            conditions.append(f"\"CREATED_DATE\" >= '{date_min}'")
        
        if date_max:
            date_max_obj = datetime.strptime(date_max, "%Y-%m-%d")
            date_max_plus_one = (date_max_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            conditions.append(f"\"CREATED_DATE\" < '{date_max_plus_one}'")
        
        if annee and annee != 'all':
            conditions.append(f"EXTRACT(YEAR FROM \"CREATED_DATE\") = {annee}")
        
        # Build and execute filtered query
        base_query = f"SELECT * FROM '{CSV_FILE_PATH}'"
        filtered_query = base_query
        if conditions:
            filtered_query += " WHERE " + " AND ".join(conditions)
            logger.info(f"Applied filters: {' AND '.join(conditions)}")
        
        # Get filtered operator counts
        try:
            filtered_operator_query = f"""
                SELECT "Operateur" as operateur, COUNT(*) as count
                FROM ({filtered_query}) as filtered_data
                GROUP BY "Operateur"
            """
            filtered_operator_counts = {row[0]: row[1] for row in conn.execute(filtered_operator_query).fetchall()}
            logger.info(f"Found {len(filtered_operator_counts)} operators after filtering")
        except Exception as e:
            logger.error(f"❌ Error getting filtered operator counts: {str(e)}")
            filtered_operator_counts = {}
        
        # Get filtered total
        try:
            filtered_count_query = f"SELECT COUNT(*) as total FROM ({filtered_query}) as filtered_data"
            filtered_total = conn.execute(filtered_count_query).fetchone()[0]
            logger.info(f"Total records after filtering: {filtered_total}")
        except Exception as e:
            logger.error(f"❌ Error getting filtered total: {str(e)}")
            filtered_total = 0
        
        # Prepare data for all operators
        all_operators_data = []
        
        for operateur, filtered_count in filtered_operator_counts.items():
            global_percentage = global_percentages.get(operateur, 0)
            filtered_percentage = round((filtered_count / filtered_total * 100), 2) if filtered_total > 0 else 0
            
            all_operators_data.append({
                "id": operateur,
                "operateur": operateur,
                "nombre_in": filtered_count,
                "pourcentage_in": global_percentage,
                "pourcentage_filtre": filtered_percentage,
            })
        
        # Apply limit filter if needed
        if limite_type and limite_type != 'none' and limite_valeur is not None:
            filtered_data = []
            for item in all_operators_data:
                percentage_to_check = item["pourcentage_in"] if filtre_global else item["pourcentage_filtre"]
                
                if limite_type == 'lt' and percentage_to_check < float(limite_valeur):
                    filtered_data.append(item)
                elif limite_type == 'gt' and percentage_to_check > float(limite_valeur):
                    filtered_data.append(item)
            
            all_operators_data = filtered_data
            logger.info(f"Applied limit filter: {limite_type} {limite_valeur}, remaining operators: {len(all_operators_data)}")
        
        # Sort and paginate
        all_operators_data.sort(key=lambda x: x["nombre_in"], reverse=True)
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_data = all_operators_data[start_idx:end_idx]
        
        total_pages = (len(all_operators_data) + page_size - 1) // page_size if all_operators_data else 0
        
        # Close the connection
        conn.close()
        
        logger.info(f"✅ Returning page {page} of {total_pages} with {len(paginated_data)} items")
        
        return {
            "data": paginated_data,
            "total_pages": total_pages,
            "total_count": len(all_operators_data),
            "is_filtered": len(conditions) > 0 or (limite_type and limite_type != 'none' and limite_valeur is not None)
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_data: {str(e)}")
        traceback.print_exc()
        return {
            "data": [],
            "total_pages": 0,
            "total_count": 0,
            "error": str(e)
        }

@router.get("/csv/head")
def get_head(n: int = 5):
    """Get the first n rows of the CSV file"""
    logger.info(f"🔍 Getting first {n} rows")
    
    if not os.path.exists(CSV_FILE_PATH):
        logger.warning("CSV file not found, returning empty data")
        return {"data": [], "message": "no_data"}
    
    try:
        # Execute query
        query = f"SELECT * FROM '{CSV_FILE_PATH}' LIMIT {n}"
        
        try:
            df = duckdb.query(query).to_df()
            logger.info(f"✅ Retrieved {len(df)} rows")
            return df.to_dict(orient="records")
        except Exception as e:
            logger.error(f"❌ Error executing head query: {str(e)}")
            return {"data": [], "error": str(e)}
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_head: {str(e)}")
        traceback.print_exc()
        return {"data": [], "error": str(e)}

@router.post("/csv/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file"""
    logger.info(f"📤 Uploading file: {file.filename}")
    
    try:
        # Validate file format
        if not file.filename.endswith('.csv'):
            logger.warning(f"Invalid file format: {file.filename}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Le fichier doit être au format CSV"}
            )
        
        # Create directory if needed
        os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
        
        # Save file
        with open(CSV_FILE_PATH, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(CSV_FILE_PATH)
        logger.info(f"✅ File saved successfully: {CSV_FILE_PATH} ({file_size / 1024:.2f} KB)")
        
        # Inspect the uploaded file
        inspect_csv_structure()
        
        return {"success": True, "message": "Fichier CSV importé avec succès"}
    except Exception as e:
        logger.error(f"❌ Error uploading CSV: {str(e)}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur lors de l'importation: {str(e)}"}
        )

@router.get("/csv/check")
def check_file():
    """Check if the CSV file exists"""
    logger.info("🔍 Checking if CSV file exists")
    exists = os.path.exists(CSV_FILE_PATH)
    
    if exists:
        file_size = os.path.getsize(CSV_FILE_PATH)
        logger.info(f"✅ CSV file exists: {CSV_FILE_PATH} ({file_size / 1024:.2f} KB)")
    else:
        logger.info("❌ CSV file does not exist")
    
    return {"exists": exists}

@router.delete("/csv/purge")
def purge_data():
    """Delete the CSV file"""
    logger.info("🗑️ Purging CSV data")
    
    try:
        if os.path.exists(CSV_FILE_PATH):
            file_size = os.path.getsize(CSV_FILE_PATH)
            logger.info(f"Deleting CSV file: {CSV_FILE_PATH} ({file_size / 1024:.2f} KB)")
            os.remove(CSV_FILE_PATH)
            logger.info("✅ CSV file deleted successfully")
            return {"success": True, "message": "Données purgées avec succès"}
        else:
            logger.info("No CSV file to purge")
            return {"success": True, "message": "Aucun fichier à purger"}
    except Exception as e:
        logger.error(f"❌ Error purging data: {str(e)}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur lors de la purge des données: {str(e)}"}
        )

# Log module loaded
logger.info("=" * 80)
logger.info("CSV QUERY MODULE LOADED SUCCESSFULLY")
logger.info("=" * 80)
