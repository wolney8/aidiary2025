import sqlite3

from scripts.run_postgres_migrations import discover_migrations
from services.runtime_migrations import ensure_entry_mood_style_columns


def test_runtime_sqlite_adds_entry_list_order_indexes_when_columns_exist(tmp_path):
    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date TEXT,
                entry_time TEXT,
                entry_number INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date TEXT,
                entry_time TEXT,
                entry_number INTEGER
            )
            """
        )

    ensure_entry_mood_style_columns(str(db_path))

    with sqlite3.connect(db_path) as conn:
        indexes = {
            row[1]
            for row in conn.execute(
                "SELECT type, name FROM sqlite_master WHERE type = 'index'"
            )
        }

    assert "idx_daily_entries_user_list_order" in indexes
    assert "idx_dream_entries_user_list_order" in indexes


def test_postgres_entry_list_order_index_migration_is_ordered():
    versions = [migration.version for migration in discover_migrations()]

    assert "0002_entry_list_order_indexes" in versions
    assert versions.index("0001_initial_schema") < versions.index(
        "0002_entry_list_order_indexes"
    )
