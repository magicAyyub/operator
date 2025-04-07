FROM python:3.10-slim

WORKDIR /app

# Installations critiques
RUN apt-get update && apt-get install -y \
    gcc libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Copie sélective
COPY requirements.txt .
COPY utils/data_processor.exe /app/utils/
COPY app /app/app
COPY run.py .

# Installation Python
RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--chdir", "/app", "run:app"]
