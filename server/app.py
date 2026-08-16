import os
import logging
import time
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, verify_jwt_in_request
from flask_limiter.errors import RateLimitExceeded
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from extensions import limiter
from services.database_adapter import DatabaseAdapter
from services.database import POSTGRES_PROVIDER, SQLITE_PROVIDER, configure_app_database
from services.database_resilience import READ_METHODS, classify_database_exception
from services.runtime_migrations import (
    ensure_account_security_tokens_table,
    ensure_admin_announcement_tables,
    ensure_auth_identities_table,
    ensure_auth_sessions_table,
    ensure_billing_tables,
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
    ensure_security_audit_events_table,
    ensure_user_settings_columns,
)
from services.media_storage import (
    DEFAULT_MEDIA_URL_PREFIX,
    LOCAL_MEDIA_BACKEND,
    R2_MEDIA_BACKEND,
    SUPPORTED_MEDIA_BACKENDS,
    build_media_response,
    ensure_media_root,
)
from services.auth_sessions import token_is_revoked
from services.admin_bootstrap import ensure_configured_admins

# Load environment variables
load_dotenv()

LOCAL_ORIGIN_MARKERS = {'localhost', '127.0.0.1', '0.0.0.0'}
PLACEHOLDER_CONFIG_MARKERS = ('your_', 'your-', 'replace-', 'example', 'changeme')


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _path_is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _is_https_public_url(value: str | None) -> bool:
    parsed = urlparse((value or '').strip())
    host = (parsed.hostname or '').lower()
    return parsed.scheme == 'https' and bool(parsed.netloc) and host not in LOCAL_ORIGIN_MARKERS


def _looks_like_placeholder_config(value: str | None) -> bool:
    normalised = (value or '').strip().lower()
    return not normalised or any(marker in normalised for marker in PLACEHOLDER_CONFIG_MARKERS)


def _apply_security_headers(response, *, app_environment: str):
    """Apply conservative API security headers without exposing app internals."""
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    response.headers.setdefault(
        'Permissions-Policy',
        'camera=(), microphone=(), geolocation=(), payment=()',
    )
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    )
    if app_environment == 'production':
        response.headers.setdefault(
            'Strict-Transport-Security',
            'max-age=31536000; includeSubDomains',
        )
    return response


def _ensure_nltk_data() -> None:
    """Check local NLTK resources without blocking app startup on network downloads."""
    resources = {
        'punkt': 'tokenizers/punkt',
        'punkt_tab': 'tokenizers/punkt_tab',
        'averaged_perceptron_tagger': 'taggers/averaged_perceptron_tagger',
        'averaged_perceptron_tagger_eng': 'taggers/averaged_perceptron_tagger_eng',
        'maxent_ne_chunker': 'chunkers/maxent_ne_chunker',
        'maxent_ne_chunker_tab': 'chunkers/maxent_ne_chunker_tab',
        'words': 'corpora/words',
    }

    try:
        import nltk
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning('NLTK unavailable; enrichment disabled: %s', exc)
        return

    missing: list[str] = []
    for package, resource_path in resources.items():
        try:
            nltk.data.find(resource_path)
        except LookupError:
            missing.append(package)

    if not missing:
        return

    if not _env_flag('OPENMYND_AUTO_DOWNLOAD_NLTK', default=False):
        logging.getLogger(__name__).warning(
            'NLTK data missing (%s); startup downloads are disabled. '
            'Set OPENMYND_AUTO_DOWNLOAD_NLTK=true or run the NLTK setup manually.',
            ', '.join(missing),
        )
        return

    for package in missing:
        try:
            nltk.download(package, quiet=True)
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                'NLTK package download failed for %s: %s',
                package,
                exc,
            )


def _bootstrap_admin_entitlements(app: Flask) -> None:
    """Grant administrator entitlement to explicitly configured usernames/emails."""
    try:
        with app.config['DATABASE_ADAPTER'].connect(timeout=10) as conn:
            ensure_configured_admins(conn, app.logger)
    except Exception as exc:  # noqa: BLE001
        app.logger.warning('Bootstrap admin entitlement skipped: %s', exc)


