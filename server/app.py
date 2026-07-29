# Flask application factory with CORS and JWT setup
import os
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity
from flask_limiter.errors import RateLimitExceeded
from dotenv import load_dotenv
from extensions import limiter
from services.database_adapter import DatabaseAdapter
from services.database import configure_app_database
from services.runtime_migrations import (
    ensure_cbt_worksheet_tables,
    ensure_chat_messages_table,
    ensure_chat_observability_events_table,
    ensure_entry_ai_metadata_table,
    ensure_entry_assets_table,
    ensure_entry_resurfacing_preferences_table,
    ensure_entry_mood_style_columns,
    ensure_export_history_table,
    ensure_import_sessions_table,
    ensure_import_jobs_table,
    ensure_important_days_table,
    ensure_public_holiday_cache_table,
    ensure_reflection_summaries_table,
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


def _run_sqlite_runtime_migrations(app, database_path: str) -> None:
    """Run local SQLite compatibility migrations during development startup."""
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

    try:
        ensure_import_jobs_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime import job migration skipped due to error: %s', migration_exc)

    try:
        ensure_entry_assets_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime entry assets migration skipped due to error: %s', migration_exc)

    try:
        ensure_important_days_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime important days migration skipped due to error: %s', migration_exc)

    try:
        ensure_public_holiday_cache_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime public holiday cache migration skipped due to error: %s', migration_exc)

    try:
        ensure_entry_resurfacing_preferences_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime entry resurfacing migration skipped due to error: %s', migration_exc)

    try:
        ensure_reflection_summaries_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime reflection summaries migration skipped due to error: %s', migration_exc)

    try:
        ensure_chat_messages_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime chat messages migration skipped due to error: %s', migration_exc)

    try:
        ensure_chat_observability_events_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning(
            'Runtime chat observability migration skipped due to error: %s',
            migration_exc,
        )

    try:
        ensure_cbt_worksheet_tables(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime CBT worksheet migration skipped due to error: %s', migration_exc)


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Configuration
    app_environment = (os.getenv('APP_ENV') or 'development').strip().lower()
    jwt_secret = os.getenv('JWT_SECRET')
    if not jwt_secret and app_environment == 'production':
        raise RuntimeError('JWT_SECRET must be configured when APP_ENV=production')
    if not jwt_secret:
        app.logger.warning('JWT_SECRET is not configured; using local development secret')
    app.config['JWT_SECRET_KEY'] = jwt_secret or 'dev-secret-key'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400  # 24 hours
    app.config['CHAT_RATE_LIMIT'] = os.getenv('CHAT_RATE_LIMIT', '20 per hour')
    try:
        app.config['CHAT_DAILY_TOKEN_BUDGET'] = max(
            1,
            int(os.getenv('CHAT_DAILY_TOKEN_BUDGET', '50000')),
        )
    except ValueError:
        app.logger.warning('Invalid CHAT_DAILY_TOKEN_BUDGET; using 50000')
        app.config['CHAT_DAILY_TOKEN_BUDGET'] = 50000
    app.config['RATELIMIT_STORAGE_URI'] = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
    database_settings = configure_app_database(app)
    app.config['DATABASE_ADAPTER'] = DatabaseAdapter.from_settings(database_settings)
    database_path = database_settings.sqlite_path
    if not os.path.exists(database_path):
        app.logger.warning('Database file not found at %s', database_path)

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

    if app.config['DATABASE_RUNTIME_MIGRATIONS_ENABLED']:
        _run_sqlite_runtime_migrations(app, database_path)
    else:
        app.logger.info(
            'Runtime SQLite migrations disabled for provider: %s',
            app.config['DATABASE_PROVIDER'],
        )
    
    # CORS configuration
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:4200').split(',')
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # JWT initialisation
    JWTManager(app)
    limiter.init_app(app)
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

    @app.errorhandler(RateLimitExceeded)
    def _handle_chat_rate_limit(_err):
        if request.path.startswith('/api/chat/'):
            try:
                from services.chat_observability import ChatObservabilityService

                identity = get_jwt_identity()
                ChatObservabilityService(
                    app.config['DATABASE_PATH'],
                    adapter=app.config.get('DATABASE_ADAPTER'),
                    log=app.logger,
                ).record_event(
                    event_type='rate_limited',
                    user_id=int(identity) if identity is not None else None,
                    error_code='rate_limit_exceeded',
                    model=os.getenv('CHAT_MODEL', 'gpt-4o-mini'),
                    metadata={'path': request.path},
                )
            except Exception:
                app.logger.exception('Chat rate-limit event could not be recorded')
        return {'error': 'Rate limit exceeded. Try again in 60 minutes.'}, 429

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
    from routes.import_routes import import_bp, recover_import_jobs
    from routes.important_days import important_days_bp
    from routes.public_holidays import public_holidays_bp
    from routes.on_this_day import on_this_day_bp
    from routes.reflection_summaries import reflection_summaries_bp
    from routes.chat import chat_bp
    from routes.cbt import cbt_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(profile_bp, url_prefix='/api')
    app.register_blueprint(entries_bp, url_prefix='/api')
    app.register_blueprint(analyse_bp, url_prefix='/api')
    app.register_blueprint(import_bp, url_prefix='/api')
    app.register_blueprint(important_days_bp, url_prefix='/api')
    app.register_blueprint(public_holidays_bp, url_prefix='/api')
    app.register_blueprint(on_this_day_bp, url_prefix='/api')
    app.register_blueprint(reflection_summaries_bp, url_prefix='/api')
    app.register_blueprint(chat_bp, url_prefix='/api')
    app.register_blueprint(cbt_bp, url_prefix='/api')

    try:
        recovered_jobs = recover_import_jobs(app)
        if recovered_jobs:
            app.logger.info('Recovered %s durable import job(s)', recovered_jobs)
    except Exception as recovery_exc:
        app.logger.warning('Durable import job recovery skipped: %s', recovery_exc)
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy'}, 200

    @app.route('/api/health/database')
    def database_health():
        report = app.config['DATABASE_ADAPTER'].health_check()
        return report, 200 if report.get('ok') is True else 503

    @app.route(f'{DEFAULT_MEDIA_URL_PREFIX}/<path:storage_key>')
    def serve_media(storage_key: str):
        return send_from_directory(app.config['MEDIA_ROOT'], storage_key, conditional=True)

    # Download NLTK data and backfill any entries that were imported before data was available.
    # This legacy backfill is SQLite-only; managed/cloud databases should be migrated explicitly.
    _ensure_nltk_data()
    if app.config['DATABASE_RUNTIME_MIGRATIONS_ENABLED']:
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
