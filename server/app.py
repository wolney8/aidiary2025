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
    app.config['DATABASE_PATH'] = os.getenv('DB_PATH', './app.db')
    
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
