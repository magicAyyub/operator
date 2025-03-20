from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from sqlalchemy import create_engine
from app.config import Config

socketio = SocketIO(cors_allowed_origins=Config.SOCKETIO_CORS_ALLOWED_ORIGINS)
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    socketio.init_app(app)

    # Importer et enregistrer les blueprints
    from app.routes.index import index_bp
    from app.routes.csv_operations import csv_bp
    from app.routes.database_operations import db_bp
    from app.routes.file_processing import file_bp
    from app.routes.dashboard_operations import board_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(csv_bp)
    app.register_blueprint(db_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(board_bp)

    return app