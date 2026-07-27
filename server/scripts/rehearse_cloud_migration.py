"""Audit and export SQLite data before cloud Postgres migration rehearsal.

This script is deliberately safe by default: it reads a SQLite database, reports
schema/count/integrity signals, and optionally exports table rows as JSONL.
It does not write to a cloud database yet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVER_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = SERVER_ROOT / "db" / "app.db"

TABLE_ORDER = [
    "users",
    "configurations",
    "dailydiary_entries",
    "dreamdiary_entries",
    "entry_ai_metadata",
    "import_history",
    "export_history",
    "entry_assets",
    "import_sessions",
    "import_jobs",
    "important_days",
    "public_holiday_cache",
    "entry_resurfacing_preferences",
    "reflection_summaries",
    "chat_messages",
    "chat_observability_events",
    "cbt_worksheets",
    "cbt_thought_record_data",
]

FOREIGN_KEY_CHECKS = [
    ("dailydiary_entries", "user_id", "users", "id"),
    ("dreamdiary_entries", "user_id", "users", "id"),
    ("entry_ai_metadata", "user_id", "users", "id"),
    ("export_history", "user_id", "users", "id"),
    ("entry_assets", "user_id", "users", "id"),
    ("important_days", "user_id", "users", "id"),
    ("entry_resurfacing_preferences", "user_id", "users", "id"),
    ("reflection_summaries", "user_id", "users", "id"),
    ("chat_messages", "user_id", "users", "id"),
    ("chat_observability_events", "user_id", "users", "id"),
    ("cbt_worksheets", "user_id", "users", "id"),
    ("cbt_thought_record_data", "worksheet_id", "cbt_worksheets", "id"),
]


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    if not _table_exists(conn, table_name):
        return []
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table_name})")]


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS total FROM {table_name}").fetchone()
    return int(row["total"] or 0)


def _load_schema_sql(conn: sqlite3.Connection, table_name: str) -> str | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return str(row["sql"]) if row and row["sql"] else None


def _orphan_count(
    conn: sqlite3.Connection,
    child_table: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
) -> int | None:
    if not _table_exists(conn, child_table) or not _table_exists(conn, parent_table):
        return None
    child_columns = set(_table_columns(conn, child_table))
    parent_columns = set(_table_columns(conn, parent_table))
    if child_column not in child_columns or parent_column not in parent_columns:
        return None
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM {child_table} child
        LEFT JOIN {parent_table} parent
          ON child.{child_column} = parent.{parent_column}
        WHERE child.{child_column} IS NOT NULL
          AND parent.{parent_column} IS NULL
        """
    ).fetchone()
    return int(row["total"] or 0)


def _media_reference_checks(conn: sqlite3.Connection) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    if _table_exists(conn, "entry_assets"):
        checks["entry_assets_missing_storage_key"] = int(
            conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM entry_assets
                WHERE COALESCE(TRIM(storage_key), '') = ''
                """
            ).fetchone()["total"]
            or 0
        )
    for table_name in ("dailydiary_entries", "dreamdiary_entries", "important_days"):
        columns = set(_table_columns(conn, table_name))
        if {"image_url", "image_storage_key"}.issubset(columns):
            checks[f"{table_name}_legacy_inline_images"] = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) AS total
                    FROM {table_name}
                    WHERE image_url LIKE 'data:image/%'
                      AND COALESCE(TRIM(image_storage_key), '') = ''
                    """
                ).fetchone()["total"]
                or 0
            )
    return checks


def build_report(db_path: Path) -> dict[str, Any]:
    with _connect(db_path) as conn:
        tables = []
        for table_name in TABLE_ORDER:
            exists = _table_exists(conn, table_name)
            tables.append(
                {
                    "name": table_name,
                    "exists": exists,
                    "row_count": _count_rows(conn, table_name) if exists else 0,
                    "columns": _table_columns(conn, table_name),
                    "sqlite_schema": _load_schema_sql(conn, table_name) if exists else None,
                }
            )

        orphan_checks = []
        for child_table, child_column, parent_table, parent_column in FOREIGN_KEY_CHECKS:
            orphan_checks.append(
                {
                    "child_table": child_table,
                    "child_column": child_column,
                    "parent_table": parent_table,
                    "parent_column": parent_column,
                    "orphan_count": _orphan_count(
                        conn,
                        child_table,
                        child_column,
                        parent_table,
                        parent_column,
                    ),
                }
            )

        report = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_db": str(db_path),
            "tables": tables,
            "foreign_key_checks": orphan_checks,
            "media_reference_checks": _media_reference_checks(conn),
        }
        report["summary"] = {
            "tables_present": sum(1 for table in tables if table["exists"]),
            "tables_missing": [table["name"] for table in tables if not table["exists"]],
            "total_rows": sum(int(table["row_count"]) for table in tables),
            "orphan_issues": [
                check for check in orphan_checks if (check["orphan_count"] or 0) > 0
            ],
        }
        return report


def export_jsonl(db_path: Path, export_dir: Path) -> list[str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    manifest_tables = []
    with _connect(db_path) as conn:
        for table_name in TABLE_ORDER:
            if not _table_exists(conn, table_name):
                continue
            output_path = export_dir / f"{table_name}.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY rowid").fetchall()
                for row in rows:
                    handle.write(json.dumps(dict(row), ensure_ascii=False, default=str))
                    handle.write("\n")
            written.append(str(output_path))
            manifest_tables.append(
                {
                    "table": table_name,
                    "file": output_path.name,
                    "row_count": len(rows),
                    "byte_size": output_path.stat().st_size,
                    "sha256": _sha256_file(output_path),
                }
            )
    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_db": str(db_path),
        "tables": manifest_tables,
        "total_rows": sum(table["row_count"] for table in manifest_tables),
    }
    (export_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return written


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit and optionally export SQLite rows for cloud migration rehearsal."
    )
    parser.add_argument(
        "--source-db",
        default=os.getenv("DB_PATH") or str(DEFAULT_DB_PATH),
        help="SQLite source database. Defaults to DB_PATH or server/db/app.db.",
    )
    parser.add_argument(
        "--report-json",
        help="Optional path to write the migration readiness report as JSON.",
    )
    parser.add_argument(
        "--export-dir",
        help="Optional directory for table JSONL exports.",
    )
    args = parser.parse_args()

    source_db = Path(args.source_db).expanduser().resolve()
    if not source_db.exists():
        raise SystemExit(f"Source database not found: {source_db}")

    report = build_report(source_db)
    if args.export_dir:
        export_dir = Path(args.export_dir).expanduser().resolve()
        report["exported_files"] = export_jsonl(
            source_db,
            export_dir,
        )
        report["export_manifest"] = str(export_dir / "manifest.json")

    report_text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_json:
        report_path = Path(args.report_json).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text + "\n", encoding="utf-8")
    else:
        print(report_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
