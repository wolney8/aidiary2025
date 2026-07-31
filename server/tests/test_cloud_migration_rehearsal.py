import json
import sqlite3

import pytest

from scripts.load_cloud_migration import (
    RESET_CONFIRMATION_TOKEN,
    _managed_table_row_counts,
    _quote_identifier,
    _postgres_schema_columns,
    _split_sql_statements,
    _validate_postgres_target_load_safety,
    apply_export_to_postgres,
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
        conn.execute(
            """
            CREATE TABLE entry_ai_metadata (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                mode TEXT,
                reference_date TEXT,
                summary_header TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE export_history (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                exported_at TEXT,
                filename TEXT
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
        conn.execute(
            """
            INSERT INTO entry_ai_metadata (
                id, user_id, mode, reference_date, summary_header
            ) VALUES (1, 1, 'daily', '2026-07-23', 'Migration context')
            """
        )
        conn.execute(
            """
            INSERT INTO export_history (
                id, user_id, exported_at, filename
            ) VALUES (1, 1, '2026-07-25T09:00:00Z', 'aidiary-export.zip')
            """
        )


def test_build_report_counts_tables_and_flags_orphans(tmp_path):
    db_path = tmp_path / "source.db"
    _seed_source_db(db_path)

    report = build_report(db_path)

    assert report["summary"]["tables_present"] == 5
    assert report["summary"]["total_rows"] == 6
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
    assert str(export_dir / "entry_ai_metadata.jsonl") in written
    assert str(export_dir / "export_history.jsonl") in written
    assert not (export_dir / "dreamdiary_entries.jsonl").exists()
    manifest = json.loads((export_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_rows"] == 6
    user_manifest = next(
        table for table in manifest["tables"] if table["table"] == "users"
    )
    assert user_manifest["file"] == "users.jsonl"
    assert user_manifest["row_count"] == 1
    assert user_manifest["byte_size"] > 0
    assert len(user_manifest["sha256"]) == 64

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

    assert plan["total_rows"] == 6
    assert plan["schema_column_mismatches"] == []
    assert plan["manifest"] == {"present": True, "total_rows": 6}
    assert plan["manifest_mismatches"] == []
    users_plan = next(table for table in plan["tables"] if table["table"] == "users")
    assert users_plan["exists"] is True
    assert users_plan["row_count"] == 1
    assert users_plan["columns"] == ["id", "username"]
    assert users_plan["unknown_columns"] == []
    metadata_plan = next(
        table for table in plan["tables"] if table["table"] == "entry_ai_metadata"
    )
    assert metadata_plan["exists"] is True
    assert metadata_plan["row_count"] == 1
    export_plan = next(table for table in plan["tables"] if table["table"] == "export_history")
    assert export_plan["exists"] is True
    assert export_plan["row_count"] == 1
    missing = set(plan["missing_files"])
    assert "dreamdiary_entries" in missing
    assert "configurations" in missing
    assert "import_history" in missing


def test_load_plan_flags_columns_missing_from_postgres_schema(tmp_path):
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    (export_dir / "users.jsonl").write_text(
        '{"id": 1, "username": "migration-user", "unexpected": "bad"}\n',
        encoding="utf-8",
    )

    plan = build_load_plan(export_dir)

    assert plan["schema_column_mismatches"] == [
        {"table": "users", "unknown_columns": ["unexpected"]}
    ]
    assert plan["manifest_mismatches"] == [
        {"gate": "manifest_missing", "message": "Export manifest.json is missing."}
    ]
    users_plan = next(table for table in plan["tables"] if table["table"] == "users")
    assert users_plan["unknown_columns"] == ["unexpected"]


def test_load_plan_flags_manifest_mismatch_before_cloud_apply(tmp_path):
    db_path = tmp_path / "source.db"
    export_dir = tmp_path / "exports"
    _seed_source_db(db_path)
    export_jsonl(db_path, export_dir)
    with (export_dir / "users.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"id": 2, "username": "tampered"}\n')

    plan = build_load_plan(export_dir)

    gates = {mismatch["gate"] for mismatch in plan["manifest_mismatches"]}
    assert {"manifest_row_count", "manifest_byte_size", "manifest_sha256"}.issubset(
        gates
    )
    with pytest.raises(ValueError, match="Export manifest validation failed"):
        apply_export_to_postgres(
            database_url="postgresql://example/rehearsal",
            export_dir=export_dir,
        )


def test_postgres_schema_column_parser_covers_managed_tables():
    schema_columns = _postgres_schema_columns()

    assert "image_storage_key" in schema_columns["dailydiary_entries"]
    assert "analysis_attachment_refs" in schema_columns["dreamdiary_entries"]
    assert "derived_text_source" in schema_columns["entry_assets"]
    assert "ai_response_outdated" in schema_columns["cbt_thought_record_data"]


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


class _FakePostgresInspectionCursor:
    def __init__(self, row_counts):
        self.row_counts = row_counts
        self.executed = []
        self._last_result = None

    def execute(self, statement, params=None):
        self.executed.append((statement, params))
        if statement == "SELECT to_regclass(%s)":
            table_name = str(params[0]).split(".", 1)[1]
            self._last_result = (f"public.{table_name}",) if table_name in self.row_counts else (None,)
            return self
        if statement.startswith("SELECT COUNT(*) FROM "):
            table_name = statement.rsplit('"', 2)[1]
            self._last_result = (self.row_counts[table_name],)
            return self
        raise AssertionError(f"Unexpected statement: {statement}")

    def fetchone(self):
        return self._last_result


def test_managed_table_row_counts_skips_missing_postgres_tables():
    cursor = _FakePostgresInspectionCursor({"users": 2, "dailydiary_entries": 5})

    counts = _managed_table_row_counts(
        cursor,
        ["users", "missing_table", "dailydiary_entries"],
    )

    assert counts == {"users": 2, "dailydiary_entries": 5}


def test_postgres_loader_allows_empty_target_without_reset_confirmation():
    cursor = _FakePostgresInspectionCursor({"users": 0, "dailydiary_entries": 0})

    safety = _validate_postgres_target_load_safety(
        cursor,
        reset_first=True,
        reset_confirmation=None,
    )

    assert safety == {
        "existing_total_rows": 0,
        "non_empty_table_counts": {},
        "reset_first": True,
        "reset_confirmation_required": False,
    }


def test_postgres_loader_blocks_append_into_non_empty_target():
    cursor = _FakePostgresInspectionCursor({"users": 2})

    with pytest.raises(RuntimeError, match="Refusing to load into a non-empty Postgres target"):
        _validate_postgres_target_load_safety(
            cursor,
            reset_first=False,
            reset_confirmation=None,
        )


def test_postgres_loader_blocks_unconfirmed_reset_of_non_empty_target():
    cursor = _FakePostgresInspectionCursor({"users": 2})

    with pytest.raises(RuntimeError, match="Refusing to reset a non-empty Postgres target"):
        _validate_postgres_target_load_safety(
            cursor,
            reset_first=True,
            reset_confirmation=None,
        )


def test_postgres_loader_allows_confirmed_reset_of_non_empty_target():
    cursor = _FakePostgresInspectionCursor({"users": 2})

    safety = _validate_postgres_target_load_safety(
        cursor,
        reset_first=True,
        reset_confirmation=RESET_CONFIRMATION_TOKEN,
    )

    assert safety == {
        "existing_total_rows": 2,
        "non_empty_table_counts": {"users": 2},
        "reset_first": True,
        "reset_confirmation_required": True,
    }
