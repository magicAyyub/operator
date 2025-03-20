from pathlib import Path
from flask import  jsonify, Blueprint
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from app.utils.enhanced_fraud_detector import EnhancedFraudDetector
from app.config import Config


board_bp = Blueprint('anomalies', __name__)

# TODO: Faire le traitement de détection et passer directement les données au lieu de lire le csv
@board_bp.route('/api/anomalies', methods=['GET'])
def get_anomalies() -> Tuple[Dict, int]:
    """Retourne les anomalies"""
    return pd.read_csv(Config.UPLOAD_FOLDER / 'anomalies_clarifiees.csv', low_memory=False).to_json(orient='records')
    