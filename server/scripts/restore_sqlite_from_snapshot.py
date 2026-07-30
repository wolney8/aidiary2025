"""Restore a runnable SQLite database from a validated JSONL snapshot.

The target database schema is copied from an existing SQLite schema database. This keeps
the restore path aligned with the current runtime-managed SQLite schema while the app is
transitioning to formal cloud migrations.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.load_cloud_migration import (
    _load_export_manifest,
    _quote_identifier,
    _validate_export_manifest,
)
from scripts.rehearse_cloud_migration import TABLE_ORDER


SERVER_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_DB = SERVER_ROOT / "db" / "app.db"


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {path} line {line_number}") from exc


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table_name}")')}


def _clear_managed_tables(conn: sqlite3.Connection) -> None:
    for table_name in reversed(TABLE_ORDER):
        if _table_exists(conn, table_name):
            conn.execute(f"DELETE FROM {_quote_identifier(table_name)}")


def _insert_rows(conn: sqlite3.Connection, table_name: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    columns = list(rows[0].keys())
    for row in rows:
        if list(row.keys()) != columns:
            raise ValueError(f"Inconsistent columns in {table_name}.jsonl")
    sqlite_columns = _table_columns(conn, table_name)
    unknown_columns = sorted(set(columns) - sqlite_columns)
    if unknown_columns:
        raise ValueError(
            f"Snapshot table {table_name} contains columns missing from SQLite schema: "
            f"{unknown_columns}"
        )
    quoted_table = _quote_identifier(table_name)
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join(["?"] * len(columns))
    conn.executemany(
        f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})",
        [tuple(row[column] for column in columns) for row in rows],
    )
    return len(rows)


def restore_sqlite_from_snapshot(
    *,
    export_dir: Path,
    schema_db: Path,
    target_db: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    export_dir = export_dir.expanduser().resolve()
    schema_db = schema_db.expanduser().resolve()
    target_db = target_db.expanduser().resolve()

    if not export_dir.exists():
        raise FileNotFoundError(f"Snapshot export directory not found: {export_dir}")
    if not schema_db.exists():
        raise FileNotFoundError(f"SQLite schema database not found: {schema_db}")
    if target_db.exists() and not overwrite:
        raise FileExistsError(f"Target SQLite database already exists: {target_db}")

    manifest = _load_export_manifest(export_dir)
    manifest_mismatches = _validate_export_manifest(export_dir, manifest)
    if manifest_mismatches:
        raise ValueError(f"Snapshot manifest validation failed: {manifest_mismatches}")

    target_db.parent.mkdir(parents=True, exist_ok=True)
    if target_db.exists():
        target_db.unlink()
    shutil.copy2(schema_db, target_db)

    loaded: dict[str, int] = {}
    with sqlite3.connect(str(target_db), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = OFF")
        _clear_managed_tables(conn)
        for table_name in TABLE_ORDER:
            path = export_dir / f"{table_name}.jsonl"
            if not path.exists():
                continue
            rows = list(_iter_jsonl(path))
            loaded[table_name] = _insert_rows(conn, table_name, rows)
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()

    report = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "export_dir": str(export_dir),
        "schema_db": str(schema_db),
        "target_db": str(target_db),
        "loaded": loaded,
        "total_loaded": sum(loaded.values()),
        "manifest_total_rows": manifest.get("total_rows") if manifest else None,
        "foreign_key_violations": [dict(row) for row in violations],
        "restored": len(violations) == 0,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore a local SQLite database from a validated JSONL snapshot."
    )
    parser.add_argument("--export-dir", required=True, help="Snapshot directory containing manifest.json.")
    parser.add_argument(
        "--schema-db",
        default=os.getenv("SQLITE_RESTORE_SCHEMA_DB") or str(DEFAULT_SCHEMA_DB),
        help="SQLite database whose schema is used as the restore template.",
    )
    parser.add_argument("--target-db", required=True, help="SQLite database path to create.")
    parser.add_argument("--overwrite", action="store_true", help="Replace target DB if it exists.")
    parser.add_argument("--output-json", help="Optional path to write restore report JSON.")
    args = parser.parse_args()

    report = restore_sqlite_from_snapshot(
        export_dir=Path(args.export_dir),
        schema_db=Path(args.schema_db),
        target_db=Path(args.target_db),
        overwrite=args.overwrite,
    )
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["restored"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
