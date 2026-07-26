"""Run explicit Postgres migrations for cloud rehearsal/cutover.

Default mode prints a migration plan only. Use --apply with a rehearsal or
production DATABASE_URL after reviewing the pending versions.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from scripts.load_cloud_migration import _split_sql_statements


SERVER_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = SERVER_ROOT / "migrations" / "postgres"


@dataclass(frozen=True)
class MigrationFile:
    version: str
    path: Path


def discover_migrations(migrations_dir: Path = MIGRATIONS_DIR) -> list[MigrationFile]:
    migrations = [
        MigrationFile(version=path.stem, path=path)
        for path in migrations_dir.glob("*.sql")
        if path.is_file()
    ]
    return sorted(migrations, key=lambda migration: migration.version)


def ensure_migration_ledger(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def fetch_applied_versions(cursor) -> set[str]:
    ensure_migration_ledger(cursor)
    rows = cursor.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()
    return {str(row[0]) for row in rows}


def build_migration_plan(
    *,
    applied_versions: Iterable[str],
    migrations_dir: Path = MIGRATIONS_DIR,
) -> dict[str, Any]:
    applied = set(applied_versions)
    migrations = discover_migrations(migrations_dir)
    pending = [migration for migration in migrations if migration.version not in applied]
    return {
        "migrations_dir": str(migrations_dir.resolve()),
        "applied_versions": sorted(applied),
        "pending_versions": [migration.version for migration in pending],
        "all_versions": [migration.version for migration in migrations],
    }


def apply_pending_migrations(
    *,
    database_url: str,
    migrations_dir: Path = MIGRATIONS_DIR,
) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            'psycopg is required for --apply. Install with: pip install "psycopg[binary]"'
        ) from exc

    applied_now: list[str] = []
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            applied_versions = fetch_applied_versions(cursor)
            plan = build_migration_plan(
                applied_versions=applied_versions,
                migrations_dir=migrations_dir,
            )
            pending_versions = set(plan["pending_versions"])
            for migration in discover_migrations(migrations_dir):
                if migration.version not in pending_versions:
                    continue
                for statement in _split_sql_statements(
                    migration.path.read_text(encoding="utf-8")
                ):
                    cursor.execute(statement)
                cursor.execute(
                    """
                    INSERT INTO schema_migrations (version)
                    VALUES (%s)
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (migration.version,),
                )
                applied_now.append(migration.version)
        conn.commit()

    return {
        "migrations_dir": str(migrations_dir.resolve()),
        "applied_versions": applied_now,
        "applied_count": len(applied_now),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or apply explicit Postgres schema migrations."
    )
    parser.add_argument(
        "--migrations-dir",
        default=str(MIGRATIONS_DIR),
        help="Directory containing ordered Postgres .sql migration files.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Postgres connection string. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply pending migrations. Default prints the discovered migration plan.",
    )
    args = parser.parse_args()

    migrations_dir = Path(args.migrations_dir).expanduser().resolve()
    if not migrations_dir.exists():
        raise SystemExit(f"Migrations directory not found: {migrations_dir}")

    if not args.apply:
        plan = build_migration_plan(applied_versions=[], migrations_dir=migrations_dir)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL is required with --apply")

    result = apply_pending_migrations(
        database_url=args.database_url,
        migrations_dir=migrations_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
