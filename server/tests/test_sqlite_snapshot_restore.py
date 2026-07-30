import hashlib
import json
import sqlite3

import pytest

from scripts.restore_sqlite_from_snapshot import restore_sqlite_from_snapshot


def _sha256(path):
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_manifest(export_dir, tables):
    manifest_tables = []
    for table_name in tables:
        path = export_dir / f"{table_name}.jsonl"
        row_count = len(path.read_text(encoding="utf-8").splitlines())
        manifest_tables.append(
            {
                "table": table_name,
                "file": path.name,
                "row_count": row_count,
                "byte_size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    (export_dir / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": "2026-07-30T12:00:00Z",
                "provider": "postgres",
                "tables": manifest_tables,
                "total_rows": sum(table["row_count"] for table in manifest_tables),
            }
        ),
        encoding="utf-8",
    )


def _create_schema_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute(
            """
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title TEXT
            )
            """
        )
        conn.execute("INSERT INTO users (id, username) VALUES (99, 'stale')")
        conn.execute(
            "INSERT INTO dailydiary_entries (id, user_id, title) VALUES (99, 99, 'stale')"
        )


def _create_snapshot(export_dir):
    export_dir.mkdir()
    _write_jsonl(export_dir / "users.jsonl", [{"id": 1, "username": "restored"}])
    _write_jsonl(
        export_dir / "dailydiary_entries.jsonl",
        [{"id": 10, "user_id": 1, "title": "from snapshot"}],
    )
    _write_manifest(export_dir, ["users", "dailydiary_entries"])


def test_restore_sqlite_from_snapshot_rebuilds_target_from_schema_template(tmp_path):
    schema_db = tmp_path / "schema.db"
    target_db = tmp_path / "restored.db"
    export_dir = tmp_path / "snapshot"
    _create_schema_db(schema_db)
    _create_snapshot(export_dir)

    report = restore_sqlite_from_snapshot(
        export_dir=export_dir,
        schema_db=schema_db,
        target_db=target_db,
    )

    assert report["restored"] is True
    assert report["loaded"] == {"users": 1, "dailydiary_entries": 1}
    assert report["total_loaded"] == 2
    assert report["manifest_total_rows"] == 2
    assert report["foreign_key_violations"] == []
    with sqlite3.connect(target_db) as conn:
        assert conn.execute("SELECT username FROM users").fetchone() == ("restored",)
        assert conn.execute("SELECT title FROM dailydiary_entries").fetchone() == (
            "from snapshot",
        )


def test_restore_sqlite_from_snapshot_refuses_existing_target_without_overwrite(tmp_path):
    schema_db = tmp_path / "schema.db"
    target_db = tmp_path / "restored.db"
    export_dir = tmp_path / "snapshot"
    _create_schema_db(schema_db)
    _create_snapshot(export_dir)
    target_db.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        restore_sqlite_from_snapshot(
            export_dir=export_dir,
            schema_db=schema_db,
            target_db=target_db,
        )


def test_restore_sqlite_from_snapshot_blocks_columns_missing_from_schema(tmp_path):
    schema_db = tmp_path / "schema.db"
    target_db = tmp_path / "restored.db"
    export_dir = tmp_path / "snapshot"
    _create_schema_db(schema_db)
    export_dir.mkdir()
    _write_jsonl(
        export_dir / "users.jsonl",
        [{"id": 1, "username": "restored", "unknown": "nope"}],
    )
    _write_manifest(export_dir, ["users"])

    with pytest.raises(ValueError, match="columns missing from SQLite schema"):
        restore_sqlite_from_snapshot(
            export_dir=export_dir,
            schema_db=schema_db,
            target_db=target_db,
        )
