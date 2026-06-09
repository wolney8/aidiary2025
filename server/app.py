# Flask application factory with CORS and JWT setup
import os
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from services.runtime_migrations import (
    ensure_entry_ai_metadata_table,
    ensure_entry_mood_style_columns,
    ensure_export_history_table,
    ensure_import_sessions_table,
    ensure_user_settings_columns,
)
from services.media_storage import DEFAULT_MEDIA_URL_PREFIX, ensure_media_root

# Load environment variables
load_dotenv()


def _ensure_nltk_data() -> None:
    """Download NLTK corpora required for keyword/NER enrichment, if not already present."""
    try:
        import nltk
        for _corpus in [
            'punkt', 'punkt_tab',
            'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng',
            'maxent_ne_chunker', 'maxent_ne_chunker_tab',
            'words',
        ]:
            nltk.download(_corpus, quiet=True)
    except Exception:
        pass

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
    media_root = os.getenv('MEDIA_ROOT')
    fallback_media_root = os.path.join(app.root_path, 'media')
    if media_root:
        resolved_media_root = media_root if os.path.isabs(media_root) else os.path.join(app.root_path, media_root)
    else:
        resolved_media_root = fallback_media_root
    app.config['MEDIA_ROOT'] = resolved_media_root
    app.config['MEDIA_URL_PREFIX'] = DEFAULT_MEDIA_URL_PREFIX
    app.config['MEDIA_BASE_URL'] = (os.getenv('MEDIA_BASE_URL') or '').strip() or None
    ensure_media_root(resolved_media_root)

    try:
        added_columns = ensure_entry_mood_style_columns(database_path, app.logger.info)
        if added_columns == 0:
            app.logger.info('Runtime DB migration check: no column changes needed')
    except Exception as migration_exc:
        app.logger.warning('Runtime DB migration skipped due to error: %s', migration_exc)

    try:
        ensure_entry_ai_metadata_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime metadata migration skipped due to error: %s', migration_exc)

    try:
        added_user_columns = ensure_user_settings_columns(database_path, app.logger.info)
        if added_user_columns == 0:
            app.logger.info('Runtime user settings migration check: no column changes needed')
    except Exception as migration_exc:
        app.logger.warning('Runtime user settings migration skipped due to error: %s', migration_exc)

    try:
        ensure_export_history_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime export history migration skipped due to error: %s', migration_exc)

    try:
        ensure_import_sessions_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime import session migration skipped due to error: %s', migration_exc)
    
    # CORS configuration
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:4200').split(',')
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # JWT initialisation
    JWTManager(app)
    # --- DEBUG: helpful JWT logging for local development ---
    # These handlers will log common JWT errors so the developer can
    # see why a token was rejected (missing, expired, invalid signature).

    @app.errorhandler(401)
    def _handle_401(err):
        app.logger.warning('401 Unauthorized: %s', getattr(err, 'description', err))
        return {'msg': 'Unauthorized'}, 401

    @app.errorhandler(422)
    def _handle_422(err):
        app.logger.warning('422 Unprocessable: %s', getattr(err, 'description', err))
        return {'msg': 'Unprocessable Entity'}, 422

    @app.errorhandler(500)
    def _handle_500(err):
        app.logger.error('500 Internal Server Error: %s', err)
        return {'msg': 'Internal Server Error'}, 500

    @app.before_request
    def _log_jwt_presence():
        # Log presence of Authorization header for debugging; don't attempt
        # to verify here to avoid interfering with route-level jwt_required.
        auth = None
        try:
            auth = request.headers.get('Authorization')
        except Exception:
            auth = None
        if auth:
            # Log only the prefix to avoid exposing full tokens in logs
            app.logger.debug('Authorization header present (prefix): %s', auth[:64])
        else:
            app.logger.debug('No Authorization header present on request to %s', request.path)
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.profile import profile_bp
    from routes.entries import entries_bp
    from routes.analyse import analyse_bp
    from routes.import_routes import import_bp
    from routes.chat import chat_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(profile_bp, url_prefix='/api')
    app.register_blueprint(entries_bp, url_prefix='/api')
    app.register_blueprint(analyse_bp, url_prefix='/api')
    app.register_blueprint(import_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy'}, 200

    @app.route(f'{DEFAULT_MEDIA_URL_PREFIX}/<path:storage_key>')
    def serve_media(storage_key: str):
        return send_from_directory(app.config['MEDIA_ROOT'], storage_key, conditional=True)

    # Download NLTK data and backfill any entries that were imported before data was available
    _ensure_nltk_data()
    try:
        import sqlite3 as _sqlite3
        from services.import_service import backfill_nltk_enrichment
        with _sqlite3.connect(app.config['DATABASE_PATH'], timeout=10) as _bfconn:
            _bfconn.execute('PRAGMA journal_mode=WAL')
            backfill_nltk_enrichment(_bfconn, app.logger)
    except Exception as _bf_exc:
        app.logger.warning('Startup NLTK backfill skipped: %s', _bf_exc)
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('FLASK_PORT', 5001))
    app.run(debug=True, port=port)
