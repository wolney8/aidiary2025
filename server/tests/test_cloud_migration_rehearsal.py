import json
import sqlite3

import pytest

from scripts.load_cloud_migration import (
    _quote_identifier,
    _split_sql_statements,
    build_load_plan,
)
from scripts.rehearse_cloud_migration import build_report, export_jsonl


def _seed_source_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute(
            """
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date TEXT,
                title TEXT,
                user_message TEXT,
                image_url TEXT,
                image_storage_key TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE entry_assets (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_type TEXT,
                entry_id INTEGER,
                storage_key TEXT
            )
            """
        )
        conn.execute("INSERT INTO users (id, username) VALUES (1, 'migration-user')")
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                id, user_id, entry_date, title, user_message, image_url, image_storage_key
            ) VALUES (10, 1, '2026-07-23', 'Ready', 'Migration rehearsal', NULL, NULL)
            """
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                id, user_id, entry_date, title, user_message, image_url, image_storage_key
            ) VALUES (11, 99, '2026-07-24', 'Orphan', 'Bad user', 'data:image/png;base64,abc', '')
            """
        )
        conn.execute(
            """
            INSERT INTO entry_assets (
                id, user_id, entry_type, entry_id, storage_key
            ) VALUES (1, 1, 'daily', 10, '')
            """
        )


def test_build_report_counts_tables_and_flags_orphans(tmp_path):
    db_path = tmp_path / "source.db"
    _seed_source_db(db_path)

    report = build_report(db_path)

    assert report["summary"]["tables_present"] == 3
    assert report["summary"]["total_rows"] == 4
    assert "dreamdiary_entries" in report["summary"]["tables_missing"]
    assert report["media_reference_checks"] == {
        "entry_assets_missing_storage_key": 1,
        "dailydiary_entries_legacy_inline_images": 1,
    }
    orphan_issues = report["summary"]["orphan_issues"]
    assert orphan_issues == [
        {
            "child_table": "dailydiary_entries",
            "child_column": "user_id",
            "parent_table": "users",
            "parent_column": "id",
            "orphan_count": 1,
        }
    ]


def test_export_jsonl_writes_existing_tables_only(tmp_path):
    db_path = tmp_path / "source.db"
    export_dir = tmp_path / "exports"
    _seed_source_db(db_path)

    written = export_jsonl(db_path, export_dir)

    assert str(export_dir / "users.jsonl") in written
    assert str(export_dir / "dailydiary_entries.jsonl") in written
    assert not (export_dir / "dreamdiary_entries.jsonl").exists()

    user_rows = [
        json.loads(line)
        for line in (export_dir / "users.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert user_rows == [{"id": 1, "username": "migration-user"}]


def test_load_plan_reports_exported_table_counts(tmp_path):
    db_path = tmp_path / "source.db"
    export_dir = tmp_path / "exports"
    _seed_source_db(db_path)
    export_jsonl(db_path, export_dir)

    plan = build_load_plan(export_dir)

    assert plan["total_rows"] == 4
    users_plan = next(table for table in plan["tables"] if table["table"] == "users")
    assert users_plan["exists"] is True
    assert users_plan["row_count"] == 1
    assert users_plan["columns"] == ["id", "username"]
    missing = set(plan["missing_files"])
    assert "dreamdiary_entries" in missing
    assert "configurations" in missing
    assert "import_history" in missing


def test_postgres_loader_sql_helpers_are_safe():
    assert _quote_identifier("dailydiary_entries") == '"dailydiary_entries"'
    with pytest.raises(ValueError):
        _quote_identifier("users; DROP TABLE users")

    statements = _split_sql_statements(
        "CREATE TABLE one (name TEXT DEFAULT 'a;b'); CREATE TABLE two (id BIGINT);"
    )
    assert statements == [
        "CREATE TABLE one (name TEXT DEFAULT 'a;b')",
        "CREATE TABLE two (id BIGINT)",
    ]
