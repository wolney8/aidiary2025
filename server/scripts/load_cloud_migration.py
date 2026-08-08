"""Load exported migration JSONL rows into a Postgres rehearsal database.

Default mode is a dry-run plan. Use --apply only with a throwaway/staging
Postgres DATABASE_URL after reviewing the plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from scripts.rehearse_cloud_migration import TABLE_ORDER


SERVER_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SERVER_ROOT / "migrations" / "postgres" / "0001_initial_schema.sql"
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
QUOTED_IDENTIFIER_RE = re.compile(r'^"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"$')
IDENTITY_ID_TABLES = {
    "users",
    "auth_identities",
    "account_security_tokens",
    "billing_customers",
    "subscriptions",
    "entitlements",
    "billing_events",
    "usage_events",
    "configurations",
    "dailydiary_entries",
    "dreamdiary_entries",
    "import_history",
    "export_history",
    "entry_assets",
    "important_days",
    "public_holiday_cache",
    "entry_resurfacing_preferences",
    "reflection_summaries",
    "chat_messages",
    "chat_observability_events",
    "security_audit_events",
    "cbt_worksheets",
    "entry_ai_metadata",
}
RESET_CONFIRMATION_TOKEN = "RESET_NON_EMPTY_POSTGRES"
TABLE_CONSTRAINT_PREFIXES = (
    "CHECK",
    "CONSTRAINT",
    "EXCLUDE",
    "FOREIGN",
    "PRIMARY",
    "UNIQUE",
)


def _quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier}")
    return f'"{identifier}"'


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL in {path} line {line_number}") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_export_manifest(export_dir: Path) -> dict[str, Any] | None:
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid export manifest JSON: {manifest_path}") from exc


def _validate_export_manifest(
    export_dir: Path,
    manifest: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if manifest is None:
        return [
            {
                "gate": "manifest_missing",
                "message": "Export manifest.json is missing.",
            }
        ]
    mismatches = []
    for table in manifest.get("tables") or []:
        file_name = table.get("file")
        if not isinstance(file_name, str) or "/" in file_name or "\\" in file_name:
            mismatches.append(
                {
                    "gate": "manifest_file",
                    "table": table.get("table"),
                    "message": "Manifest file reference is invalid.",
                }
            )
            continue
        path = export_dir / file_name
        if not path.exists():
            mismatches.append(
                {
                    "gate": "manifest_file",
                    "table": table.get("table"),
                    "message": "Manifest file is missing from export directory.",
                }
            )
            continue
        actual_row_count = sum(1 for _row in _iter_jsonl(path))
        actual_byte_size = path.stat().st_size
        actual_sha256 = _sha256_file(path)
        if actual_row_count != table.get("row_count"):
            mismatches.append(
                {
                    "gate": "manifest_row_count",
                    "table": table.get("table"),
                    "expected": table.get("row_count"),
                    "actual": actual_row_count,
                }
            )
        if actual_byte_size != table.get("byte_size"):
            mismatches.append(
                {
                    "gate": "manifest_byte_size",
                    "table": table.get("table"),
                    "expected": table.get("byte_size"),
                    "actual": actual_byte_size,
                }
            )
        if actual_sha256 != table.get("sha256"):
            mismatches.append(
                {
                    "gate": "manifest_sha256",
                    "table": table.get("table"),
                    "expected": table.get("sha256"),
                    "actual": actual_sha256,
                }
            )
    return mismatches


def _split_sql_statements(sql: str) -> list[str]:
    statements = []
    current = []
    in_single_quote = False
    for character in sql:
        if character == "'":
            in_single_quote = not in_single_quote
        if character == ";" and not in_single_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _postgres_schema_columns(schema_sql: str | None = None) -> dict[str, set[str]]:
    sql = SCHEMA_PATH.read_text(encoding="utf-8") if schema_sql is None else schema_sql
    columns_by_table: dict[str, set[str]] = {}
    for table_name in TABLE_ORDER:
        table_match = re.search(
            rf"CREATE TABLE IF NOT EXISTS {table_name} \((?P<body>.*?)\n\);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not table_match:
            continue
        columns = set()
        for raw_line in table_match.group("body").splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            keyword = line.split(maxsplit=1)[0].upper()
            if keyword in TABLE_CONSTRAINT_PREFIXES:
                continue
            column_name = line.split(maxsplit=1)[0]
            quoted_match = QUOTED_IDENTIFIER_RE.match(column_name)
            if quoted_match:
                columns.add(quoted_match.group("name"))
            elif IDENTIFIER_RE.match(column_name):
                columns.add(column_name)
        columns_by_table[table_name] = columns
    return columns_by_table


def build_load_plan(export_dir: Path) -> dict[str, Any]:
    export_dir = export_dir.resolve()
    tables = []
    total_rows = 0
    schema_columns_by_table = _postgres_schema_columns()
    schema_column_mismatches = []
    export_manifest = _load_export_manifest(export_dir)
    manifest_mismatches = _validate_export_manifest(export_dir, export_manifest)
    for table_name in TABLE_ORDER:
        path = export_dir / f"{table_name}.jsonl"
        if not path.exists():
            tables.append(
                {
                    "table": table_name,
                    "exists": False,
                    "row_count": 0,
                    "columns": [],
                    "unknown_columns": [],
                }
            )
            continue
        rows = list(_iter_jsonl(path))
        columns = sorted({column for row in rows for column in row.keys()})
        unknown_columns = sorted(set(columns) - schema_columns_by_table.get(table_name, set()))
        if unknown_columns:
            schema_column_mismatches.append(
                {
                    "table": table_name,
                    "unknown_columns": unknown_columns,
                }
            )
        total_rows += len(rows)
        tables.append(
            {
                "table": table_name,
                "exists": True,
                "row_count": len(rows),
                "columns": columns,
                "unknown_columns": unknown_columns,
            }
        )
    return {
        "export_dir": str(export_dir),
        "schema_file": str(SCHEMA_PATH),
        "tables": tables,
        "total_rows": total_rows,
        "missing_files": [table["table"] for table in tables if not table["exists"]],
        "schema_column_mismatches": schema_column_mismatches,
        "manifest": (
            {
                "present": True,
                "total_rows": export_manifest.get("total_rows"),
            }
            if export_manifest
            else {"present": False, "total_rows": None}
        ),
        "manifest_mismatches": manifest_mismatches,
    }


def _insert_rows(cursor, table_name: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    columns = list(rows[0].keys())
    for row in rows:
        if list(row.keys()) != columns:
            raise ValueError(f"Inconsistent columns in {table_name}.jsonl")
    quoted_table = _quote_identifier(table_name)
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    statement = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})"
    values = [tuple(row[column] for column in columns) for row in rows]
    cursor.executemany(statement, values)
    return len(rows)


def _reset_identity_sequences(cursor, table_names: Iterable[str]) -> None:
    for table_name in table_names:
        if table_name not in IDENTITY_ID_TABLES:
            continue
        cursor.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence(%s, 'id'),
                COALESCE((SELECT MAX(id) FROM {_quote_identifier(table_name)}), 0) + 1,
                false
            )
            """,
            (table_name,),
        )


