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
AUTH_RATE_LIMIT_ENV_KEYS = (
    "AUTH_LOGIN_RATE_LIMIT",
    "AUTH_REGISTER_RATE_LIMIT",
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


def _env_flag(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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

    if app_env == "production" and not _env_flag(env, "OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK"):
        _add_gate(
            warnings,
            gate="jwt_browser_storage_review",
            severity="warning",
            message=(
                "Browser bearer tokens are currently stored in localStorage. "
                "Set OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK=true only after the launch owner accepts this risk or ships a cookie/session redesign."
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

    repo_root = root_path.parent
    frontend_tree_available = (repo_root / "client").exists()
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

    media_root = (env.get("MEDIA_ROOT") or "").strip()
    media_base_url = (env.get("MEDIA_BASE_URL") or "").strip()
    if app_env == "production" and not media_root and not media_base_url:
        _add_gate(
            blockers,
            gate="media_storage",
            message=(
                "MEDIA_ROOT or MEDIA_BASE_URL must be explicit before production deployment."
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

    openai_key = (env.get("OPENAI_API_KEY") or "").strip()
    if not openai_key:
        _add_gate(
            warnings,
            gate="openai_api_key",
            severity="warning",
            message="OPENAI_API_KEY is not configured; AI features will fail.",
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
            "localstorage_jwt_risk_accepted": _env_flag(env, "OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK"),
            "legacy_password_fallback_accepted": _env_flag(env, "OPENMYND_ACCEPT_LEGACY_PASSWORD_FALLBACK"),
            "legacy_password_fallback_disabled": legacy_password_fallback_disabled,
            "legal_privacy_routes_present": not missing_legal_sources,
            "media_root_configured": bool(media_root),
            "media_base_url_configured": bool(media_base_url),
            "rate_limit_storage_configured": rate_limit_storage_uri != "memory://",
            "sensitive_rate_limits_configured": configured_sensitive_rate_limits,
            "openai_api_key_configured": bool(openai_key),
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
