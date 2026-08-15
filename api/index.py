"""Vercel Python Function entrypoint for the OpenMynd Flask API.

This keeps the existing Flask app intact while allowing a single Vercel project to
route /api and /media requests to serverless Python during deployment rehearsals.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


def _should_apply_postgres_migrations_on_startup() -> bool:
    configured = (
        os.getenv("OPENMYND_APPLY_POSTGRES_MIGRATIONS_ON_STARTUP") or ""
    ).strip().lower()
    if configured in {"0", "false", "no", "off"}:
        return False
    database_provider = (os.getenv("DATABASE_PROVIDER") or "").strip().lower()
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    return (
        bool(os.getenv("VERCEL"))
        and database_provider == "postgres"
        and database_url.lower().startswith(("postgres://", "postgresql://"))
    )


def _apply_postgres_migrations_for_vercel() -> dict[str, object] | None:
    if not _should_apply_postgres_migrations_on_startup():
        return None

    from scripts.run_postgres_migrations import (  # noqa: E402
        MIGRATIONS_DIR,
        apply_pending_migrations,
    )

    return apply_pending_migrations(
        database_url=(os.getenv("DATABASE_URL") or "").strip(),
        migrations_dir=MIGRATIONS_DIR,
    )


def _safe_env_snapshot() -> dict[str, object]:
    return {
        "app_env": (os.getenv("APP_ENV") or "").strip() or None,
        "vercel": bool(os.getenv("VERCEL")),
        "vercel_env": (os.getenv("VERCEL_ENV") or "").strip() or None,
        "vercel_git_commit_sha": (os.getenv("VERCEL_GIT_COMMIT_SHA") or "").strip()[:12]
        or None,
        "database_provider_env": (os.getenv("DATABASE_PROVIDER") or "").strip() or None,
        "database_url_present": bool((os.getenv("DATABASE_URL") or "").strip()),
        "database_url_is_postgres": (os.getenv("DATABASE_URL") or "")
        .strip()
        .lower()
        .startswith(("postgres://", "postgresql://")),
        "cors_origins_present": bool((os.getenv("CORS_ORIGINS") or "").strip()),
        "frontend_base_url_present": bool(
            (os.getenv("FRONTEND_BASE_URL") or "").strip()
        ),
        "media_storage_backend": (os.getenv("MEDIA_STORAGE_BACKEND") or "").strip()
        or None,
        "r2_endpoint_present": bool((os.getenv("R2_ENDPOINT_URL") or "").strip()),
        "r2_access_key_present": bool((os.getenv("R2_ACCESS_KEY_ID") or "").strip()),
        "r2_secret_key_present": bool((os.getenv("R2_SECRET_ACCESS_KEY") or "").strip()),
        "r2_bucket_present": bool((os.getenv("R2_BUCKET_NAME") or "").strip()),
        "rate_limit_storage_uri_present": bool(
            (os.getenv("RATELIMIT_STORAGE_URI") or "").strip()
        ),
        "shared_rate_limiting_deferred": (os.getenv("OPENMYND_DEFER_SHARED_RATE_LIMITING") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
        "email_provider": (os.getenv("EMAIL_PROVIDER") or "").strip() or None,
        "email_delivery_deferred": (os.getenv("OPENMYND_DEFER_EMAIL_DELIVERY") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"},
    }


def _startup_failure_app(exc: BaseException) -> Flask:
    fallback = Flask(__name__)
    startup_error = {
        "category": "startup",
        "code": "startup_configuration_failed",
        "error": "OpenMynd API could not start with the current hosting configuration.",
        "startup_error_type": exc.__class__.__name__,
        "startup_error": str(exc),
        "environment": _safe_env_snapshot(),
    }

    @fallback.route("/health")
    @fallback.route("/api/health/database")
    def health():
        return jsonify(startup_error), 503

    @fallback.route("/api", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    @fallback.route("/api/<path:_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def api_unavailable(_path: str = ""):
        return jsonify(startup_error), 503

    @fallback.route("/", defaults={"_path": ""})
    @fallback.route("/<path:_path>")
    def unavailable(_path: str):
        if request.path.startswith("/api/"):
            return jsonify(startup_error), 503
        return jsonify(startup_error), 503

    return fallback


def _build_vercel_app() -> Flask:
    try:
        migration_result = _apply_postgres_migrations_for_vercel()
        from app import create_app  # noqa: E402

        flask_app = create_app()
        if migration_result is not None:
            flask_app.config["POSTGRES_STARTUP_MIGRATION_RESULT"] = migration_result
        return flask_app
    except Exception as startup_exc:  # noqa: BLE001
        return _startup_failure_app(startup_exc)


# Vercel's Python builder scans for a top-level `app` symbol. Keep the fallback
# inside the builder function so startup errors return structured JSON at runtime.
app = _build_vercel_app()
