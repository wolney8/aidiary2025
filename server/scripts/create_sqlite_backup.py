"""Create a consistent local SQLite backup with retention metadata.

This is for local fallback and pre-cutover safety. It uses SQLite's backup API rather
than copying files directly, so WAL-backed databases produce a coherent snapshot.
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
DEFAULT_BACKUP_DIR = Path.home() / "AIDiaryBackups"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_label(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in label.strip())
    return cleaned.strip("-_") or "manual"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _table_counts(db_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(str(db_path), timeout=30) as conn:
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        for (table_name,) in table_rows:
            if str(table_name).startswith("sqlite_"):
                continue
            count_row = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
            counts[str(table_name)] = int(count_row[0] or 0)
    return counts


def _backup_files(backup_dir: Path) -> list[Path]:
    return sorted(
        backup_dir.glob("aidiary-sqlite-*.db"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )


def _next_backup_path(backup_dir: Path, label: str) -> Path:
    stem = f"aidiary-sqlite-{_utc_timestamp()}-{_safe_label(label)}"
    candidate = backup_dir / f"{stem}.db"
    suffix = 2
    while candidate.exists():
        candidate = backup_dir / f"{stem}-{suffix}.db"
        suffix += 1
    return candidate


def _prune_old_backups(backup_dir: Path, retain: int) -> list[str]:
    if retain <= 0:
        return []
    removed: list[str] = []
    for stale_backup in _backup_files(backup_dir)[retain:]:
        manifest_path = stale_backup.with_suffix(".manifest.json")
        stale_backup.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        removed.append(str(stale_backup))
    return removed


def create_sqlite_backup(
    *,
    source_db: Path,
    backup_dir: Path,
    label: str = "manual",
    retain: int = 14,
) -> dict[str, Any]:
    source_db = source_db.expanduser().resolve()
    backup_dir = backup_dir.expanduser().resolve()
    if not source_db.exists():
        raise FileNotFoundError(f"SQLite source database not found: {source_db}")
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_path = _next_backup_path(backup_dir, label)
    with sqlite3.connect(str(source_db), timeout=30) as source_conn:
        with sqlite3.connect(str(backup_path), timeout=30) as backup_conn:
            source_conn.backup(backup_conn)

    table_counts = _table_counts(backup_path)
    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_db": str(source_db),
        "backup_path": str(backup_path),
        "provider": "sqlite",
        "label": _safe_label(label),
        "byte_size": backup_path.stat().st_size,
        "sha256": _sha256_file(backup_path),
        "table_counts": table_counts,
        "total_rows": sum(table_counts.values()),
        "retention": {"retain": retain, "removed": _prune_old_backups(backup_dir, retain)},
    }
    manifest_path = backup_path.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite backup.")
    parser.add_argument(
        "--source-db",
        default=os.getenv("DB_PATH") or str(DEFAULT_DB_PATH),
        help="SQLite database to back up. Defaults to DB_PATH or server/db/app.db.",
    )
    parser.add_argument(
        "--backup-dir",
        default=os.getenv("SQLITE_BACKUP_DIR") or str(DEFAULT_BACKUP_DIR),
        help="Directory where backup files are written. Defaults to SQLITE_BACKUP_DIR or ~/AIDiaryBackups.",
    )
    parser.add_argument(
        "--label",
        default=os.getenv("SQLITE_BACKUP_LABEL") or "manual",
        help="Short label included in the backup filename.",
    )
    parser.add_argument(
        "--retain",
        type=int,
        default=int(os.getenv("SQLITE_BACKUP_RETAIN", "14")),
        help="Number of newest backups to retain in the backup directory.",
    )
    parser.add_argument("--output-json", help="Optional path for a copy of the manifest JSON.")
    args = parser.parse_args()

    manifest = create_sqlite_backup(
        source_db=Path(args.source_db),
        backup_dir=Path(args.backup_dir),
        label=args.label,
        retain=args.retain,
    )
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
