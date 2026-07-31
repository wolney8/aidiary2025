import pytest
import sys
import types

import app as app_module
import routes.import_routes as import_routes_module
from app import create_app
from services.database import DatabaseSettings
from services.database import connect_sqlite_path, resolve_database_settings, table_columns, table_info


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
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    with pytest.raises(RuntimeError, match="DATABASE_PROVIDER=sqlite is blocked"):
        create_app()


def test_app_allows_explicit_sqlite_production_fallback(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    db_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PROVIDER", "sqlite")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://openmynd.example")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK", "true")
    monkeypatch.setenv("OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION", "true")
    monkeypatch.setattr(app_module, "_run_sqlite_runtime_migrations", lambda *_args: None)
    monkeypatch.setattr(app_module, "_ensure_nltk_data", lambda: None)
    monkeypatch.setattr(import_routes_module, "recover_import_jobs", lambda _app: 0)

    app = create_app()

    assert app.config["DATABASE_PROVIDER"] == "sqlite"
    assert app.config["DATABASE_PATH"] == str(db_path)


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
    assert "DATABASE_URL" not in str(payload)


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
        def health_check(self):
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


def test_table_columns_returns_empty_set_for_missing_table(tmp_path):
    db_path = tmp_path / "app.db"
    conn = connect_sqlite_path(str(db_path))

    assert table_columns(conn, "missing") == set()

    conn.close()