def _managed_table_row_counts(cursor, table_names: Iterable[str]) -> dict[str, int]:
    row_counts: dict[str, int] = {}
    for table_name in table_names:
        cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        table_ref = cursor.fetchone()
        if not table_ref or table_ref[0] is None:
            continue
        cursor.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}")
        row = cursor.fetchone()
        row_counts[table_name] = int(row[0] or 0)
    return row_counts


def _validate_postgres_target_load_safety(
    cursor,
    *,
    reset_first: bool,
    reset_confirmation: str | None,
) -> dict[str, Any]:
    row_counts = _managed_table_row_counts(cursor, TABLE_ORDER)
    non_empty_counts = {
        table_name: row_count
        for table_name, row_count in row_counts.items()
        if row_count > 0
    }
    existing_total_rows = sum(row_counts.values())

    if reset_first:
        if non_empty_counts and reset_confirmation != RESET_CONFIRMATION_TOKEN:
            raise RuntimeError(
                "Refusing to reset a non-empty Postgres target. Re-run with "
                f"--confirm-reset {RESET_CONFIRMATION_TOKEN} only after confirming "
                "this is a disposable rehearsal target or an approved cutover reset."
            )
    elif non_empty_counts:
        raise RuntimeError(
            "Refusing to load into a non-empty Postgres target without --reset-first. "
            "Use an empty target, or use --reset-first with explicit confirmation "
            "when overwriting is intentional."
        )

    return {
        "existing_total_rows": existing_total_rows,
        "non_empty_table_counts": non_empty_counts,
        "reset_first": reset_first,
        "reset_confirmation_required": bool(reset_first and non_empty_counts),
    }


