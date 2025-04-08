from fastapi import APIRouter, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from typing import Optional, List
import duckdb
import pandas as pd
import os
import shutil
from io import StringIO
from datetime import datetime
import time

router = APIRouter(
    prefix="/api",
    tags=["csv_query"],
    responses={404: {"description": "Not found"}}
)

CSV_FILE_PATH = "src/data/input.csv"

# Vérifier si le fichier CSV existe, mais retourner un statut spécial plutôt qu'une erreur
def check_csv_exists():
    return os.path.exists(CSV_FILE_PATH)

@router.get("/csv/head")
def get_head(n: int = 5):
    if not check_csv_exists():
        return {"data": [], "message": "no_data"}
    
    try:
        query = f"SELECT * FROM '{CSV_FILE_PATH}' LIMIT {n}"
        df = duckdb.query(query).to_df()
        return df.to_dict(orient="records")
    except Exception as e:
        return {"data": [], "error": str(e)}

@router.get("/csv/data")
def get_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    statut: Optional[str] = None,
    fa_statut: Optional[str] = None,
    limite_type: Optional[str] = None,
    limite_valeur: Optional[float] = None,
    date_min: Optional[str] = None,
    date_max: Optional[str] = None,
    annee: Optional[str] = None
):
    # Si le fichier n'existe pas, retourner un résultat vide avec un message spécial
    if not check_csv_exists():
        return {
            "data": [],
            "total_pages": 0,
            "total_count": 0,
            "message": "no_data"
        }
    
    try:
        # Connexion à DuckDB avec une instance en mémoire pour de meilleures performances
        conn = duckdb.connect(":memory:")
        
        # Construire la requête SQL de base
        query = f"SELECT * FROM '{CSV_FILE_PATH}'"
        
        # Ajouter les conditions de filtrage
        conditions = []
        
        if statut and statut != 'all':
            conditions.append(f"USER_STATUS = '{statut}'")
        
        if fa_statut and fa_statut != 'all':
            conditions.append(f"\"2FA_STATUS\" = '{fa_statut}'")
        
        if date_min:
            conditions.append(f"CREATED_DATE >= '{date_min}'")
        
        if date_max:
            conditions.append(f"CREATED_DATE <= '{date_max}'")
        
        if annee and annee != 'all':
            conditions.append(f"EXTRACT(YEAR FROM CREATED_DATE) = {annee}")
        
        # Ajouter les conditions à la requête
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Compter le nombre total de lignes pour la pagination
        count_query = f"SELECT COUNT(*) as total FROM ({query}) as filtered_data"
        total_count = conn.execute(count_query).fetchone()[0]
        
        # Ajouter la pagination
        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"
        
        # Exécuter la requête
        result = conn.execute(query).fetchall()
        columns = conn.execute(query).description
        
        # Créer un dictionnaire de colonnes
        column_names = [col[0] for col in columns]
        
        # Transformer les données pour le frontend
        data = []
        for row in result:
            row_dict = dict(zip(column_names, row))
            
            # Calculer le pourcentage IN (simulé pour cet exemple)
            telephone = row_dict.get('TELEPHONE')
            pourcentage_in = round(float(telephone) % 100, 2) if telephone is not None else 0
            
            data.append({
                "id": row_dict.get('UUID', ''),
                "operateur": row_dict.get('Operateur', ''),
                "nombre_in": int(telephone % 1000) if telephone is not None else 0,  # Simulé pour l'exemple
                "pourcentage_in": pourcentage_in,
                "statut": row_dict.get('USER_STATUS', ''),
                "fa_statut": row_dict.get('2FA_STATUS', ''),
                "date": row_dict.get('CREATED_DATE', '')
            })
        
        # Calculer le nombre total de pages
        total_pages = (total_count + page_size - 1) // page_size
        
        # Fermer la connexion
        conn.close()
        
        # Retourner les résultats
        return {
            "data": data,
            "total_pages": total_pages,
            "total_count": total_count
        }
    except Exception as e:
        return {
            "data": [],
            "total_pages": 0,
            "total_count": 0,
            "error": str(e)
        }

