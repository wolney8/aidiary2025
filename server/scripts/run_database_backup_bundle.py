"""Run scheduled database backup tasks and write one operational summary.

The bundle is intentionally conservative:
- SQLite backup runs when the source database exists.
- Postgres snapshot runs only when DATABASE_URL or --database-url is supplied.
- Outputs stay outside the repository by default.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.create_sqlite_backup import DEFAULT_BACKUP_DIR, DEFAULT_DB_PATH, create_sqlite_backup
from scripts.export_postgres_snapshot import DEFAULT_SNAPSHOT_DIR, export_postgres_snapshot
from services.database import POSTGRES_PROVIDER
from services.database_adapter import DatabaseAdapter


BackupCallable = Callable[..., dict[str, Any]]
SnapshotCallable = Callable[..., dict[str, Any]]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_summary_path(output_dir: Path) -> Path:
    return output_dir.expanduser().resolve() / f"database-backup-bundle-{_utc_timestamp()}.json"


def run_database_backup_bundle(
    *,
    sqlite_source_db: Path,
    sqlite_backup_dir: Path,
    postgres_database_url: str | None,
    postgres_snapshot_dir: Path,
    label: str = "scheduled",
    sqlite_retain: int = 14,
    summary_json: Path | None = None,
    create_sqlite_backup_fn: BackupCallable = create_sqlite_backup,
    export_postgres_snapshot_fn: SnapshotCallable = export_postgres_snapshot,
) -> dict[str, Any]:
    sqlite_source_db = sqlite_source_db.expanduser().resolve()
    sqlite_backup_dir = sqlite_backup_dir.expanduser().resolve()
    postgres_snapshot_dir = postgres_snapshot_dir.expanduser().resolve()

    tasks: dict[str, Any] = {}
    exit_code = 0

    if sqlite_source_db.exists():
        try:
            tasks["sqlite_backup"] = {
                "status": "completed",
                "manifest": create_sqlite_backup_fn(
                    source_db=sqlite_source_db,
                    backup_dir=sqlite_backup_dir,
                    label=label,
                    retain=sqlite_retain,
                ),
            }
        except Exception as exc:  # pragma: no cover - exercised through injected tests.
            exit_code = 1
            tasks["sqlite_backup"] = {
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
    else:
        tasks["sqlite_backup"] = {
            "status": "skipped",
            "reason": f"SQLite source database not found: {sqlite_source_db}",
        }

    if postgres_database_url:
        try:
            tasks["postgres_snapshot"] = {
                "status": "completed",
                "manifest": export_postgres_snapshot_fn(
                    adapter=DatabaseAdapter(
                        provider=POSTGRES_PROVIDER,
                        sqlite_path="",
                        database_url=postgres_database_url,
                    ),
                    output_dir=postgres_snapshot_dir,
                    label=label,
                ),
            }
        except Exception as exc:  # pragma: no cover - exercised through injected tests.
            exit_code = 1
            tasks["postgres_snapshot"] = {
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
    else:
        tasks["postgres_snapshot"] = {
            "status": "skipped",
            "reason": "DATABASE_URL was not supplied.",
        }

    completed = sum(1 for task in tasks.values() if task["status"] == "completed")
    failed = sum(1 for task in tasks.values() if task["status"] == "failed")
    skipped = sum(1 for task in tasks.values() if task["status"] == "skipped")
    summary = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": label,
        "ok": failed == 0,
        "exit_code": exit_code,
        "counts": {
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        },
        "tasks": tasks,
    }

    output_path = summary_json.expanduser().resolve() if summary_json else _default_summary_path(sqlite_backup_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["summary_path"] = str(output_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run SQLite backup and optional Postgres snapshot tasks."
    )
    parser.add_argument(
        "--sqlite-source-db",
        default=os.getenv("DB_PATH") or str(DEFAULT_DB_PATH),
        help="SQLite source database for local fallback backup.",
    )
    parser.add_argument(
        "--sqlite-backup-dir",
        default=os.getenv("SQLITE_BACKUP_DIR") or str(DEFAULT_BACKUP_DIR),
        help="Directory for SQLite backups and default bundle summaries.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL") or "",
        help="Optional Postgres URL for cloud snapshot export.",
    )
    parser.add_argument(
        "--postgres-snapshot-dir",
        default=os.getenv("POSTGRES_SNAPSHOT_DIR") or str(DEFAULT_SNAPSHOT_DIR),
        help="Directory for Postgres JSONL snapshots.",
    )
    parser.add_argument(
        "--label",
        default=os.getenv("DATABASE_BACKUP_LABEL") or "scheduled",
        help="Short label included in generated backup/snapshot directories.",
    )
    parser.add_argument(
        "--sqlite-retain",
        type=int,
        default=int(os.getenv("SQLITE_BACKUP_RETAIN", "14")),
        help="Number of newest SQLite backups to retain.",
    )
    parser.add_argument(
        "--summary-json",
        help="Optional path for the backup bundle summary JSON.",
    )
    args = parser.parse_args()

    summary = run_database_backup_bundle(
        sqlite_source_db=Path(args.sqlite_source_db),
        sqlite_backup_dir=Path(args.sqlite_backup_dir),
        postgres_database_url=args.database_url.strip() or None,
        postgres_snapshot_dir=Path(args.postgres_snapshot_dir),
        label=args.label,
        sqlite_retain=args.sqlite_retain,
        summary_json=Path(args.summary_json) if args.summary_json else None,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(summary["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