def apply_export_to_postgres(
    *,
    database_url: str,
    export_dir: Path,
    reset_first: bool = False,
    reset_confirmation: str | None = None,
) -> dict[str, Any]:
    plan = build_load_plan(export_dir)
    if plan["schema_column_mismatches"]:
        raise ValueError(
            "Export contains columns not present in the Postgres schema: "
            f"{plan['schema_column_mismatches']}"
        )
    if plan["manifest_mismatches"]:
        raise ValueError(
            "Export manifest validation failed: "
            f"{plan['manifest_mismatches']}"
        )

    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            'psycopg is required for --apply. Install with: pip install "psycopg[binary]"'
        ) from exc
    loaded: dict[str, int] = {}
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    reset_safety: dict[str, Any] | None = None
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            for statement in _split_sql_statements(schema_sql):
                cursor.execute(statement)
            reset_safety = _validate_postgres_target_load_safety(
                cursor,
                reset_first=reset_first,
                reset_confirmation=reset_confirmation,
            )
            if reset_first:
                table_list = ", ".join(
                    _quote_identifier(table_name) for table_name in reversed(TABLE_ORDER)
                )
                cursor.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")
            for table_name in TABLE_ORDER:
                path = export_dir / f"{table_name}.jsonl"
                if not path.exists():
                    continue
                rows = list(_iter_jsonl(path))
                loaded[table_name] = _insert_rows(cursor, table_name, rows)
            _reset_identity_sequences(cursor, loaded.keys())
        conn.commit()

    return {
        "loaded": loaded,
        "total_loaded": sum(loaded.values()),
        "reset_safety": reset_safety,
        "source_plan": plan,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply a JSONL cloud migration export to Postgres."
    )
    parser.add_argument(
        "--export-dir",
        required=True,
        help="Directory produced by rehearse_cloud_migration.py --export-dir.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Postgres connection string. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create schema and insert rows. Default is dry-run only.",
    )
    parser.add_argument(
        "--reset-first",
        action="store_true",
        help="TRUNCATE managed migration tables before loading. Use only on rehearsal DBs.",
    )
    parser.add_argument(
        "--confirm-reset",
        default=None,
        help=(
            "Required token when --reset-first would wipe a non-empty Postgres target. "
            f"Use exactly: {RESET_CONFIRMATION_TOKEN}"
        ),
    )
    args = parser.parse_args()

    export_dir = Path(args.export_dir).expanduser().resolve()
    if not export_dir.exists():
        raise SystemExit(f"Export directory not found: {export_dir}")

    if not args.apply:
        print(json.dumps(build_load_plan(export_dir), ensure_ascii=False, indent=2))
        return 0

    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required with --apply")

    result = apply_export_to_postgres(
        database_url=args.database_url,
        export_dir=export_dir,
        reset_first=args.reset_first,
        reset_confirmation=args.confirm_reset,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
