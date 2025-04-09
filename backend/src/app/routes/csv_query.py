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
    filtre_global: Optional[bool] = False,
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
        
        # 1. Calculer d'abord le nombre total d'entrées et par opérateur (pour le pourcentage global)
        total_count_query = f"SELECT COUNT(*) as total FROM '{CSV_FILE_PATH}'"
        total_count = conn.execute(total_count_query).fetchone()[0]
        
        # Calculer le nombre total par opérateur (pour le pourcentage global)
        operator_count_query = f"""
            SELECT "Operateur" as operateur, COUNT(*) as count
            FROM '{CSV_FILE_PATH}'
            GROUP BY "Operateur"
        """
        operator_counts = {row[0]: row[1] for row in conn.execute(operator_count_query).fetchall()}
        
        # Calculer les pourcentages globaux pour tous les opérateurs (indépendamment des filtres)
        global_percentages = {}
        for operateur, count in operator_counts.items():
            global_percentages[operateur] = round((count / total_count * 100), 2) if total_count > 0 else 0
        
        # 2. Construire la requête SQL pour les données filtrées
        base_query = f"SELECT * FROM '{CSV_FILE_PATH}'"
        
        # Ajouter les conditions de filtrage
        conditions = []
        
        if statut and statut != 'all':
            conditions.append(f"USER_STATUS = '{statut}'")
        
        if fa_statut and fa_statut != 'all':
            conditions.append(f"\"2FA_STATUS\" = '{fa_statut}'")
        
        # Correction du problème de date : ajouter un jour à date_max pour inclure la date sélectionnée
        if date_min:
            conditions.append(f"CREATED_DATE >= '{date_min}'")
        
        if date_max:
            # Ajouter un jour à date_max pour inclure la date sélectionnée
            date_max_obj = datetime.strptime(date_max, "%Y-%m-%d")
            date_max_plus_one = (date_max_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            conditions.append(f"CREATED_DATE < '{date_max_plus_one}'")
        
        if annee and annee != 'all':
            conditions.append(f"EXTRACT(YEAR FROM CREATED_DATE) = {annee}")
        
        # Ajouter les conditions à la requête
        filtered_query = base_query
        if conditions:
            filtered_query += " WHERE " + " AND ".join(conditions)
        
        # 3. Compter le nombre d'entrées filtrées par opérateur
        filtered_operator_query = f"""
            SELECT "Operateur" as operateur, COUNT(*) as count
            FROM ({filtered_query}) as filtered_data
            GROUP BY "Operateur"
        """
        filtered_operator_counts = {row[0]: row[1] for row in conn.execute(filtered_operator_query).fetchall()}
        
        # 4. Compter le nombre total d'entrées filtrées
        filtered_count_query = f"SELECT COUNT(*) as total FROM ({filtered_query}) as filtered_data"
        filtered_total = conn.execute(filtered_count_query).fetchone()[0]
        
        # 5. Préparer les données pour tous les opérateurs qui ont des entrées après filtrage
        all_operators_data = []
        
        for operateur, filtered_count in filtered_operator_counts.items():
            # Récupérer le pourcentage global pour cet opérateur (calculé précédemment)
            global_percentage = global_percentages.get(operateur, 0)
            
            # Calculer le pourcentage filtré (basé sur les données filtrées)
            filtered_percentage = round((filtered_count / filtered_total * 100), 2) if filtered_total > 0 else 0
            
            all_operators_data.append({
                "id": operateur,  # Utiliser l'opérateur comme ID
                "operateur": operateur,
                "nombre_in": filtered_count,  # Nombre filtré
                "pourcentage_in": global_percentage,  # Pourcentage global (indépendant des filtres)
                "pourcentage_filtre": filtered_percentage,  # Pourcentage filtré
            })
        
        # 6. Appliquer le filtre de limite si nécessaire
        if limite_type and limite_type != 'none' and limite_valeur is not None:
            filtered_data = []
            for item in all_operators_data:
                # Choisir le pourcentage à vérifier en fonction de filtre_global
                if filtre_global:
                    percentage_to_check = item["pourcentage_in"]
                else:
                    percentage_to_check = item["pourcentage_filtre"]
                
                if limite_type == 'lt' and percentage_to_check < float(limite_valeur):
                    filtered_data.append(item)
                elif limite_type == 'gt' and percentage_to_check > float(limite_valeur):
                    filtered_data.append(item)
            
            all_operators_data = filtered_data
        
        # 7. Trier les données par nombre d'IN (filtré) décroissant
        all_operators_data.sort(key=lambda x: x["nombre_in"], reverse=True)
        
        # 8. Appliquer la pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_data = all_operators_data[start_idx:end_idx]
        
        # 9. Calculer le nombre total de pages
        total_pages = (len(all_operators_data) + page_size - 1) // page_size if all_operators_data else 0
        
        # Fermer la connexion
        conn.close()
        
        # Retourner les résultats
        return {
            "data": paginated_data,
            "total_pages": total_pages,
            "total_count": len(all_operators_data),
            "is_filtered": len(conditions) > 0 or (limite_type and limite_type != 'none' and limite_valeur is not None)
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
    filtre_global: Optional[bool] = False,
    date_min: Optional[str] = None,
    date_max: Optional[str] = None,
    annee: Optional[str] = None
):
    if not check_csv_exists():
        return JSONResponse(
            status_code=200,
            content={"message": "no_data"}
        )
    
    try:
        # Connexion à DuckDB avec une instance en mémoire pour de meilleures performances
        conn = duckdb.connect(":memory:")
        
        # 1. Calculer d'abord le nombre total d'entrées (pour le pourcentage global)
        total_count_query = f"SELECT COUNT(*) as total FROM '{CSV_FILE_PATH}'"
        total_count = conn.execute(total_count_query).fetchone()[0]
        
        # Calculer le nombre total par opérateur (pour le pourcentage global)
        operator_count_query = f"""
            SELECT "Operateur" as operateur, COUNT(*) as count
            FROM '{CSV_FILE_PATH}'
            GROUP BY "Operateur"
        """
        operator_counts = {row[0]: row[1] for row in conn.execute(operator_count_query).fetchall()}
        
        # Calculer les pourcentages globaux pour tous les opérateurs (indépendamment des filtres)
        global_percentages = {}
        for operateur, count in operator_counts.items():
            global_percentages[operateur] = round((count / total_count * 100), 2) if total_count > 0 else 0
        
        # 2. Construire la requête SQL pour les données filtrées
        base_query = f"SELECT * FROM '{CSV_FILE_PATH}'"
        
        # Ajouter les conditions de filtrage
        conditions = []
        
        if statut and statut != 'all':
            conditions.append(f"USER_STATUS = '{statut}'")
        
        if fa_statut and fa_statut != 'all':
            conditions.append(f"\"2FA_STATUS\" = '{fa_statut}'")
        
        # Correction du problème de date : ajouter un jour à date_max pour inclure la date sélectionnée
        if date_min:
            conditions.append(f"CREATED_DATE >= '{date_min}'")
        
        if date_max:
            # Ajouter un jour à date_max pour inclure la date sélectionnée
            date_max_obj = datetime.strptime(date_max, "%Y-%m-%d")
            date_max_plus_one = (date_max_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            conditions.append(f"CREATED_DATE < '{date_max_plus_one}'")
        
        if annee and annee != 'all':
            conditions.append(f"EXTRACT(YEAR FROM CREATED_DATE) = {annee}")
        
        # Ajouter les conditions à la requête
        filtered_query = base_query
        if conditions:
            filtered_query += " WHERE " + " AND ".join(conditions)
        
        # 3. Compter le nombre d'entrées filtrées par opérateur
        filtered_operator_query = f"""
            SELECT "Operateur" as operateur, COUNT(*) as count
            FROM ({filtered_query}) as filtered_data
            GROUP BY "Operateur"
        """
        filtered_operator_counts = {row[0]: row[1] for row in conn.execute(filtered_operator_query).fetchall()}
        
        # 4. Compter le nombre total d'entrées filtrées
        filtered_count_query = f"SELECT COUNT(*) as total FROM ({filtered_query}) as filtered_data"
        filtered_total = conn.execute(filtered_count_query).fetchone()[0]
        
        # 5. Préparer les données pour tous les opérateurs qui ont des entrées après filtrage
        all_operators_data = []
        
        for operateur, filtered_count in filtered_operator_counts.items():
            # Récupérer le pourcentage global pour cet opérateur (calculé précédemment)
            global_percentage = global_percentages.get(operateur, 0)
            
            # Calculer le pourcentage filtré (basé sur les données filtrées)
            filtered_percentage = round((filtered_count / filtered_total * 100), 2) if filtered_total > 0 else 0
            
            all_operators_data.append({
                "operateur": operateur,
                "nombre_in": filtered_count,
                "pourcentage_global": global_percentage,
                "pourcentage_filtre": filtered_percentage
            })
        
        # 6. Appliquer le filtre de limite si nécessaire
        if limite_type and limite_type != 'none' and limite_valeur is not None:
            filtered_data = []
            for item in all_operators_data:
                # Choisir le pourcentage à vérifier en fonction de filtre_global
                if filtre_global:
                    percentage_to_check = item["pourcentage_global"]
                else:
                    percentage_to_check = item["pourcentage_filtre"]
                
                if limite_type == 'lt' and percentage_to_check < float(limite_valeur):
                    filtered_data.append(item)
                elif limite_type == 'gt' and percentage_to_check > float(limite_valeur):
                    filtered_data.append(item)
            
            all_operators_data = filtered_data
        
        # 7. Trier les données par nombre d'IN (filtré) décroissant
        all_operators_data.sort(key=lambda x: x["nombre_in"], reverse=True)
        
        # Déterminer si des filtres sont appliqués
        is_filtered = len(conditions) > 0 or (limite_type and limite_type != 'none' and limite_valeur is not None)
        
        # Préparer les en-têtes du CSV
        if is_filtered:
            headers = ["Opérateur", "Nombre d'IN", "% IN (parc global)", "% IN (filtré)"]
        else:
            headers = ["Opérateur", "Nombre d'IN", "% IN (parc global)"]
        
        # Créer le CSV manuellement
        csv_content = ",".join(headers) + "\n"
        
        # Ajouter les données
        for item in all_operators_data:
            if is_filtered:
                csv_content += f"{item['operateur']},{item['nombre_in']},{item['pourcentage_global']},{item['pourcentage_filtre']}\n"
            else:
                csv_content += f"{item['operateur']},{item['nombre_in']},{item['pourcentage_global']}\n"
        
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