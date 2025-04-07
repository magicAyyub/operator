# Utilise l'image Python 3.12
FROM python:3.12

# Définit le répertoire de travail dans le conteneur
WORKDIR /app

# Copie le fichier pyproject.toml et poetry.lock
COPY pyproject.toml poetry.lock /app/

# Installe Poetry
RUN pip install poetry

# Installe les dépendances du projet
RUN poetry install --no-root

# Copie tout le reste du projet dans le conteneur
COPY . /app/

# Exécute le serveur via main.py
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]