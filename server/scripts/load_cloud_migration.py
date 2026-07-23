"""Load exported migration JSONL rows into a Postgres rehearsal database.

Default mode is a dry-run plan. Use --apply only with a throwaway/staging
Postgres DATABASE_URL after reviewing the plan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from scripts.rehearse_cloud_migration import TABLE_ORDER


SERVER_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = SERVER_ROOT / "migrations" / "postgres" / "0001_initial_schema.sql"
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
IDENTITY_ID_TABLES = {
    "users",
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
    "cbt_worksheets",
    "entry_ai_metadata",
}


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


def build_load_plan(export_dir: Path) -> dict[str, Any]:
    export_dir = export_dir.resolve()
    tables = []
    total_rows = 0
    for table_name in TABLE_ORDER:
        path = export_dir / f"{table_name}.jsonl"
        if not path.exists():
            tables.append(
                {
                    "table": table_name,
                    "exists": False,
                    "row_count": 0,
                    "columns": [],
                }
            )
            continue
        rows = list(_iter_jsonl(path))
        columns = sorted({column for row in rows for column in row.keys()})
        total_rows += len(rows)
        tables.append(
            {
                "table": table_name,
                "exists": True,
                "row_count": len(rows),
                "columns": columns,
            }
        )
    return {
        "export_dir": str(export_dir),
        "schema_file": str(SCHEMA_PATH),
        "tables": tables,
        "total_rows": total_rows,
        "missing_files": [table["table"] for table in tables if not table["exists"]],
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


def apply_export_to_postgres(
    *,
    database_url: str,
    export_dir: Path,
    reset_first: bool = False,
) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            'psycopg is required for --apply. Install with: pip install "psycopg[binary]"'
        ) from exc

    plan = build_load_plan(export_dir)
    loaded: dict[str, int] = {}
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            for statement in _split_sql_statements(schema_sql):
                cursor.execute(statement)
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
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
