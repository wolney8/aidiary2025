import sys
from types import SimpleNamespace

import pytest

from services.database import DatabaseSettings
from services.database_adapter import (
    DatabaseAdapter,
    _SqlCompatConnection,
    get_database_adapter,
)


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
    with adapter.connect() as conn:
        persisted = conn.execute("SELECT name FROM sample").fetchone()
    assert persisted["name"] == "adapter"


def test_database_adapter_open_returns_manual_close_sqlite_connection(tmp_path):
    db_path = tmp_path / "app.db"
    adapter = DatabaseAdapter(provider="sqlite", sqlite_path=str(db_path))

    conn = adapter.open()
    try:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES (?)", ("manual",))
        conn.commit()
    finally:
        conn.close()

    with adapter.connect() as conn:
        row = conn.execute("SELECT name FROM sample").fetchone()
    assert row["name"] == "manual"


def test_database_adapter_introspects_sqlite_tables_and_columns(tmp_path):
    db_path = tmp_path / "app.db"
    adapter = DatabaseAdapter(provider="sqlite", sqlite_path=str(db_path))

    with adapter.connect() as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        assert adapter.table_exists(conn, "sample") is True
        assert adapter.table_exists(conn, "missing") is False
        assert adapter.table_columns(conn, "sample") == {"id", "name"}


def test_database_adapter_introspects_postgres_tables_with_psycopg_placeholders():
    raw_conn = _FakeConnection()
    adapter = DatabaseAdapter(
        provider="postgres",
        sqlite_path="/tmp/fallback.db",
        database_url="postgresql://example/rehearsal",
    )

    assert adapter.table_exists(_SqlCompatConnection(raw_conn, "postgres"), "users") is True

    assert raw_conn.calls == [
        (
            """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
                """,
            ("users",),
        )
    ]


def test_database_adapter_health_check_reports_sqlite_success(tmp_path):
    db_path = tmp_path / "app.db"
    adapter = DatabaseAdapter(provider="sqlite", sqlite_path=str(db_path))

    report = adapter.health_check(write=True)

    assert report["provider"] == "sqlite"
    assert report["ok"] is True
    assert report["read_ok"] is True
    assert report["write_ok"] is True
    assert isinstance(report["latency_ms"], float)
    assert "database_url" not in report
    assert "error_type" not in report


def test_database_adapter_health_check_sanitizes_failures():
    adapter = DatabaseAdapter(
        provider="postgres",
        sqlite_path="/tmp/fallback.db",
        database_url="postgresql://user:secret@example.invalid/app",
    )

    report = adapter.health_check()

    assert report["provider"] == "postgres"
    assert report["ok"] is False
    assert report["message"] == "Database connection check failed."
    assert "error_type" in report
    assert "secret" not in str(report)
    assert "example.invalid" not in str(report)


def test_database_adapter_rejects_unsafe_table_names(tmp_path):
    db_path = tmp_path / "app.db"
    adapter = DatabaseAdapter(provider="sqlite", sqlite_path=str(db_path))

    with adapter.connect() as conn:
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            adapter.table_exists(conn, "users; DROP TABLE users")
        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            adapter.table_columns(conn, "users; DROP TABLE users")


class _FakeCursor:
    def __init__(self):
        self.calls = []
        self.rowcount = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self

    def executemany(self, sql, params_seq):
        self.calls.append((sql, params_seq))
        return self

    def fetchone(self):
        return {"id": 123}

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self):
        self.calls = []
        self.cursor_obj = _FakeCursor()

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self.cursor_obj

    def executemany(self, sql, params_seq):
        self.calls.append((sql, params_seq))
        return self.cursor_obj

    def cursor(self):
        return self.cursor_obj


def test_sql_compat_connection_adapts_direct_execute_placeholders():
    raw_conn = _FakeConnection()
    conn = _SqlCompatConnection(raw_conn, "postgres")

    conn.execute("SELECT * FROM users WHERE id = ? AND note = '?'", (7,))

    assert raw_conn.calls == [
        ("SELECT * FROM users WHERE id = %s AND note = '?'", (7,))
    ]


def test_sql_compat_cursor_adapts_execute_placeholders_and_preserves_cursor_api():
    raw_conn = _FakeConnection()
    cursor = _SqlCompatConnection(raw_conn, "postgres").cursor()

    returned = cursor.execute("UPDATE users SET name = ? WHERE id = ?", ("Will", 7))

    assert returned is cursor
    assert cursor.connection.database_provider == "postgres"
    assert raw_conn.cursor_obj.calls == [
        ("UPDATE users SET name = %s WHERE id = %s", ("Will", 7))
    ]
    assert cursor.fetchone() == {"id": 123}


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
