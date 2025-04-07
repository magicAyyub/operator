import os
import sys
from pathlib import Path
import subprocess


def check_docker_compose():
    """
    Vérifie si Docker et Docker Compose sont installés.
    """
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
        print("✅ Docker et Docker Compose sont installés.")
    except FileNotFoundError:
        print("❌ Docker ou Docker Compose n'est pas installé. Veuillez l'installer avant de continuer.")
        exit(1)

def build_and_run_docker():
    """
    Lance la construction et l'exécution avec docker-compose.
    """
    try:
        print("\n--- Lancement de Docker Compose ---")
        print("⚠️  Cela peut prendre un certain temps pour la première")
        subprocess.run(["docker-compose", "up", "--build", "-d"], check=True)
        print("✅ Docker Compose a été lancé avec succès.")
    except subprocess.CalledProcessError:
        print("❌ Une erreur est survenue lors de l'exécution de Docker Compose. Assurez-vous que Docker-desktop est en cours d'exécution.")
        exit(1)

def stop_docker():
    """
    Arrête les conteneurs Docker.
    """
    try:
        print("\n--- Arrêt de Docker Compose ---")
        subprocess.run(["docker-compose", "down"], check=True)
        print("✅ Docker Compose a été arrêté avec succès.")
    except subprocess.CalledProcessError:
        print("❌ Une erreur est survenue lors de l'arrêt de Docker Compose.")
        exit(1)

def remove_docker_volumes():
    """
    Supprime les volumes Docker.
    """
    try:
        print("\n--- Suppression des volumes Docker ---")
        subprocess.run(["docker-compose", "down", "-v"], check=True)
        print("✅ Les volumes Docker ont été supprimés avec succès.")
    except subprocess.CalledProcessError:
        print("❌ Une erreur est survenue lors de la suppression des volumes Docker.")
        exit(1)
def show_docker_logs():
    """
    Affiche les logs des conteneurs Docker.
    """
    try:
        print("\n--- Affichage des logs Docker ---")
        subprocess.run(["docker-compose", "logs"], check=True)
    except subprocess.CalledProcessError:
        print("❌ Une erreur est survenue lors de l'affichage des logs Docker.")
        exit(1)

def reset_docker():
    """
    Réinitialise les conteneurs Docker.
    """
    stop_docker()
    remove_docker_volumes()
    build_and_run_docker()
        

def setup():
    """
    Point d'entrée principal du script.
    """
    print("⚙️  Initialisation de la configuration Docker...")

    # Vérification de l'installation de Docker et Docker Compose
    check_docker_compose()

    # Lancement de docker-compose
    build_and_run_docker()
