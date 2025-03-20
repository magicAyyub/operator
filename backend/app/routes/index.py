from flask import Blueprint, jsonify
import os
from app.config import Config

index_bp = Blueprint('index', __name__)

@index_bp.route("/", methods=["GET"])
def index():
    # Nettoie le dossier temporaire
    for filename in os.listdir(Config.UPLOAD_FOLDER):
        file_path = os.path.join(Config.UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path) or os.path.islink(file_path):
            os.unlink(file_path)
    return jsonify({'access': True}), 500