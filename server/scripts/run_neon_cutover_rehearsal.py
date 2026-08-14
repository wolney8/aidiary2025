"""Prepare or apply a local SQLite to Neon/Postgres cutover rehearsal.

Default mode is local-only and safe: create a coherent SQLite backup, export JSONL rows,
and build a Postgres load plan. Use --apply only when DATABASE_URL points to the intended
Neon/Postgres target.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.create_sqlite_backup import create_sqlite_backup
from scripts.load_cloud_migration import apply_export_to_postgres, build_load_plan
from scripts.rehearse_cloud_migration import DEFAULT_DB_PATH, build_report, export_jsonl
from scripts.run_postgres_migrations import apply_pending_migrations


DEFAULT_WORK_ROOT = Path.home() / "OpenMyndBackups" / "neon-rehearsals"
RESET_CONFIRMATION_TOKEN = "RESET_NON_EMPTY_POSTGRES"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_neon_cutover_rehearsal(
    *,
    source_db: Path = DEFAULT_DB_PATH,
    work_dir: Path | None = None,
    backup_dir: Path | None = None,
    database_url: str | None = None,
    apply: bool = False,
    reset_first: bool = False,
    confirm_reset: str | None = None,
) -> dict[str, Any]:
    resolved_work_dir = (work_dir or DEFAULT_WORK_ROOT / _utc_timestamp()).expanduser().resolve()
    resolved_backup_dir = (
        backup_dir or resolved_work_dir / "sqlite-backups"
    ).expanduser().resolve()
    export_dir = resolved_work_dir / "jsonl-export"
    migration_report_path = resolved_work_dir / "migration-report.json"
    load_plan_path = resolved_work_dir / "postgres-load-plan.json"
    result_path = resolved_work_dir / "neon-cutover-rehearsal.json"
    resolved_work_dir.mkdir(parents=True, exist_ok=True)

    backup_manifest = create_sqlite_backup(
        source_db=source_db,
        backup_dir=resolved_backup_dir,
        label="neon-cutover-rehearsal",
        retain=14,
    )
    backup_path = Path(str(backup_manifest["backup_path"]))
    migration_report = build_report(backup_path)
    migration_report["exported_files"] = export_jsonl(backup_path, export_dir)
    migration_report["export_manifest"] = str(export_dir / "manifest.json")
    migration_report_path.write_text(
        json.dumps(migration_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    load_plan = build_load_plan(export_dir)
    load_plan_path.write_text(
        json.dumps(load_plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    postgres_migration_result = None
    postgres_load_result = None
    if apply:
        if not database_url:
            raise RuntimeError("--database-url or DATABASE_URL is required with --apply")
        postgres_migration_result = apply_pending_migrations(database_url=database_url)
        postgres_load_result = apply_export_to_postgres(
            database_url=database_url,
            export_dir=export_dir,
            reset_first=reset_first,
            reset_confirmation=confirm_reset,
        )

    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_db": str(source_db.expanduser().resolve()),
        "work_dir": str(resolved_work_dir),
        "apply": apply,
        "sqlite_backup": backup_manifest,
        "migration_report_path": str(migration_report_path),
        "export_dir": str(export_dir),
        "load_plan_path": str(load_plan_path),
        "load_plan_summary": {
            "total_rows": load_plan["total_rows"],
            "missing_files": load_plan["missing_files"],
            "schema_column_mismatches": load_plan["schema_column_mismatches"],
            "manifest_mismatches": load_plan["manifest_mismatches"],
        },
        "postgres_migrations": postgres_migration_result,
        "postgres_load": postgres_load_result,
    }
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result["result_path"] = str(result_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or apply a SQLite to Neon/Postgres cutover rehearsal."
    )
    parser.add_argument(
        "--source-db",
        default=os.getenv("DB_PATH") or str(DEFAULT_DB_PATH),
        help="SQLite source database. Defaults to DB_PATH or server/db/app.db.",
    )
    parser.add_argument(
        "--work-dir",
        help="Directory for backup/export/rehearsal artifacts. Defaults under ~/OpenMyndBackups.",
    )
    parser.add_argument(
        "--backup-dir",
        help="Directory for the SQLite backup. Defaults under --work-dir.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Neon/Postgres target. Defaults to DATABASE_URL.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply migrations and load data.")
    parser.add_argument(
        "--reset-first",
        action="store_true",
        help="Truncate managed Postgres tables before loading. Use only on rehearsal targets.",
    )
    parser.add_argument(
        "--confirm-reset",
        default=None,
        help=f"Required token for resetting non-empty targets: {RESET_CONFIRMATION_TOKEN}",
    )
    args = parser.parse_args()

    result = run_neon_cutover_rehearsal(
        source_db=Path(args.source_db),
        work_dir=Path(args.work_dir) if args.work_dir else None,
        backup_dir=Path(args.backup_dir) if args.backup_dir else None,
        database_url=args.database_url,
        apply=args.apply,
        reset_first=args.reset_first,
        confirm_reset=args.confirm_reset,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
