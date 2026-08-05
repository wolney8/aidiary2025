import re
import sqlite3

from scripts.load_cloud_migration import (
    IDENTITY_ID_TABLES,
    SCHEMA_PATH,
    _postgres_schema_columns,
)
from scripts.rehearse_cloud_migration import TABLE_ORDER
from services.runtime_migrations import (
    ensure_auth_identities_table,
    ensure_cbt_worksheet_tables,
    ensure_chat_messages_table,
    ensure_chat_observability_events_table,
    ensure_entry_ai_metadata_table,
    ensure_entry_assets_table,
    ensure_entry_mood_style_columns,
    ensure_entry_resurfacing_preferences_table,
    ensure_export_history_table,
    ensure_import_jobs_table,
    ensure_import_sessions_table,
    ensure_important_days_table,
    ensure_public_holiday_cache_table,
    ensure_reflection_summaries_table,
    ensure_user_settings_columns,
)


CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE IF NOT EXISTS (?P<table>[A-Za-z_][A-Za-z0-9_]*) \(",
    re.IGNORECASE,
)


def _postgres_schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _postgres_data_tables() -> set[str]:
    tables = {
        match.group("table")
        for match in CREATE_TABLE_RE.finditer(_postgres_schema_sql())
    }
    tables.discard("schema_migrations")
    return tables


def _postgres_identity_tables() -> set[str]:
    sql = _postgres_schema_sql()
    identity_tables = set()
    for table_name in _postgres_data_tables():
        table_match = re.search(
            rf"CREATE TABLE IF NOT EXISTS {table_name} \((?P<body>.*?)\n\);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not table_match:
            continue
        if re.search(
            r"\bid\s+BIGINT\s+GENERATED\s+BY\s+DEFAULT\s+AS\s+IDENTITY\b",
            table_match.group("body"),
            re.IGNORECASE,
        ):
            identity_tables.add(table_name)
    return identity_tables


def _sqlite_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table_name})")}


def _build_runtime_sqlite_schema(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                entry_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                entry_date TEXT
            )
            """
        )

    ensure_entry_mood_style_columns(str(db_path))
    ensure_entry_ai_metadata_table(str(db_path))
    ensure_user_settings_columns(str(db_path))
    ensure_auth_identities_table(str(db_path))
    ensure_export_history_table(str(db_path))
    ensure_import_sessions_table(str(db_path))
    ensure_import_jobs_table(str(db_path))
    ensure_entry_assets_table(str(db_path))
    ensure_important_days_table(str(db_path))
    ensure_public_holiday_cache_table(str(db_path))
    ensure_entry_resurfacing_preferences_table(str(db_path))
    ensure_reflection_summaries_table(str(db_path))
    ensure_chat_messages_table(str(db_path))
    ensure_chat_observability_events_table(str(db_path))
    ensure_cbt_worksheet_tables(str(db_path))


def test_cloud_export_table_order_covers_every_postgres_data_table():
    assert set(TABLE_ORDER) == _postgres_data_tables()


def test_cloud_loader_resets_every_postgres_identity_table():
    assert IDENTITY_ID_TABLES == _postgres_identity_tables()


def test_runtime_sqlite_managed_columns_exist_in_postgres_schema(tmp_path):
    db_path = tmp_path / "runtime.db"
    _build_runtime_sqlite_schema(db_path)
    postgres_columns = _postgres_schema_columns()

    managed_tables = {
        "users",
        "auth_identities",
        "dailydiary_entries",
        "dreamdiary_entries",
        "entry_ai_metadata",
        "export_history",
        "import_sessions",
        "import_jobs",
        "entry_assets",
        "important_days",
        "public_holiday_cache",
        "entry_resurfacing_preferences",
        "reflection_summaries",
        "chat_messages",
        "chat_observability_events",
        "cbt_worksheets",
        "cbt_thought_record_data",
    }

    with sqlite3.connect(db_path) as conn:
        mismatches = []
        for table_name in sorted(managed_tables):
            sqlite_columns = _sqlite_columns(conn, table_name)
            missing_in_postgres = sorted(
                sqlite_columns - postgres_columns.get(table_name, set())
            )
            if missing_in_postgres:
                mismatches.append(
                    {
                        "table": table_name,
                        "sqlite_only_columns": missing_in_postgres,
                    }
                )

    assert mismatches == []


def test_important_day_runtime_schema_covers_cloud_fields(tmp_path):
    db_path = tmp_path / "important-days.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )

    ensure_important_days_table(str(db_path))

    with sqlite3.connect(db_path) as conn:
        assert {"ends_on", "linked_entry_refs"}.issubset(
            _sqlite_columns(conn, "important_days")
        )


def test_auth_identity_runtime_schema_supports_provider_registration(tmp_path):
    db_path = tmp_path / "auth-identities.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )

    ensure_auth_identities_table(str(db_path))

    with sqlite3.connect(db_path) as conn:
        assert {
            "user_id",
            "provider",
            "provider_subject",
            "email",
            "email_verified",
            "display_name",
            "profile_picture_url",
        }.issubset(_sqlite_columns(conn, "auth_identities"))
        indexes = {
            str(row[1])
            for row in conn.execute("PRAGMA index_list(auth_identities)").fetchall()
        }
        assert "idx_auth_identities_user_provider" in indexes
