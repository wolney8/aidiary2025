import sys
from types import SimpleNamespace

import pytest

from services.database import DatabaseSettings
from services.database_adapter import DatabaseAdapter, get_database_adapter


def test_database_adapter_builds_from_settings():
    settings = DatabaseSettings(
        provider="sqlite",
        sqlite_path="/tmp/app.db",
        database_url=None,
        runtime_migrations_enabled=True,
    )

    adapter = DatabaseAdapter.from_settings(settings)

    assert adapter.provider == "sqlite"
    assert adapter.sqlite_path == "/tmp/app.db"
    assert adapter.database_url is None


def test_database_adapter_builds_from_app_config(tmp_path):
    db_path = tmp_path / "app.db"
    app = SimpleNamespace(
        config={
            "DATABASE_PROVIDER": "sqlite",
            "DATABASE_PATH": str(db_path),
            "DATABASE_URL": None,
        }
    )

    adapter = get_database_adapter(app)

    assert adapter == DatabaseAdapter(
        provider="sqlite",
        sqlite_path=str(db_path),
        database_url=None,
    )


def test_database_adapter_opens_sqlite_connections(tmp_path):
    db_path = tmp_path / "app.db"
    adapter = DatabaseAdapter(provider="sqlite", sqlite_path=str(db_path))

    with adapter.connect() as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES (?)", ("adapter",))
        row = conn.execute("SELECT name FROM sample").fetchone()

    assert row["name"] == "adapter"


def test_database_adapter_requires_postgres_url():
    adapter = DatabaseAdapter(provider="postgres", sqlite_path="/tmp/fallback.db")

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        with adapter.connect():
            pass


def test_database_adapter_reports_missing_psycopg(monkeypatch):
    adapter = DatabaseAdapter(
        provider="postgres",
        sqlite_path="/tmp/fallback.db",
        database_url="postgresql://example/rehearsal",
    )
    monkeypatch.setitem(sys.modules, "psycopg", None)

    with pytest.raises(RuntimeError, match="psycopg is required"):
        with adapter.connect():
            pass


def test_database_adapter_rejects_unknown_provider():
    adapter = DatabaseAdapter(provider="mysql", sqlite_path="/tmp/fallback.db")

    with pytest.raises(ValueError, match="Unsupported database provider"):
        with adapter.connect():
            pass
