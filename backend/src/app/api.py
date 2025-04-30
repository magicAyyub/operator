"""
This module contains the FastAPI application and its configuration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.app.routes import file_processing
from src.app.routes import csv_query
from fastapi import APIRouter, HTTPException, status
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


file_processing_router = file_processing.router
csv_query_router = csv_query.router

app = FastAPI(
    title = "API operator",
    description = "API pour la jointure de fichier avec operateur",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include all routes
app.include_router(file_processing_router)
app.include_router(csv_query_router)


# Root endpoint to verify API connection
@app.get("/")
async def root() -> dict:
    return {"message": "Bienvenu sur l'API jointure de fichier avec opérateur"}