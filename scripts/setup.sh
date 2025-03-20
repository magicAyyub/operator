#!/bin/bash

echo "Installation de l'application de recherche..."
echo

# Vérification de Docker
if ! command -v docker &> /dev/null; then
    echo "Docker n'est pas installé. Veuillez installer Docker Desktop d'abord."
    echo "Lien : https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    read -p "Appuyez sur une touche pour quitter..."
    exit 1
fi

# Vérification de Node.js
if ! command -v node &> /dev/null; then
    echo "Node.js n'est pas installé. Veuillez installer Node.js d'abord."
    echo "Lien : https://nodejs.org/"
    read -p "Appuyez sur une touche pour quitter..."
    exit 1
fi

# Installation du backend
echo "Installation du backend..."
cd ..
cd backend || exit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Installation du frontend
echo
echo "Installation du frontend..."
cd frontend || exit
npm install
cd ..

# Configuration de la base de données
echo "Configuration de la base de données..."
cd backend || exit
docker-compose up -d
cd ..

echo
echo "Installation terminée avec succès !"
echo "Pour lancer l'application, utilisez start.sh"
echo
read -p "Appuyez sur une touche pour quitter..."