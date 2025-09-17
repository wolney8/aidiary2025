# Flask application factory with CORS and JWT setup
import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET', 'dev-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400  # 24 hours
    env_db_path = os.getenv('DB_PATH')
    fallback_path = os.path.join(app.root_path, 'db', 'app.db')

    if env_db_path:
        # Resolve relative paths against the server package root
        resolved_path = env_db_path if os.path.isabs(env_db_path) else os.path.join(app.root_path, env_db_path)
        if os.path.exists(resolved_path):
            database_path = resolved_path
        elif os.path.exists(fallback_path):
            database_path = fallback_path
        else:
            database_path = resolved_path
    else:
        database_path = fallback_path

    if not os.path.exists(database_path):
        app.logger.warning('Database file not found at %s', database_path)

    app.config['DATABASE_PATH'] = database_path
    
    # CORS configuration
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:4200').split(',')
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # JWT initialisation
    JWTManager(app)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.profile import profile_bp
    from routes.entries import entries_bp
    from routes.analyse import analyse_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(profile_bp, url_prefix='/api')
    app.register_blueprint(entries_bp, url_prefix='/api')
    app.register_blueprint(analyse_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('FLASK_PORT', 5001))
    app.run(debug=True, port=port)
