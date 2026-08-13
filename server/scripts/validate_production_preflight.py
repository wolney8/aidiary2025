"""Validate production/cloud runtime configuration before deployment.

This is intentionally configuration-only. It does not connect to Postgres or
start the Flask app, so it can run safely in CI before a cutover attempt.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, urlparse

from services.database import SUPPORTED_DATABASE_PROVIDERS, resolve_database_settings


LOCAL_ORIGIN_MARKERS = ("localhost", "127.0.0.1", "0.0.0.0")
PLACEHOLDER_MARKERS = ("your_", "your-", "replace-", "example", "changeme")
PUBLIC_LEGAL_ROUTES = (
    "client/src/app/legal/legal-page.component.ts",
    "client/src/app/shared/components/cookie-consent/cookie-consent.component.ts",
)
FRONTEND_PRODUCTION_ENV_PATH = "client/src/environments/environment.prod.ts"
PUBLIC_FRONTEND_ROUTES = ("privacy", "terms", "cookies")
PROCESS_SUPERVISION_FILES = (
    "wsgi.py",
    "gunicorn.conf.py",
    "scripts/healthcheck.py",
)
AUTH_RATE_LIMIT_ENV_KEYS = (
    "AUTH_LOGIN_RATE_LIMIT",
    "AUTH_REGISTER_RATE_LIMIT",
    "AUTH_PASSWORD_RESET_RATE_LIMIT",
    "AUTH_EMAIL_VERIFICATION_RATE_LIMIT",
    "AUTH_OAUTH_START_RATE_LIMIT",
    "AUTH_OAUTH_CALLBACK_RATE_LIMIT",
)
SENSITIVE_RATE_LIMIT_ENV_KEYS = AUTH_RATE_LIMIT_ENV_KEYS + (
    "ANALYSE_RATE_LIMIT",
    "IMPORT_UPLOAD_RATE_LIMIT",
    "IMPORT_COMMIT_RATE_LIMIT",
    "IMPORT_JOB_RATE_LIMIT",
    "IMPORT_REVERT_RATE_LIMIT",
    "EXPORT_RATE_LIMIT",
    "ACCOUNT_DELETE_RATE_LIMIT",
)
MIN_SECURITY_AUDIT_RETENTION_DAYS = 30
MAX_SECURITY_AUDIT_RETENTION_DAYS = 730


def _add_gate(
    collection: list[dict[str, str]],
    *,
    gate: str,
    message: str,
    severity: str = "blocker",
) -> None:
    collection.append({"gate": gate, "severity": severity, "message": message})


def _looks_like_postgres_url(database_url: str | None) -> bool:
    if not database_url:
        return False
    return database_url.startswith(("postgresql://", "postgres://"))


def _postgres_url_uses_disabled_ssl(database_url: str | None) -> bool:
    if not database_url:
        return False
    query = parse_qs(urlparse(database_url).query)
    sslmode_values = [value.lower() for value in query.get("sslmode", [])]
    return "disable" in sslmode_values


def _postgres_url_has_pooler_signal(
    database_url: str | None,
    env: Mapping[str, str],
) -> bool:
    if (env.get("DATABASE_USES_POOLER") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return True
    if not database_url:
        return False
    parsed = urlparse(database_url)
    host = (parsed.hostname or "").lower()
    query = parse_qs(parsed.query)
    query_keys = {key.lower() for key in query}
    return (
        "pooler" in host
        or "pgbouncer" in host
        or "pool" in host
        or "pgbouncer" in query_keys
    )


def _looks_like_https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _is_local_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return any(marker == host for marker in LOCAL_ORIGIN_MARKERS)


def _looks_like_placeholder(value: str | None) -> bool:
    normalised = (value or "").strip().lower()
    return not normalised or any(marker in normalised for marker in PLACEHOLDER_MARKERS)


def _path_is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _looks_like_prefixed_secret(value: str | None, prefix: str) -> bool:
    normalised = (value or "").strip()
    return normalised.startswith(prefix) and not _looks_like_placeholder(normalised)


def _email_provider(env: Mapping[str, str]) -> str:
    return (env.get("EMAIL_PROVIDER") or "console").strip().lower()


def _env_flag(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _frontend_cookie_only_auth_enabled(repo_root: Path) -> bool | None:
    environment_path = repo_root / FRONTEND_PRODUCTION_ENV_PATH
    if not environment_path.exists():
        return None
    source = environment_path.read_text(encoding="utf-8")
    compact_source = "".join(source.split())
    if "cookieOnlyAuth:true" in compact_source:
        return True
    if "cookieOnlyAuth:false" in compact_source:
        return False
    return None


def _parse_positive_int(value: str | None) -> int | None:
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _app_declares_health_routes(app_path: Path) -> bool:
    if not app_path.exists():
        return False
    source = app_path.read_text(encoding="utf-8")
    return "/health" in source and "/api/health/database" in source


def build_production_preflight(
    *,
    root_path: Path,
    environ: Mapping[str, str] | None = None,
    require_postgres: bool = False,
) -> dict[str, object]:
    env = os.environ if environ is None else environ
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    app_env = (env.get("APP_ENV") or "").strip().lower()
    if app_env != "production":
        _add_gate(
            warnings,
            gate="app_env",
            severity="warning",
            message="APP_ENV is not set to production.",
        )

    jwt_secret = (env.get("JWT_SECRET") or "").strip()
    if not jwt_secret:
        _add_gate(
            blockers,
            gate="jwt_secret",
            message="JWT_SECRET must be configured before production deployment.",
        )
    elif jwt_secret == "dev-secret-key" or len(jwt_secret) < 32:
        _add_gate(
            blockers,
            gate="jwt_secret_strength",
            message="JWT_SECRET must not use the development fallback and should be at least 32 characters.",
        )

    provider = (env.get("DATABASE_PROVIDER") or "").strip().lower()
    if not provider:
        _add_gate(
            blockers,
            gate="database_provider",
            message="DATABASE_PROVIDER must be explicit for production/cutover checks.",
        )
    elif provider not in SUPPORTED_DATABASE_PROVIDERS:
        _add_gate(
            blockers,
            gate="database_provider",
            message=f"DATABASE_PROVIDER must be one of: {', '.join(sorted(SUPPORTED_DATABASE_PROVIDERS))}.",
        )

    try:
        database_settings = resolve_database_settings(str(root_path), env)
    except RuntimeError as exc:
        database_settings = None
        _add_gate(blockers, gate="database_settings", message=str(exc))

    database_url = (env.get("DATABASE_URL") or "").strip() or None
    allow_sqlite_fallback = _env_flag(
        env,
        "OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK",
    )
    allow_runtime_migrations = _env_flag(
        env,
        "OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION",
    )

    if app_env == "production" and provider == "sqlite" and not allow_sqlite_fallback:
        _add_gate(
            blockers,
            gate="production_database_provider",
            message=(
                "APP_ENV=production requires DATABASE_PROVIDER=postgres unless "
                "OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK=true is set for a documented rollback window."
            ),
        )

    if (
        app_env == "production"
        and database_settings
        and database_settings.runtime_migrations_enabled
        and not allow_runtime_migrations
    ):
        _add_gate(
            blockers,
            gate="production_runtime_migrations",
            message=(
                "Runtime database migrations are blocked in production. "
                "Run explicit migration tooling before startup."
            ),
        )

    if require_postgres:
        if provider != "postgres":
            _add_gate(
                blockers,
                gate="postgres_provider",
                message="Cloud cutover preflight requires DATABASE_PROVIDER=postgres.",
            )
        if not _looks_like_postgres_url(database_url):
            _add_gate(
                blockers,
                gate="database_url",
                message="DATABASE_URL must be a postgres/postgresql connection string.",
            )
        elif _postgres_url_uses_disabled_ssl(database_url):
            _add_gate(
                blockers,
                gate="database_url_ssl",
                message="DATABASE_URL must not disable SSL for cloud Postgres cutover.",
            )
        elif not _postgres_url_has_pooler_signal(database_url, env):
            _add_gate(
                warnings,
                gate="database_pooling",
                severity="warning",
                message=(
                    "Postgres cutover should use a pooled connection URL or set "
                    "DATABASE_USES_POOLER=true after confirming provider pooling."
                ),
            )
        if database_settings and database_settings.runtime_migrations_enabled:
            _add_gate(
                blockers,
                gate="runtime_migrations",
                message="SQLite runtime migrations must be disabled for Postgres cutover.",
            )

    cors_origins = [
        origin.strip()
        for origin in (env.get("CORS_ORIGINS") or "").split(",")
        if origin.strip()
    ]
    if not cors_origins:
        _add_gate(
            blockers,
            gate="cors_origins",
            message="CORS_ORIGINS must include the production frontend origin.",
        )
    elif "*" in cors_origins or any(
        marker in origin for origin in cors_origins for marker in LOCAL_ORIGIN_MARKERS
    ):
        _add_gate(
            blockers,
            gate="cors_origins",
            message="CORS_ORIGINS must not use wildcard or localhost origins for production.",
        )

    frontend_base_url = (env.get("FRONTEND_BASE_URL") or "").strip()
    if app_env == "production":
        if not _looks_like_https_url(frontend_base_url):
            _add_gate(
                blockers,
                gate="frontend_base_url",
                message="FRONTEND_BASE_URL must be an HTTPS production URL.",
            )
        elif _is_local_url(frontend_base_url):
            _add_gate(
                blockers,
                gate="frontend_base_url",
                message="FRONTEND_BASE_URL must not point at localhost for production.",
            )
    elif not frontend_base_url:
        _add_gate(
            warnings,
            gate="frontend_base_url",
            severity="warning",
            message="FRONTEND_BASE_URL should be explicit before deployment rehearsal.",
        )

    oauth_google_client_id = (env.get("OAUTH_GOOGLE_CLIENT_ID") or "").strip()
    oauth_google_client_secret = (env.get("OAUTH_GOOGLE_CLIENT_SECRET") or "").strip()
    oauth_google_redirect_uri = (env.get("OAUTH_GOOGLE_REDIRECT_URI") or "").strip()
    oauth_google_configured = any(
        value
        for value in (
            oauth_google_client_id,
            oauth_google_client_secret,
            oauth_google_redirect_uri,
        )
    )
    if app_env == "production" and oauth_google_configured:
        if (
            _looks_like_placeholder(oauth_google_client_id)
            or _looks_like_placeholder(oauth_google_client_secret)
            or _looks_like_placeholder(oauth_google_redirect_uri)
        ):
            _add_gate(
                blockers,
                gate="oauth_google_configuration",
                message="Google OAuth production configuration must not be blank or placeholder values.",
            )
        elif not _looks_like_https_url(oauth_google_redirect_uri) or _is_local_url(oauth_google_redirect_uri):
            _add_gate(
                blockers,
                gate="oauth_google_redirect_uri",
                message="OAUTH_GOOGLE_REDIRECT_URI must be an HTTPS production callback URL.",
            )

    email_provider = _email_provider(env)
    email_from_address = (env.get("EMAIL_FROM_ADDRESS") or "").strip()
    smtp_host = (env.get("SMTP_HOST") or "").strip()
    if app_env == "production":
        if email_provider == "console":
            _add_gate(
                blockers,
                gate="transactional_email_provider",
                message=(
                    "EMAIL_PROVIDER=console is blocked in production. "
                    "Configure EMAIL_PROVIDER=smtp and SMTP delivery settings."
                ),
            )
        elif email_provider != "smtp":
            _add_gate(
                blockers,
                gate="transactional_email_provider",
                message="EMAIL_PROVIDER must be smtp for production account recovery.",
            )
        if _looks_like_placeholder(email_from_address):
            _add_gate(
                blockers,
                gate="transactional_email_from",
                message="EMAIL_FROM_ADDRESS must be a real sender before production deployment.",
            )
        if email_provider == "smtp" and _looks_like_placeholder(smtp_host):
            _add_gate(
                blockers,
                gate="transactional_email_smtp_host",
                message="SMTP_HOST must be configured when EMAIL_PROVIDER=smtp.",
            )
        if not _env_flag(env, "OPENMYND_REQUIRE_REGISTRATION_EMAIL"):
            _add_gate(
                warnings,
                gate="registration_email_required",
                severity="warning",
                message=(
                    "OPENMYND_REQUIRE_REGISTRATION_EMAIL should be true before public launch "
                    "so local accounts can verify email and recover passwords."
                ),
            )

    repo_root = root_path.parent
    frontend_tree_available = (repo_root / "client").exists()
    frontend_cookie_only_auth_enabled = (
        _frontend_cookie_only_auth_enabled(repo_root)
        if frontend_tree_available
        else None
    )

    cookie_auth_mode = _env_flag(env, "OPENMYND_AUTH_COOKIE_MODE")
    cookie_csrf_protect = _env_flag(env, "OPENMYND_AUTH_COOKIE_CSRF_PROTECT")
    localstorage_jwt_risk_present = frontend_cookie_only_auth_enabled is not True
    if (
        app_env == "production"
        and localstorage_jwt_risk_present
        and not _env_flag(env, "OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK")
    ):
        _add_gate(
            warnings,
            gate="jwt_browser_storage_review",
            severity="warning",
            message=(
                "The production frontend is not confirmed as cookie-only, so "
                "browser bearer tokens may be stored in localStorage. Set "
                "OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK=true only after the "
                "launch owner accepts this risk or ships a cookie/session redesign."
            ),
        )
    if app_env == "production" and cookie_auth_mode and frontend_cookie_only_auth_enabled is False:
        _add_gate(
            warnings,
            gate="cookie_auth_frontend_mode",
            severity="warning",
            message=(
                "OPENMYND_AUTH_COOKIE_MODE is enabled, but the production frontend has cookieOnlyAuth=false. "
                "This is additive cookie mode, not a cookie-only launch posture."
            ),
        )
    if app_env == "production" and cookie_auth_mode and not cookie_csrf_protect:
        _add_gate(
            warnings,
            gate="cookie_auth_csrf",
            severity="warning",
            message=(
                "OPENMYND_AUTH_COOKIE_MODE is enabled without "
                "OPENMYND_AUTH_COOKIE_CSRF_PROTECT. This is only acceptable during "
                "the staged migration before cookie-only launch."
            ),
        )

    legacy_password_fallback_disabled = _env_flag(
        env,
        "OPENMYND_DISABLE_LEGACY_PASSWORD_FALLBACK",
    )
    if (
        app_env == "production"
        and not legacy_password_fallback_disabled
        and not _env_flag(env, "OPENMYND_ACCEPT_LEGACY_PASSWORD_FALLBACK")
    ):
        _add_gate(
            warnings,
            gate="legacy_password_fallback_review",
            severity="warning",
            message=(
                "Legacy plaintext-password fallback remains enabled. "
                "Set OPENMYND_ACCEPT_LEGACY_PASSWORD_FALLBACK=true only for a documented migration window."
            ),
        )

    missing_legal_sources = []
    if frontend_tree_available:
        missing_legal_sources = [
            path
            for path in PUBLIC_LEGAL_ROUTES
            if not (repo_root / path).exists()
        ]
    else:
        _add_gate(
            warnings,
            gate="legal_privacy_routes",
            severity="warning",
            message="Frontend legal/cookie route sources were not available to this preflight run.",
        )
    if frontend_tree_available and missing_legal_sources:
        _add_gate(
            blockers,
            gate="legal_privacy_routes",
            message=(
                "Public legal/cookie source files are missing: "
                + ", ".join(missing_legal_sources)
            ),
        )

    missing_frontend_routes: list[str] = []
    app_routes_path = repo_root / "client/src/app/app.routes.ts"
    if frontend_tree_available and app_routes_path.exists():
        route_source = app_routes_path.read_text(encoding="utf-8")
        missing_frontend_routes = [
            route
            for route in PUBLIC_FRONTEND_ROUTES
            if f'path: "{route}"' not in route_source and f"path: '{route}'" not in route_source
        ]
        if missing_frontend_routes:
            _add_gate(
                blockers,
                gate="public_frontend_routes",
                message=(
                    "Public frontend routes are missing from app.routes.ts: "
                    + ", ".join(missing_frontend_routes)
                ),
            )
    elif frontend_tree_available:
        _add_gate(
            blockers,
            gate="public_frontend_routes",
            message="client/src/app/app.routes.ts is missing, so public route readiness cannot be checked.",
        )

    stripe_secret_key = (env.get("STRIPE_SECRET_KEY") or "").strip()
    stripe_webhook_secret = (env.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    stripe_price_personal_legacy = (env.get("STRIPE_PRICE_PERSONAL") or "").strip()
    stripe_price_plus_legacy = (env.get("STRIPE_PRICE_PLUS") or "").strip()
    stripe_price_personal_monthly = (
        (env.get("STRIPE_PRICE_PERSONAL_MONTHLY") or "").strip()
        or stripe_price_personal_legacy
    )
    stripe_price_personal_annual = (
        env.get("STRIPE_PRICE_PERSONAL_ANNUAL") or ""
    ).strip()
    stripe_price_plus_monthly = (
        (env.get("STRIPE_PRICE_PLUS_MONTHLY") or "").strip()
        or stripe_price_plus_legacy
    )
    stripe_price_plus_annual = (env.get("STRIPE_PRICE_PLUS_ANNUAL") or "").strip()
    stripe_values = {
        "STRIPE_SECRET_KEY": stripe_secret_key,
        "STRIPE_WEBHOOK_SECRET": stripe_webhook_secret,
        "STRIPE_PRICE_PERSONAL_MONTHLY": stripe_price_personal_monthly,
        "STRIPE_PRICE_PERSONAL_ANNUAL": stripe_price_personal_annual,
        "STRIPE_PRICE_PLUS_MONTHLY": stripe_price_plus_monthly,
        "STRIPE_PRICE_PLUS_ANNUAL": stripe_price_plus_annual,
    }
    stripe_price_inputs = {
        "STRIPE_PRICE_PERSONAL": stripe_price_personal_legacy,
        "STRIPE_PRICE_PLUS": stripe_price_plus_legacy,
        "STRIPE_PRICE_PERSONAL_MONTHLY": (
            env.get("STRIPE_PRICE_PERSONAL_MONTHLY") or ""
        ).strip(),
        "STRIPE_PRICE_PERSONAL_ANNUAL": stripe_price_personal_annual,
        "STRIPE_PRICE_PLUS_MONTHLY": (
            env.get("STRIPE_PRICE_PLUS_MONTHLY") or ""
        ).strip(),
        "STRIPE_PRICE_PLUS_ANNUAL": stripe_price_plus_annual,
    }
    stripe_partially_configured = any(stripe_values.values()) or any(
        stripe_price_inputs.values()
    )
    if app_env == "production":
        missing_stripe_values = [
            key for key, value in stripe_values.items() if _looks_like_placeholder(value)
        ]
        if stripe_partially_configured and missing_stripe_values:
            _add_gate(
                blockers,
                gate="stripe_configuration",
                message=(
                    "Stripe billing configuration is incomplete: "
                    + ", ".join(missing_stripe_values)
                ),
            )
        if stripe_secret_key and not _looks_like_prefixed_secret(stripe_secret_key, "sk_"):
            _add_gate(
                blockers,
                gate="stripe_secret_key",
                message="STRIPE_SECRET_KEY must look like a Stripe secret key.",
            )
        if stripe_webhook_secret and not _looks_like_prefixed_secret(stripe_webhook_secret, "whsec_"):
            _add_gate(
                blockers,
                gate="stripe_webhook_secret",
                message="STRIPE_WEBHOOK_SECRET must look like a Stripe webhook signing secret.",
            )
        for tier_key, price_value in stripe_price_inputs.items():
            if price_value and not _looks_like_prefixed_secret(price_value, "price_"):
                _add_gate(
                    blockers,
                    gate=tier_key.lower(),
                    message=f"{tier_key} must look like a Stripe Price ID.",
                )

    media_root = (env.get("MEDIA_ROOT") or "").strip()
    media_base_url = (env.get("MEDIA_BASE_URL") or "").strip()
    media_root_path = Path(media_root).expanduser() if media_root else None
    repo_root = root_path.resolve().parent
    media_root_is_absolute = bool(media_root_path and media_root_path.is_absolute())
    media_root_inside_repo = bool(
        media_root_path and media_root_is_absolute and _path_is_within(media_root_path, repo_root)
    )
    if app_env == "production" and not media_root:
        _add_gate(
            blockers,
            gate="media_storage",
            message=(
                "MEDIA_ROOT must be explicit before production deployment; do not use "
                "the repository-local media directory."
            ),
        )
    elif app_env == "production" and not media_root_is_absolute:
        _add_gate(
            blockers,
            gate="media_storage_path",
            message="MEDIA_ROOT must be an absolute path for production deployment.",
        )
    elif app_env == "production" and media_root_inside_repo:
        _add_gate(
            blockers,
            gate="media_storage_path",
            message=(
                "MEDIA_ROOT must not point inside the repository source tree for "
                "production deployment."
            ),
        )
    elif not media_root and not media_base_url:
        _add_gate(
            warnings,
            gate="media_storage",
            severity="warning",
            message="MEDIA_ROOT or MEDIA_BASE_URL should be explicit before production deployment.",
        )

    rate_limit_storage_uri = (env.get("RATELIMIT_STORAGE_URI") or "memory://").strip()
    if app_env == "production" and rate_limit_storage_uri == "memory://":
        _add_gate(
            blockers,
            gate="rate_limit_storage",
            message=(
                "RATELIMIT_STORAGE_URI=memory:// is not safe for production; use Redis or another shared limiter backend."
            ),
        )

    configured_sensitive_rate_limits = {
        key: bool((env.get(key) or "").strip())
        for key in SENSITIVE_RATE_LIMIT_ENV_KEYS
    }
    missing_auth_rate_limits = [
        key for key, configured in configured_sensitive_rate_limits.items() if not configured
    ]
    if app_env == "production" and missing_auth_rate_limits:
        _add_gate(
            warnings,
            gate="sensitive_route_rate_limits",
            severity="warning",
            message=(
                "Sensitive route rate limits should be explicit before public launch: "
                + ", ".join(missing_auth_rate_limits)
            ),
        )

    security_audit_retention_days = _parse_positive_int(
        env.get("SECURITY_AUDIT_RETENTION_DAYS")
    )
    if app_env == "production":
        if security_audit_retention_days is None:
            _add_gate(
                warnings,
                gate="security_audit_retention",
                severity="warning",
                message=(
                    "SECURITY_AUDIT_RETENTION_DAYS should be set before public launch "
                    "so audit evidence retention is explicit."
                ),
            )
        elif not (
            MIN_SECURITY_AUDIT_RETENTION_DAYS
            <= security_audit_retention_days
            <= MAX_SECURITY_AUDIT_RETENTION_DAYS
        ):
            _add_gate(
                warnings,
                gate="security_audit_retention",
                severity="warning",
                message=(
                    "SECURITY_AUDIT_RETENTION_DAYS should be between "
                    f"{MIN_SECURITY_AUDIT_RETENTION_DAYS} and "
                    f"{MAX_SECURITY_AUDIT_RETENTION_DAYS} days."
                ),
            )

    openai_key = (env.get("OPENAI_API_KEY") or "").strip()
    openai_key_configured = bool(openai_key) and not _looks_like_placeholder(openai_key)
    if not openai_key_configured:
        _add_gate(
            blockers if app_env == "production" else warnings,
            gate="openai_api_key",
            severity="blocker" if app_env == "production" else "warning",
            message=(
                "OPENAI_API_KEY must be configured with a non-placeholder backend "
                "secret before AI features can run."
            ),
        )

    missing_process_supervision_files = [
        path for path in PROCESS_SUPERVISION_FILES if not (root_path / path).exists()
    ]
    health_routes_present = _app_declares_health_routes(root_path / "app.py")
    if app_env == "production" and (
        missing_process_supervision_files or not health_routes_present
    ):
        missing_details = list(missing_process_supervision_files)
        if not health_routes_present:
            missing_details.append("app.py health routes")
        _add_gate(
            warnings,
            gate="process_supervision",
            severity="warning",
            message=(
                "Production process supervision assets or health routes are missing: "
                + ", ".join(missing_details)
            ),
        )

    return {
        "ready_for_production": not blockers,
        "require_postgres": require_postgres,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "app_env": app_env or None,
            "database_provider": provider or None,
            "database_url_configured": bool(database_url),
            "database_url_ssl_disabled": _postgres_url_uses_disabled_ssl(database_url),
            "database_pooler_configured": _postgres_url_has_pooler_signal(
                database_url,
                env,
            ),
            "sqlite_production_fallback_allowed": allow_sqlite_fallback,
            "runtime_migrations_allowed_in_production": allow_runtime_migrations,
            "cors_origins": cors_origins,
            "frontend_base_url_configured": bool(frontend_base_url),
            "frontend_base_url_https": _looks_like_https_url(frontend_base_url),
            "oauth_google_configured": oauth_google_configured,
            "oauth_google_redirect_https": _looks_like_https_url(oauth_google_redirect_uri),
            "email_provider": email_provider,
            "email_from_configured": bool(email_from_address),
            "smtp_host_configured": bool(smtp_host),
            "registration_email_required": _env_flag(env, "OPENMYND_REQUIRE_REGISTRATION_EMAIL"),
            "localstorage_jwt_risk_accepted": _env_flag(env, "OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK"),
            "cookie_auth_mode": cookie_auth_mode,
            "cookie_auth_csrf_protect": cookie_csrf_protect,
            "frontend_cookie_only_auth_enabled": frontend_cookie_only_auth_enabled,
            "legacy_password_fallback_accepted": _env_flag(env, "OPENMYND_ACCEPT_LEGACY_PASSWORD_FALLBACK"),
            "legacy_password_fallback_disabled": legacy_password_fallback_disabled,
            "legal_privacy_routes_present": not missing_legal_sources,
            "public_frontend_routes_present": not missing_frontend_routes,
            "stripe_configured": all(
                not _looks_like_placeholder(value) for value in stripe_values.values()
            ),
            "stripe_secret_configured": bool(stripe_secret_key),
            "stripe_webhook_secret_configured": bool(stripe_webhook_secret),
            "stripe_price_personal_configured": bool(stripe_price_personal_monthly),
            "stripe_price_plus_configured": bool(stripe_price_plus_monthly),
            "stripe_price_personal_monthly_configured": bool(
                stripe_price_personal_monthly
            ),
            "stripe_price_personal_annual_configured": bool(
                stripe_price_personal_annual
            ),
            "stripe_price_plus_monthly_configured": bool(stripe_price_plus_monthly),
            "stripe_price_plus_annual_configured": bool(stripe_price_plus_annual),
            "media_root_configured": bool(media_root),
            "media_root_absolute": media_root_is_absolute,
            "media_root_inside_repo": media_root_inside_repo,
            "media_base_url_configured": bool(media_base_url),
            "rate_limit_storage_configured": rate_limit_storage_uri != "memory://",
            "sensitive_rate_limits_configured": configured_sensitive_rate_limits,
            "security_audit_retention_days": security_audit_retention_days,
            "openai_api_key_configured": openai_key_configured,
            "process_supervision_files_present": not missing_process_supervision_files,
            "missing_process_supervision_files": missing_process_supervision_files,
            "health_routes_present": health_routes_present,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate production/cloud runtime configuration."
    )
    parser.add_argument(
        "--root-path",
        default=Path(__file__).resolve().parents[1],
        help="Backend root path used for resolving DB_PATH fallbacks.",
    )
    parser.add_argument(
        "--require-postgres",
        action="store_true",
        help="Require Postgres-ready cloud cutover settings.",
    )
    args = parser.parse_args()

    report = build_production_preflight(
        root_path=Path(args.root_path).expanduser().resolve(),
        require_postgres=args.require_postgres,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready_for_production"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
