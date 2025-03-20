@echo off
echo Demarrage de l'application de recherche...
echo.

REM Vérification si Docker est en cours d'exécution
docker info > nul 2>&1
if %errorlevel% neq 0 (
    echo Docker n'est pas lance. Veuillez lancer Docker Desktop et reessayer.
    echo.
    pause
    exit /b 1
)

REM Vérification supplémentaire que le daemon Docker est prêt
echo Verification de l'etat de Docker...
docker ps > nul 2>&1
if %errorlevel% neq 0 (
    echo Docker n'est pas encore pret. Veuillez attendre que Docker Desktop soit completement demarre.
    echo.
    pause
    exit /b 1
)

REM Vérification de la base de données MySQL
echo Verification de la base de donnees...
cd backend
docker-compose ps | find "db" | find "Up" > nul
if %errorlevel% neq 0 (
    echo Demarrage de la base de donnees...
    docker-compose up -d
    
    echo Attente du demarrage complet de MySQL...
    timeout /t 15 /nobreak > nul
) else (
    echo La base de donnees est deja en cours d'execution.
)

REM Activation de l'environnement Python et lancement du backend
echo Demarrage du backend...
call venv\Scripts\activate
start "Backend Flask" cmd /k "venv\Scripts\activate && python run.py"

REM Retour au dossier racine
cd ..

REM Attente que le backend soit prêt
timeout /t 5 /nobreak > nul

REM Lancement du frontend React
echo Demarrage du frontend...
cd frontend
start "Frontend React" cmd /k "npm run dev"

REM Attente que le frontend soit prêt
timeout /t 5 /nobreak > nul

REM Ouverture du navigateur
start http://localhost:3000

echo.
echo Application lancee avec succes !
echo Pour arreter l'application, fermez les fenetres et Docker Desktop.
echo.
pause