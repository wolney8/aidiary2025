import pytest
import sys
import sqlite3
import types

import app as app_module
import routes.import_routes as import_routes_module
from app import create_app
from services.database import DatabaseSettings
from services.database import connect_sqlite_path, resolve_database_settings, table_columns, table_info
from services.import_service import (
    ensure_export_history_table,
    ensure_history_table,
    ensure_import_jobs_table,
    ensure_import_sessions_table,
)


@pytest.fixture(autouse=True)
def _clear_external_provider_env(monkeypatch):
    for name in (
        "OAUTH_GOOGLE_CLIENT_ID",
        "OAUTH_GOOGLE_CLIENT_SECRET",
        "OAUTH_GOOGLE_REDIRECT_URI",
    ):
        monkeypatch.delenv(name, raising=False)


def test_database_settings_default_to_sqlite(tmp_path):
    settings = resolve_database_settings(
        str(tmp_path),
        environ={},
    )

    assert settings.provider == "sqlite"
    assert settings.sqlite_path == str(tmp_path / "db" / "app.db")
    assert settings.database_url is None
    assert settings.runtime_migrations_enabled is True


def test_database_settings_resolve_relative_db_path(tmp_path):
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    db_path = db_dir / "local.db"
    db_path.write_text("", encoding="utf-8")

    settings = resolve_database_settings(
        str(tmp_path),
        environ={"DB_PATH": "data/local.db"},
    )

    assert settings.provider == "sqlite"
    assert settings.sqlite_path == str(db_path)


def test_database_settings_reject_unknown_provider(tmp_path):
    with pytest.raises(RuntimeError, match="Unsupported DATABASE_PROVIDER"):
        resolve_database_settings(
            str(tmp_path),
            environ={"DATABASE_PROVIDER": "mysql"},
        )


def test_database_settings_require_url_for_postgres(tmp_path):
    with pytest.raises(RuntimeError, match="DATABASE_URL must be configured"):
        resolve_database_settings(
            str(tmp_path),
            environ={"DATABASE_PROVIDER": "postgres"},
        )


def test_app_accepts_postgres_runtime_provider_after_adapter_lands(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/rehearsal")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()

    assert app.config["DATABASE_PROVIDER"] == "postgres"
    assert app.config["DATABASE_URL"] == "postgresql://example/rehearsal"
    assert app.config["DATABASE_RUNTIME_MIGRATIONS_ENABLED"] is False
    assert app.config["DATABASE_ADAPTER"].provider == "postgres"


def test_app_records_sqlite_database_provider(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/rehearsal")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    app = create_app()

    assert app.config["DATABASE_PROVIDER"] == "sqlite"
    assert app.config["DATABASE_PATH"] == str(db_path)
    assert app.config["DATABASE_URL"] == "postgresql://example/rehearsal"
    assert app.config["DATABASE_RUNTIME_MIGRATIONS_ENABLED"] is True
    assert app.config["DATABASE_ADAPTER"].provider == "sqlite"
    assert app.config["DATABASE_ADAPTER"].sqlite_path == str(db_path)


def test_app_blocks_sqlite_when_app_env_is_production(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="DATABASE_PROVIDER=sqlite is blocked"):
        create_app()


def test_app_blocks_short_jwt_secret_when_app_env_is_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "short-secret")

    with pytest.raises(RuntimeError, match="JWT_SECRET must not use"):
        create_app()


def test_app_blocks_development_jwt_secret_when_app_env_is_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "dev-secret-key")

    with pytest.raises(RuntimeError, match="JWT_SECRET must not use"):
        create_app()


