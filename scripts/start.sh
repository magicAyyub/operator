#!/bin/bash

echo "Démarrage de l'application de recherche..."
echo

# Vérification si Docker est en cours d'exécution
if ! docker info > /dev/null 2>&1; then
    echo "Docker n'est pas lancé. Veuillez lancer Docker Desktop et réessayer."
    echo
    read -p "Appuyez sur une touche pour quitter..."
    exit 1
fi

# Vérification supplémentaire que le daemon Docker est prêt
echo "Vérification de l'état de Docker..."
if ! docker ps > /dev/null 2>&1; then
    echo "Docker n'est pas encore prêt. Veuillez attendre que Docker Desktop soit complètement démarré."
    echo
    read -p "Appuyez sur une touche pour quitter..."
    exit 1
fi

# Vérification de la base de données MySQL
echo "Vérification de la base de données..."
cd backend || exit

if ! docker-compose ps | grep "db" | grep "Up" > /dev/null 2>&1; then
    echo "Démarrage de la base de données..."
    docker-compose up -d

    echo "Attente du démarrage complet de MySQL..."
    sleep 15
else
    echo "La base de données est déjà en cours d'exécution."
fi

# Activation de l'environnement Python et lancement du backend
echo "Démarrage du backend..."
source venv/bin/activate
gnome-terminal -- bash -c "source venv/bin/activate && python app.py; exec bash"

# Retour au dossier racine
cd ..

# Attente que le backend soit prêt
sleep 5

# Lancement du frontend React
echo "Démarrage du frontend..."
cd frontend || exit
gnome-terminal -- bash -c "npm run dev; exec bash"

# Attente que le frontend soit prêt
sleep 5

# Ouverture du navigateur
xdg-open "http://localhost:5173" &

echo
echo "Application lancée avec succès !"
echo "Pour arrêter l'application, fermez les fenêtres et Docker Desktop."
echo
read -p "Appuyez sur une touche pour quitter..."