def _production_runtime_blockers(
    *,
    database_provider: str,
    runtime_migrations_enabled: bool,
    media_root_value: str | None,
    resolved_media_root: str,
    media_storage_backend: str,
    r2_endpoint_url: str,
    r2_access_key_id: str,
    r2_secret_access_key: str,
    r2_bucket_name: str,
    app_root_path: str,
    cors_origins: list[str],
    frontend_base_url: str,
    oauth_google_client_id: str,
    oauth_google_client_secret: str,
    oauth_google_redirect_uri: str,
    rate_limit_storage_uri: str,
    shared_rate_limiting_deferred: bool,
    email_provider: str,
    email_delivery_deferred: bool,
    email_from_configured: bool,
    smtp_host_configured: bool,
) -> list[str]:
    blockers: list[str] = []

    if database_provider == SQLITE_PROVIDER and not _env_flag(
        'OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK',
        default=False,
    ):
        blockers.append(
            'DATABASE_PROVIDER=sqlite is blocked when APP_ENV=production. '
            'Use DATABASE_PROVIDER=postgres for public production, or set '
            'OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK=true only for a documented '
            'emergency rollback window.'
        )

    if database_provider == POSTGRES_PROVIDER and runtime_migrations_enabled:
        blockers.append('Runtime SQLite migrations must be disabled for Postgres production.')

    if runtime_migrations_enabled and not _env_flag(
        'OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION',
        default=False,
    ):
        blockers.append(
            'Runtime database migrations are blocked when APP_ENV=production. '
            'Run explicit migration tooling before startup, or opt in only for a '
            'controlled emergency fallback.'
        )

    media_storage_backend = (media_storage_backend or LOCAL_MEDIA_BACKEND).strip().lower()
    if media_storage_backend not in SUPPORTED_MEDIA_BACKENDS:
        blockers.append(
            'MEDIA_STORAGE_BACKEND must be one of: '
            f"{', '.join(sorted(SUPPORTED_MEDIA_BACKENDS))}."
        )
    elif media_storage_backend == R2_MEDIA_BACKEND:
        if not all(
            value.strip()
            for value in (
                r2_endpoint_url,
                r2_access_key_id,
                r2_secret_access_key,
                r2_bucket_name,
            )
        ):
            blockers.append(
                'R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and '
                'R2_BUCKET_NAME must be configured when MEDIA_STORAGE_BACKEND=r2.'
            )
    else:
        media_root_value = (media_root_value or '').strip()
        media_root_path = Path(resolved_media_root)
        repo_root = Path(app_root_path).resolve().parent
        media_root_inside_repo = _path_is_within(media_root_path, repo_root)
        if not media_root_value:
            blockers.append(
                'MEDIA_ROOT must be explicit when APP_ENV=production; do not use the '
                'repository-local media directory for public production.'
            )
        elif not Path(media_root_value).expanduser().is_absolute():
            blockers.append(
                'MEDIA_ROOT must be an absolute path when APP_ENV=production.'
            )
        elif media_root_inside_repo:
            blockers.append(
                'MEDIA_ROOT must not point inside the repository source tree when '
                'APP_ENV=production.'
            )

    if rate_limit_storage_uri == 'memory://' and not shared_rate_limiting_deferred:
        blockers.append(
            'RATELIMIT_STORAGE_URI=memory:// is blocked when APP_ENV=production. '
            'Use Redis or another shared limiter backend.'
        )

    if not cors_origins or '*' in cors_origins or any(
        marker in origin
        for origin in cors_origins
        for marker in ('localhost', '127.0.0.1', '0.0.0.0')
    ):
        blockers.append(
            'CORS_ORIGINS must contain only production frontend origins when APP_ENV=production.'
        )
    elif any(not origin.startswith('https://') for origin in cors_origins):
        blockers.append(
            'CORS_ORIGINS must contain only HTTPS frontend origins when APP_ENV=production.'
        )

    if not _is_https_public_url(frontend_base_url):
        blockers.append(
            'FRONTEND_BASE_URL must be an HTTPS production URL when APP_ENV=production.'
        )

    oauth_google_values = (
        oauth_google_client_id.strip(),
        oauth_google_client_secret.strip(),
        oauth_google_redirect_uri.strip(),
    )
    if any(oauth_google_values):
        if any(_looks_like_placeholder_config(value) for value in oauth_google_values):
            blockers.append(
                'Google OAuth production configuration must not be blank or placeholder values.'
            )
        elif not _is_https_public_url(oauth_google_redirect_uri):
            blockers.append(
                'OAUTH_GOOGLE_REDIRECT_URI must be an HTTPS production callback URL.'
            )

    if email_delivery_deferred:
        return blockers

    if email_provider == 'console':
        blockers.append(
            'EMAIL_PROVIDER=console is blocked when APP_ENV=production. '
            'Use EMAIL_PROVIDER=smtp for verification and password recovery.'
        )
    elif email_provider != 'smtp':
        blockers.append('EMAIL_PROVIDER must be smtp when APP_ENV=production.')

    if not email_from_configured:
        blockers.append('EMAIL_FROM_ADDRESS must be configured when APP_ENV=production.')

    if email_provider == 'smtp' and not smtp_host_configured:
        blockers.append('SMTP_HOST must be configured when EMAIL_PROVIDER=smtp.')

    return blockers


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
        ensure_auth_identities_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime auth identities migration skipped due to error: %s', migration_exc)

    try:
        ensure_account_security_tokens_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning(
            'Runtime account security token migration skipped due to error: %s',
            migration_exc,
        )

    try:
        ensure_auth_sessions_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime auth session migration skipped due to error: %s', migration_exc)

    try:
        ensure_billing_tables(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime billing table migration skipped due to error: %s', migration_exc)

    try:
        ensure_admin_announcement_tables(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime admin announcement migration skipped due to error: %s', migration_exc)

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
        ensure_security_audit_events_table(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime security audit migration skipped due to error: %s', migration_exc)

    try:
        ensure_cbt_worksheet_tables(database_path, app.logger.info)
    except Exception as migration_exc:
        app.logger.warning('Runtime CBT worksheet migration skipped due to error: %s', migration_exc)


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)
    
    # Configuration
    default_app_environment = 'production' if os.getenv('VERCEL') else 'development'
    app_environment = (os.getenv('APP_ENV') or default_app_environment).strip().lower()
    jwt_secret = os.getenv('JWT_SECRET')
    if not jwt_secret and app_environment == 'production':
        raise RuntimeError('JWT_SECRET must be configured when APP_ENV=production')
    if app_environment == 'production' and (
        jwt_secret == 'dev-secret-key' or len(jwt_secret or '') < 32
    ):
        raise RuntimeError(
            'JWT_SECRET must not use the development fallback and must be at least '
            '32 characters when APP_ENV=production'
        )
    if not jwt_secret:
        app.logger.warning('JWT_SECRET is not configured; using local development secret')
    app.config['JWT_SECRET_KEY'] = jwt_secret or 'dev-secret-key'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400  # 24 hours
    cookie_auth_enabled = (
        os.getenv('OPENMYND_AUTH_COOKIE_MODE', '').strip().lower()
        in {'1', 'true', 'yes', 'on'}
    )
    app.config['OPENMYND_AUTH_COOKIE_MODE'] = cookie_auth_enabled
    app.config['JWT_TOKEN_LOCATION'] = (
        ['headers', 'cookies'] if cookie_auth_enabled else ['headers']
    )
    app.config['JWT_COOKIE_SECURE'] = app_environment == 'production'
    app.config['JWT_COOKIE_SAMESITE'] = os.getenv('JWT_COOKIE_SAMESITE', 'Lax')
    app.config['JWT_COOKIE_CSRF_PROTECT'] = (
        os.getenv('OPENMYND_AUTH_COOKIE_CSRF_PROTECT', '').strip().lower()
        in {'1', 'true', 'yes', 'on'}
    )
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
    shared_rate_limiting_deferred = _env_flag(
        'OPENMYND_DEFER_SHARED_RATE_LIMITING',
        default=False,
    )
    database_settings = configure_app_database(app)
    app.config['DATABASE_ADAPTER'] = DatabaseAdapter.from_settings(database_settings)
    database_path = database_settings.sqlite_path
    if database_settings.provider == SQLITE_PROVIDER and not os.path.exists(database_path):
        app.logger.warning('Database file not found at %s', database_path)

    media_storage_backend = (os.getenv('MEDIA_STORAGE_BACKEND') or LOCAL_MEDIA_BACKEND).strip().lower()
    app.config['MEDIA_STORAGE_BACKEND'] = media_storage_backend
    app.config['R2_ENDPOINT_URL'] = (os.getenv('R2_ENDPOINT_URL') or '').strip()
    app.config['R2_ACCESS_KEY_ID'] = (os.getenv('R2_ACCESS_KEY_ID') or '').strip()
    app.config['R2_SECRET_ACCESS_KEY'] = (os.getenv('R2_SECRET_ACCESS_KEY') or '').strip()
    app.config['R2_BUCKET_NAME'] = (os.getenv('R2_BUCKET_NAME') or '').strip()
    app.config['R2_PUBLIC_BASE_URL'] = (os.getenv('R2_PUBLIC_BASE_URL') or '').strip() or None

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

    cors_origins = [
        origin.strip()
        for origin in os.getenv('CORS_ORIGINS', 'http://localhost:4200').split(',')
        if origin.strip()
    ]
    frontend_base_url = (os.getenv('FRONTEND_BASE_URL') or '').strip()
    oauth_google_client_id = (os.getenv('OAUTH_GOOGLE_CLIENT_ID') or '').strip()
    oauth_google_client_secret = (os.getenv('OAUTH_GOOGLE_CLIENT_SECRET') or '').strip()
    oauth_google_redirect_uri = (os.getenv('OAUTH_GOOGLE_REDIRECT_URI') or '').strip()
    email_provider = (os.getenv('EMAIL_PROVIDER') or 'console').strip().lower()
    email_delivery_deferred = _env_flag('OPENMYND_DEFER_EMAIL_DELIVERY', default=False)
    if app_environment == 'production':
        production_blockers = _production_runtime_blockers(
            database_provider=database_settings.provider,
            runtime_migrations_enabled=database_settings.runtime_migrations_enabled,
            media_root_value=media_root,
            resolved_media_root=resolved_media_root,
            media_storage_backend=media_storage_backend,
            r2_endpoint_url=app.config['R2_ENDPOINT_URL'],
            r2_access_key_id=app.config['R2_ACCESS_KEY_ID'],
            r2_secret_access_key=app.config['R2_SECRET_ACCESS_KEY'],
            r2_bucket_name=app.config['R2_BUCKET_NAME'],
            app_root_path=app.root_path,
            cors_origins=cors_origins,
            frontend_base_url=frontend_base_url,
            oauth_google_client_id=oauth_google_client_id,
            oauth_google_client_secret=oauth_google_client_secret,
            oauth_google_redirect_uri=oauth_google_redirect_uri,
            rate_limit_storage_uri=app.config['RATELIMIT_STORAGE_URI'],
            shared_rate_limiting_deferred=shared_rate_limiting_deferred,
            email_provider=email_provider,
            email_delivery_deferred=email_delivery_deferred,
            email_from_configured=bool((os.getenv('EMAIL_FROM_ADDRESS') or '').strip()),
            smtp_host_configured=bool((os.getenv('SMTP_HOST') or '').strip()),
        )
        if production_blockers:
            raise RuntimeError(
                'Unsafe production runtime configuration: '
                + ' '.join(production_blockers)
            )

    if app.config['DATABASE_RUNTIME_MIGRATIONS_ENABLED']:
        _run_sqlite_runtime_migrations(app, database_path)
    else:
        app.logger.info(
            'Runtime SQLite migrations disabled for provider: %s',
            app.config['DATABASE_PROVIDER'],
        )
    _bootstrap_admin_entitlements(app)
    
    # CORS configuration
    CORS(app, origins=cors_origins, supports_credentials=True)
    
    # JWT initialisation
    jwt = JWTManager(app)
    limiter.init_app(app)
    # --- DEBUG: helpful JWT logging for local development ---
    # These handlers will log common JWT errors so the developer can
    # see why a token was rejected (missing, expired, invalid signature).

    @app.before_request
    def _start_request_timer():
        request._openmynd_started_at = time.perf_counter()

    @app.after_request
    def _set_security_and_timing_headers(response):
        response = _apply_security_headers(response, app_environment=app_environment)
        started_at = getattr(request, '_openmynd_started_at', None)
        if started_at is not None:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            response.headers['Server-Timing'] = f'app;dur={duration_ms}'
            response.headers['X-OpenMynd-Request-Duration-Ms'] = str(duration_ms)
            try:
                slow_threshold_ms = int(os.getenv('SLOW_REQUEST_LOG_MS', '1500'))
            except (TypeError, ValueError):
                slow_threshold_ms = 1500
            if request.path.startswith('/api/') and duration_ms >= slow_threshold_ms:
                app.logger.warning(
                    'Slow API request: method=%s path=%s status=%s duration_ms=%.2f',
                    request.method,
                    request.path,
                    response.status_code,
                    duration_ms,
                )
        return response

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

    @app.errorhandler(Exception)
    def _handle_unexpected_exception(err):
        if isinstance(err, HTTPException):
            return err

        database_operation = 'read' if request.method in READ_METHODS else 'write'
        database_failure = classify_database_exception(
            err,
            operation=database_operation,
        )
        if database_failure:
            app.logger.error(
                'Database failure classified: category=%s code=%s operation=%s provider=%s path=%s error_type=%s',
                database_failure.category,
                database_failure.code,
                database_operation,
                app.config.get('DATABASE_PROVIDER', 'unknown'),
                request.path,
                err.__class__.__name__,
            )
            return jsonify({
                'error': database_failure.user_message,
                'code': database_failure.code,
                'category': database_failure.category,
            }), database_failure.status_code

        app.logger.exception('Unhandled application exception on %s', request.path)
        return {'msg': 'Internal Server Error'}, 500

    @app.errorhandler(RateLimitExceeded)
    def _handle_rate_limit(_err):
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
        return {'error': 'Too many attempts. Try again shortly.'}, 429

    @jwt.token_in_blocklist_loader
    def _jwt_token_is_revoked(_jwt_header, jwt_payload):
        jwt_jti = str(jwt_payload.get('jti') or '').strip()
        if not jwt_jti:
            return True
        try:
            with app.config['DATABASE_ADAPTER'].connect(timeout=5) as conn:
                return token_is_revoked(conn, jwt_jti)
        except Exception as exc:  # noqa: BLE001
            app.logger.warning('JWT revocation check failed: %s', exc)
            return app_environment == 'production'

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

    @app.before_request
    def _enforce_onboarding_completion():
        if request.method == 'OPTIONS':
            return None
        if not request.path.startswith('/api/'):
            return None

        allowed_prefixes = (
            '/api/login',
            '/api/register',
            '/api/oauth/',
        )
        if request.path.startswith(allowed_prefixes):
            return None

        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
        except Exception:
            # Let route-level jwt_required produce the canonical auth failure.
            return None
        if identity is None:
            return None

        try:
            user_id = int(identity)
        except (TypeError, ValueError):
            return None

        try:
            adapter = app.config['DATABASE_ADAPTER']
            with adapter.connect() as conn:
                user_columns = adapter.table_columns(conn, 'users')
                account_status_expr = (
                    'account_status'
                    if 'account_status' in user_columns
                    else "'active' AS account_status"
                )
                row = conn.execute(
                    f'''
                    SELECT onboarding_completed, {account_status_expr}
                    FROM users
                    WHERE id = ?
                    ''',
                    (user_id,),
                ).fetchone()
        except Exception as exc:
            app.logger.warning('Onboarding gate check failed: %s', exc)
            return None

        if row is not None and str(row['account_status'] or 'active').lower() == 'restricted':
            restricted_allowed = (
                request.path == '/api/profile/account'
                and request.method == 'DELETE'
            ) or (
                request.path == '/api/import/export'
                and request.method == 'GET'
            )
            if not restricted_allowed:
                return jsonify({
                    'error': 'This account has been restricted. Contact the OpenMynd administrator for access.',
                    'code': 'account_restricted',
                }), 403

        if request.path.startswith('/api/profile'):
            return None

        if row is not None and not bool(row['onboarding_completed']):
            return jsonify({
                'error': 'Account setup is required before using OpenMynd.',
                'code': 'onboarding_required',
            }), 403

        return None
    
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
    from routes.dashboard import dashboard_bp
    from routes.billing import billing_bp
    from routes.admin import admin_bp
    
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
    app.register_blueprint(dashboard_bp, url_prefix='/api')
    app.register_blueprint(billing_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')

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
        write = str(request.args.get('write') or '').strip().lower() in {'1', 'true', 'yes'}
        include_schema = str(request.args.get('schema') or '').strip().lower() in {'1', 'true', 'yes'}
        report = app.config['DATABASE_ADAPTER'].health_check(write=write)
        if include_schema and hasattr(app.config['DATABASE_ADAPTER'], 'schema_readiness'):
            schema_report = app.config['DATABASE_ADAPTER'].schema_readiness()
            report['schema'] = schema_report
            if schema_report.get('ok') is not True:
                report['ok'] = False
        report['environment'] = {
            'app_env': app_environment,
            'vercel': bool(os.getenv('VERCEL')),
            'vercel_env': (os.getenv('VERCEL_ENV') or '').strip() or None,
            'vercel_git_commit_sha': (os.getenv('VERCEL_GIT_COMMIT_SHA') or '').strip()[:12] or None,
            'database_provider_env': (os.getenv('DATABASE_PROVIDER') or '').strip() or None,
            'database_url_present': bool((os.getenv('DATABASE_URL') or '').strip()),
            'database_url_is_postgres': (os.getenv('DATABASE_URL') or '')
            .strip()
            .lower()
            .startswith(('postgres://', 'postgresql://')),
            'media_storage_backend': app.config.get('MEDIA_STORAGE_BACKEND'),
        }
        startup_migration_result = app.config.get('POSTGRES_STARTUP_MIGRATION_RESULT')
        if startup_migration_result is not None:
            report['startup_migrations'] = startup_migration_result
        return report, 200 if report.get('ok') is True else 503

    @app.route(f'{DEFAULT_MEDIA_URL_PREFIX}/<path:storage_key>')
    def serve_media(storage_key: str):
        if app.config.get('MEDIA_STORAGE_BACKEND') == R2_MEDIA_BACKEND:
            response = build_media_response(storage_key)
            if response is None:
                return jsonify({'error': 'Media not found'}), 404
            return response
        return send_from_directory(app.config['MEDIA_ROOT'], storage_key, conditional=True)

    # Check NLTK data and optionally backfill entries imported before enrichment was available.
    # This legacy backfill is SQLite-only; managed/cloud databases should be migrated explicitly.
    _ensure_nltk_data()
    if (
        app.config['DATABASE_RUNTIME_MIGRATIONS_ENABLED']
        and _env_flag('OPENMYND_STARTUP_NLTK_BACKFILL', default=False)
    ):
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