def test_app_allows_explicit_sqlite_production_fallback(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.app>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.app")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()

    assert app.config["DATABASE_PROVIDER"] == "sqlite"
    assert app.config["DATABASE_PATH"] == str(db_path)


def test_app_blocks_missing_media_root_when_app_env_is_production(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.delenv("MEDIA_ROOT", raising=False)
    monkeypatch.setenv("MEDIA_BASE_URL", "https://cdn.openmynd.example/media")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.app>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.app")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="MEDIA_ROOT must be explicit"):
        create_app()


def test_app_blocks_repo_local_media_root_when_app_env_is_production(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(app_module.Path(app_module.__file__).resolve().parent / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.app>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.app")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="MEDIA_ROOT must not point inside"):
        create_app()


def test_app_blocks_console_email_when_app_env_is_production(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.app>")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="EMAIL_PROVIDER=console is blocked"):
        create_app()


def test_app_allows_deferred_email_for_private_production_rehearsal(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setenv("OPENMYND_DEFER_EMAIL_DELIVERY", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()

    assert app.config["DATABASE_PROVIDER"] == "sqlite"


def test_app_blocks_http_cors_origin_when_app_env_is_production(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "http://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.app>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.app")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="HTTPS frontend origins"):
        create_app()


def test_app_blocks_http_frontend_base_url_when_app_env_is_production(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.example>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.example")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="FRONTEND_BASE_URL must be an HTTPS"):
        create_app()


def test_app_blocks_placeholder_google_oauth_when_app_env_is_production(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.example>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.example")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "your_google_client_id")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "real-secret")
    monkeypatch.setenv(
        "OAUTH_GOOGLE_REDIRECT_URI",
        "https://api.openmynd.example/api/oauth/google/callback",
    )
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="Google OAuth production configuration"):
        create_app()


def test_app_blocks_local_google_oauth_redirect_when_app_env_is_production(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.example>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.example")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "real-secret")
    monkeypatch.setenv(
        "OAUTH_GOOGLE_REDIRECT_URI",
        "http://localhost:5001/api/oauth/google/callback",
    )
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="OAUTH_GOOGLE_REDIRECT_URI must be an HTTPS"):
        create_app()


def test_app_blocks_memory_rate_limit_storage_when_app_env_is_production(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.example>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.example")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI=memory:// is blocked"):
        create_app()


def test_app_allows_deferred_shared_rate_limiting_for_private_production_rehearsal(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("OPENMYND_DEFER_SHARED_RATE_LIMITING", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    monkeypatch.setenv("OPENMYND_DEFER_EMAIL_DELIVERY", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()

    assert app.config["RATELIMIT_STORAGE_URI"] == "memory://"


def test_database_health_endpoint_reports_provider_status(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()
    response = app.test_client().get("/api/health/database")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["provider"] == "sqlite"
    assert payload["ok"] is True
    assert payload["read_ok"] is True
    assert payload["write_ok"] is None
    assert "DATABASE_URL" not in str(payload)


def test_app_applies_default_security_headers(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()
    response = app.test_client().get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers


def test_app_applies_hsts_when_app_env_is_production(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "OpenMynd <no-reply@openmynd.example>")
    monkeypatch.setenv("SMTP_HOST", "smtp.openmynd.example")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()
    response = app.test_client().get("/health")

    assert response.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains"
    )


def test_database_health_endpoint_can_probe_write_readiness(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()
    response = app.test_client().get("/api/health/database?write=true")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["read_ok"] is True
    assert payload["write_ok"] is True


def test_database_health_endpoint_returns_503_for_failed_provider(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    class FailingAdapter:
        def health_check(self, *, write=False):
            return {
                "provider": "postgres",
                "ok": False,
                "latency_ms": None,
                "error_type": "OperationalError",
                "message": "Database connection check failed.",
            }

    app = create_app()
    app.config["DATABASE_ADAPTER"] = FailingAdapter()
    response = app.test_client().get("/api/health/database")

    assert response.status_code == 503
    assert response.get_json() == {
        "provider": "postgres",
        "ok": False,
        "latency_ms": None,
        "error_type": "OperationalError",
        "message": "Database connection check failed.",
    }


def test_database_write_failure_returns_sanitized_api_error(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()

    @app.route("/api/test-database-write-failure", methods=["POST"])
    def test_database_write_failure():
        raise sqlite3.OperationalError("database or disk is full")

    response = app.test_client().post("/api/test-database-write-failure")

    assert response.status_code == 507
    payload = response.get_json()
    assert payload["code"] == "database_storage_exhausted"
    assert payload["category"] == "storage_or_quota"
    assert "database or disk is full" not in str(payload)


def test_app_runs_runtime_migration_hook_for_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    calls = []

    def fake_runtime_migrations(_app, database_path):
        calls.append(database_path)

    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", fake_runtime_migrations)

    create_app()

    assert calls == [str(db_path)]


def test_app_skips_sqlite_runtime_migrations_when_disabled(monkeypatch, tmp_path):
    db_path = tmp_path / "fallback.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    def fake_configure(flask_app):
        flask_app.config["DATABASE_PROVIDER"] = "postgres"
        flask_app.config["DATABASE_PATH"] = str(db_path)
        flask_app.config["DATABASE_URL"] = "postgresql://example/rehearsal"
        flask_app.config["DATABASE_RUNTIME_MIGRATIONS_ENABLED"] = False
        return DatabaseSettings(
            provider="postgres",
            sqlite_path=str(db_path),
            database_url="postgresql://example/rehearsal",
            runtime_migrations_enabled=False,
        )

    def fail_runtime_migrations(_app, _database_path):
        raise AssertionError("SQLite runtime migrations should be skipped")

    monkeypatch.setattr(app_module, "configure_app_database", fake_configure)
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", fail_runtime_migrations)

    app = create_app()

    assert app.config["DATABASE_PROVIDER"] == "postgres"
    assert app.config["DATABASE_RUNTIME_MIGRATIONS_ENABLED"] is False


def test_nltk_startup_check_does_not_download_by_default(monkeypatch):
    download_calls = []

    class FakeNltkData:
        @staticmethod
        def find(_resource_path):
            raise LookupError

    fake_nltk = types.SimpleNamespace(
        data=FakeNltkData(),
        download=lambda package, quiet=True: download_calls.append((package, quiet)),
    )

    monkeypatch.setitem(sys.modules, "nltk", fake_nltk)
    monkeypatch.delenv("OPENMYND_AUTO_DOWNLOAD_NLTK", raising=False)

    app_module._ensure_nltk_data()

    assert download_calls == []


def test_nltk_startup_check_downloads_only_when_enabled(monkeypatch):
    download_calls = []

    class FakeNltkData:
        @staticmethod
        def find(_resource_path):
            raise LookupError

    fake_nltk = types.SimpleNamespace(
        data=FakeNltkData(),
        download=lambda package, quiet=True: download_calls.append((package, quiet)),
    )

    monkeypatch.setitem(sys.modules, "nltk", fake_nltk)
    monkeypatch.setenv("OPENMYND_AUTO_DOWNLOAD_NLTK", "true")

    app_module._ensure_nltk_data()

    assert download_calls
    assert all(quiet is True for _package, quiet in download_calls)


def test_startup_nltk_backfill_requires_explicit_opt_in(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.delenv("OPENMYND_STARTUP_NLTK_BACKFILL", raising=False)
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    def fail_backfill(_conn, _logger=None):
        raise AssertionError("Startup NLTK backfill should be opt-in")

    fake_import_service = types.SimpleNamespace(backfill_nltk_enrichment=fail_backfill)
    monkeypatch.setitem(sys.modules, "services.import_service", fake_import_service)

    create_app()


def test_connect_sqlite_path_returns_row_mapping(tmp_path):
    db_path = tmp_path / "app.db"
    conn = connect_sqlite_path(str(db_path))
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO sample (name) VALUES (?)", ("test",))
    row = conn.execute("SELECT id, name FROM sample").fetchone()
    conn.close()

    assert row["name"] == "test"


def test_table_columns_returns_column_names(tmp_path):
    db_path = tmp_path / "app.db"
    conn = connect_sqlite_path(str(db_path))
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")

    assert table_columns(conn, "sample") == {"id", "name"}

    conn.close()


def test_table_info_returns_column_metadata(tmp_path):
    db_path = tmp_path / "app.db"
    conn = connect_sqlite_path(str(db_path))
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")

    info = table_info(conn, "sample")

    assert [row[1] for row in info] == ["id", "name"]
    assert info[1][3] == 1

    conn.close()


class _PostgresManagedTableConnection:
    database_provider = "postgres"

    def __init__(self, table_exists: bool):
        self.table_exists = table_exists
        self.executed_sql: list[str] = []
        self.last_params = None

    def execute(self, sql, params=None):
        self.executed_sql.append(sql)
        self.last_params = params
        if "PRAGMA" in sql or "AUTOINCREMENT" in sql:
            raise AssertionError("Postgres managed table check must not issue SQLite SQL")
        return self

    def fetchone(self):
        requested_table = self.last_params[0] if self.last_params else "public.unknown"
        return {"table_name": requested_table if self.table_exists else None}


@pytest.mark.parametrize(
    ("ensure_fn", "table_name"),
    [
        (ensure_history_table, "import_history"),
        (ensure_export_history_table, "export_history"),
        (ensure_import_sessions_table, "import_sessions"),
        (ensure_import_jobs_table, "import_jobs"),
    ],
)
def test_import_schema_helpers_use_managed_postgres_schema(ensure_fn, table_name):
    conn = _PostgresManagedTableConnection(table_exists=True)

    ensure_fn(conn)

    assert conn.executed_sql == ["SELECT to_regclass(?) AS table_name"]
    assert conn.last_params == (f"public.{table_name}",)


@pytest.mark.parametrize(
    ("ensure_fn", "table_name"),
    [
        (ensure_history_table, "import_history"),
        (ensure_export_history_table, "export_history"),
        (ensure_import_sessions_table, "import_sessions"),
        (ensure_import_jobs_table, "import_jobs"),
    ],
)
def test_import_schema_helpers_require_postgres_migration_schema(ensure_fn, table_name):
    conn = _PostgresManagedTableConnection(table_exists=False)

    with pytest.raises(RuntimeError, match=f"Postgres {table_name} table is missing"):
        ensure_fn(conn)


def test_table_columns_returns_empty_set_for_missing_table(tmp_path):
    db_path = tmp_path / "app.db"
    conn = connect_sqlite_path(str(db_path))

    assert table_columns(conn, "missing") == set()

    conn.close()
