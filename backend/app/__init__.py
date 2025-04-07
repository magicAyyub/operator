from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from app.config import Config

socketio = SocketIO(cors_allowed_origins=Config.SOCKETIO_CORS_ALLOWED_ORIGINS)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    socketio.init_app(app)

    # Importer et enregistrer les blueprints
    from app.routes.index import index_bp
    from app.routes.file_processing import file_bp

    app.register_blueprint(index_bp)
    app.register_blueprint(file_bp)

    return app