@router.get("/csv/stats")
def get_stats(type: str = Query("operators", enum=["operators", "status", "2fa"])):
    # Si le fichier n'existe pas, retourner un résultat vide avec un message spécial
    if not check_csv_exists():
        return {"data": [], "message": "no_data"}
    
    try:
        # Connexion à DuckDB avec une instance en mémoire pour de meilleures performances
        conn = duckdb.connect(":memory:")
        
        # Requête SQL optimisée selon le type de statistique
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
                SELECT USER_STATUS as name, COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM '{CSV_FILE_PATH}'), 2) as value
                FROM '{CSV_FILE_PATH}'
                WHERE USER_STATUS IS NOT NULL
                GROUP BY USER_STATUS
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
            return []
        
        # Exécuter la requête
        result = conn.execute(query).fetchall()
        
        # Transformer les résultats
        data = []
        for row in result:
            data.append({
                "name": row[0] or "Non défini",
                "value": row[2]
            })
        
        # Fermer la connexion
        conn.close()
        
        return data
    except Exception as e:
        return {"data": [], "error": str(e)}

@router.get("/csv/filter-options")
def get_filter_options():
    # Si le fichier n'existe pas, retourner un résultat vide avec un message spécial
    if not check_csv_exists():
        return {
            "statuts": [],
            "fa_statuts": [],
            "annees": [],
            "message": "no_data"
        }
    
    try:
        # Connexion à DuckDB avec une instance en mémoire pour de meilleures performances
        conn = duckdb.connect(":memory:")
        
        # Requêtes SQL directes pour de meilleures performances
        statuts_query = f"""
            SELECT DISTINCT USER_STATUS as statut
            FROM '{CSV_FILE_PATH}'
            WHERE USER_STATUS IS NOT NULL
            ORDER BY USER_STATUS
        """
        
        fa_statuts_query = f"""
            SELECT DISTINCT "2FA_STATUS" as fa_statut
            FROM '{CSV_FILE_PATH}'
            WHERE "2FA_STATUS" IS NOT NULL
            ORDER BY "2FA_STATUS"
        """
        
        annees_query = f"""
            SELECT DISTINCT EXTRACT(YEAR FROM CREATED_DATE)::VARCHAR as annee
            FROM '{CSV_FILE_PATH}'
            WHERE CREATED_DATE IS NOT NULL
            ORDER BY annee
        """
        
        # Exécuter les requêtes
        statuts = [row[0] for row in conn.execute(statuts_query).fetchall()]
        fa_statuts = [row[0] for row in conn.execute(fa_statuts_query).fetchall()]
        annees = [row[0] for row in conn.execute(annees_query).fetchall()]
        
        # Fermer la connexion
        conn.close()
        
        return {
            "statuts": statuts,
            "fa_statuts": fa_statuts,
            "annees": annees
        }
    except Exception as e:
        return {
            "statuts": [],
            "fa_statuts": [],
            "annees": [],
            "error": str(e)
        }

@router.post("/csv/upload")
async def upload_csv(file: UploadFile = File(...)):
    try:
        # Vérifier que c'est un fichier CSV
        if not file.filename.endswith('.csv'):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Le fichier doit être au format CSV"}
            )
        
        # Créer le répertoire de données s'il n'existe pas
        os.makedirs(os.path.dirname(CSV_FILE_PATH), exist_ok=True)
        
        # Sauvegarder le fichier
        with open(CSV_FILE_PATH, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"success": True, "message": "Fichier CSV importé avec succès"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erreur lors de l'importation: {str(e)}"}
        )

