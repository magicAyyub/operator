@echo off
echo Installation de l'application de recherche...
echo.

REM Vérification de Docker
docker --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Docker n'est pas installe. Veuillez installer Docker Desktop d'abord.
    echo Lien: https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe
    pause
    exit
)

REM Vérification de Node.js
node --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Node.js n'est pas installe. Veuillez installer Node.js d'abord.
    echo Lien: https://nodejs.org/
    pause
    exit
)

REM Installation du backend
echo Installation du backend...
cd backend
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
cd ..

REM Installation du frontend
echo.
echo Installation du frontend...
cd frontend
npm install
cd ..

echo Configuration de la base de donnees...
cd backend
docker-compose up -d
cd ..

echo.
echo Installation terminee avec succes !
echo Pour lancer l'application, utilisez start.bat
echo.
pause