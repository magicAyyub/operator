#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import subprocess
from pathlib import Path

def ask_yes_no(question):
    while True:
        response = input(f"{question} [y/n] ").lower()
        if response in ['y', 'n']:
            return response == 'y'
        print("Veuillez répondre y ou n")

def run_docker_command(command, error_message):
    try:
        subprocess.run(command, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"\nERREUR: {error_message}")
        print(f"Message d'erreur : {str(e)}")
        sys.exit(1)

def setup():
    print("""
    ======================================
    SETUP DOCKER DUCKDB/REDIS POUR LE PROJET
    ======================================
    """)

    # 1. Vérifier la structure
    required = ['app', 'utils/data_processor.exe', 'run.py']
    missing = [f for f in required if not Path(f).exists()]
    
    if missing:
        print("\nERREUR: Structure de projet invalide.")
        print("Fichiers/dossiers manquants:")
        for f in missing:
            print(f" - {f}")
        sys.exit(1)

    # 2. Créer les dossiers nécessaires
    Path("docker").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)

    # 3. Vérifier Docker
    print("\n[1/4] Vérification de Docker...")
    run_docker_command("docker info", "Docker n'est pas démarré ou configuré correctement")

    # 4. Démarrer les containers
    print("\n[2/4] Build des containers Docker...")
    run_docker_command("docker-compose up -d --build", "Échec du build Docker")

    # 5. Attendre que Redis soit prêt
    print("\n[3/4] Attente du démarrage de Redis...")
    run_docker_command(
        "docker exec $(docker-compose ps -q backend) sh -c 'while ! nc -z redis 6379; do sleep 1; done'",
        "Redis n'a pas démarré correctement"
    )

    # 6. Initialisation conditionnelle de DuckDB
    print("\n[4/4] Vérification de DuckDB...")
    init_command = """
    docker exec $(docker-compose ps -q backend) python -c \"
    import duckdb
    import os
    con = duckdb.connect('/data/analytics.db')
    if 'data' not in [t[0] for t in con.execute('SHOW TABLES').fetchall()]:
        con.execute('CREATE TABLE data (id BIGINT)')  # Schéma minimal
        print('Table vide créée (le CSV sera ajouté via l\\'endpoint)')
    \"
    """
    
    run_docker_command(init_command.strip(), "Échec de l'initialisation de DuckDB")

    print("\nSetup terminé avec succès!")
    print("Accédez à l'application via http://localhost:5005")
    print("\nPour charger des données :")
    print("1. Placez votre CSV dans le dossier data/")
    print("2. Exécutez le script de rafraîchissement :")
    print("   docker exec $(docker-compose ps -q backend) python -c \"import duckdb; con = duckdb.connect('/data/analytics.db'); con.execute('DROP TABLE IF EXISTS data; CREATE TABLE data AS SELECT * FROM read_csv_auto(\\'/data/input.csv\\')')\"")

if __name__ == "__main__":
    setup()