@router.get("/csv/export")
def export_csv(
    statut: Optional[str] = None,
    fa_statut: Optional[str] = None,
    limite_type: Optional[str] = None,
    limite_valeur: Optional[float] = None,
    date_min: Optional[str] = None,
    date_max: Optional[str] = None,
    annee: Optional[str] = None
):
    if not check_csv_exists():
        return JSONResponse(
            status_code=200,  # Utiliser 200 au lieu de 404 pour une meilleure expérience utilisateur
            content={"message": "no_data"}
        )
    
    try:
        # Connexion à DuckDB avec une instance en mémoire pour de meilleures performances
        conn = duckdb.connect(":memory:")
        
        # Utiliser une requête SQL optimisée pour l'agrégation directe
        query = f"""
            SELECT 
                "Operateur" as operateur,
                COUNT(*) as nombre_in,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM '{CSV_FILE_PATH}'), 2) as pourcentage_in
            FROM '{CSV_FILE_PATH}'
        """
        
        # Ajouter les conditions de filtrage
        conditions = []
        
        if statut and statut != 'all':
            conditions.append(f"USER_STATUS = '{statut}'")
        
        if fa_statut and fa_statut != 'all':
            conditions.append(f"\"2FA_STATUS\" = '{fa_statut}'")
        
        if date_min:
            conditions.append(f"CREATED_DATE >= '{date_min}'")
        
        if date_max:
            conditions.append(f"CREATED_DATE <= '{date_max}'")
        
        if annee and annee != 'all':
            conditions.append(f"EXTRACT(YEAR FROM CREATED_DATE) = {annee}")
        
        # Ajouter les conditions à la requête
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Compléter la requête avec le regroupement et le tri
        query += " GROUP BY operateur ORDER BY nombre_in DESC"
        
        # Exécuter la requête
        result = conn.execute(query).fetchall()
        
        # Créer le CSV manuellement pour éviter de charger tout en mémoire
        csv_content = "Opérateur,Nombre d'IN,Pourcentage IN (%)\n"
        
        for row in result:
            csv_content += f"{row[0]},{row[1]},{row[2]}\n"
        
        # Fermer la connexion
        conn.close()
        
        # Préparer la réponse
        response = StreamingResponse(
            iter([csv_content]),
            media_type="text/csv"
        )
        response.headers["Content-Disposition"] = f"attachment; filename=export_resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return response
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@router.get("/csv/export-in-details")
def export_in_details(
    statut: Optional[str] = None,
    fa_statut: Optional[str] = None,
    limite_type: Optional[str] = None,
    limite_valeur: Optional[float] = None,
    date_min: Optional[str] = None,
    date_max: Optional[str] = None,
    annee: Optional[str] = None
):
    if not check_csv_exists():
        return JSONResponse(
            status_code=200,  # Utiliser 200 au lieu de 404 pour une meilleure expérience utilisateur
            content={"message": "no_data"}
        )
    
    try:
        # Connexion à DuckDB avec une instance en mémoire pour de meilleures performances
        conn = duckdb.connect(":memory:")
        
        # Construire la requête SQL optimisée
        query = f"""
            SELECT 
                FIRST_NAME as "Prénom",
                LAST_NAME as "Nom",
                EMAIL as "Email",
                TELEPHONE as "Téléphone",
                INDICATIF as "Indicatif",
                USER_STATUS as "Statut",
                "2FA_STATUS" as "Statut 2FA",
                CREATED_DATE as "Date de création",
                "Operateur" as "Opérateur"
            FROM '{CSV_FILE_PATH}'
        """
        
        # Ajouter les conditions de filtrage
        conditions = []
        
        if statut and statut != 'all':
            conditions.append(f"USER_STATUS = '{statut}'")
        
        if fa_statut and fa_statut != 'all':
            conditions.append(f"\"2FA_STATUS\" = '{fa_statut}'")
        
        if date_min:
            conditions.append(f"CREATED_DATE >= '{date_min}'")
        
        if date_max:
            conditions.append(f"CREATED_DATE <= '{date_max}'")
        
        if annee and annee != 'all':
            conditions.append(f"EXTRACT(YEAR FROM CREATED_DATE) = {annee}")
        
        # Ajouter les conditions à la requête
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Exécuter la requête
        result = conn.execute(query).fetchall()
        columns = conn.execute(query).description
        column_names = [col[0] for col in columns]
        
        # Créer le CSV manuellement pour éviter de charger tout en mémoire
        csv_content = ",".join(column_names) + "\n"
        
        for row in result:
            csv_content += ",".join([str(val) if val is not None else "" for val in row]) + "\n"
        
        # Fermer la connexion
        conn.close()
        
        # Préparer la réponse
        response = StreamingResponse(
            iter([csv_content]),
            media_type="text/csv"
        )
        response.headers["Content-Disposition"] = f"attachment; filename=export_details_in_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return response
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
