"""Run scheduled database backup tasks and write one operational summary.

The bundle is intentionally conservative:
- SQLite backup runs when the source database exists.
- Postgres snapshot runs only when DATABASE_URL or --database-url is supplied.
- Outputs stay outside the repository by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from scripts.create_sqlite_backup import DEFAULT_BACKUP_DIR, DEFAULT_DB_PATH, create_sqlite_backup
from scripts.export_postgres_snapshot import DEFAULT_SNAPSHOT_DIR, export_postgres_snapshot
from services.database import POSTGRES_PROVIDER
from services.database_adapter import DatabaseAdapter


BackupCallable = Callable[..., dict[str, Any]]
SnapshotCallable = Callable[..., dict[str, Any]]
MediaBackupCallable = Callable[..., dict[str, Any]]
NotifyCallable = Callable[..., dict[str, Any]]
NotifyMode = Literal["failure", "always", "never"]
SECRET_URL_RE = re.compile(r"postgres(?:ql)?://[^\s'\"<>]+", re.IGNORECASE)
DEFAULT_MEDIA_ROOT = Path(__file__).resolve().parents[1] / "media"
DEFAULT_MEDIA_BACKUP_DIR = Path.home() / "OpenMyndBackups" / "media"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_summary_path(output_dir: Path) -> Path:
    return output_dir.expanduser().resolve() / f"database-backup-bundle-{_utc_timestamp()}.json"


def _redact_secrets(value: Any) -> Any:
    if isinstance(value, str):
        return SECRET_URL_RE.sub("postgresql://<redacted>", value)
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_secrets(item) for key, item in value.items()}
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_label(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", label.strip().lower()).strip("-") or "backup"


def create_media_archive(
    *,
    media_root: Path,
    output_dir: Path,
    label: str = "scheduled",
) -> dict[str, Any]:
    media_root = media_root.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"openmynd-media-{_utc_timestamp()}-{_safe_label(label)}.zip"

    files = sorted(path for path in media_root.rglob("*") if path.is_file())
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, f"media/{path.relative_to(media_root).as_posix()}")

    manifest = {
        "provider": "local_media",
        "label": label,
        "media_root": str(media_root),
        "archive_path": str(archive_path),
        "file_count": len(files),
        "source_bytes": sum(path.stat().st_size for path in files),
        "archive_bytes": archive_path.stat().st_size,
        "sha256": _sha256_file(archive_path),
    }
    manifest_path = archive_path.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def send_backup_webhook_notification(
    *,
    webhook_url: str,
    summary: dict[str, Any],
    timeout_seconds: float = 10,
) -> dict[str, Any]:
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - dependency exists in normal runtime.
        raise RuntimeError("httpx is required for webhook notifications") from exc

    payload = {
        "event": "openmynd.database_backup_bundle",
        "ok": summary.get("ok") is True,
        "created_at": summary.get("created_at"),
        "label": summary.get("label"),
        "counts": summary.get("counts"),
        "summary_path": summary.get("summary_path"),
        "tasks": summary.get("tasks"),
    }
    response = httpx.post(
        webhook_url,
        json=_redact_secrets(payload),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return {
        "status": "sent",
        "status_code": response.status_code,
    }


def _maybe_send_notification(
    *,
    summary: dict[str, Any],
    webhook_url: str | None,
    notify_mode: NotifyMode,
    notify_fn: NotifyCallable = send_backup_webhook_notification,
) -> dict[str, Any]:
    if not webhook_url or notify_mode == "never":
        return {
            "status": "skipped",
            "reason": "notification disabled",
        }
    if notify_mode == "failure" and summary.get("ok") is True:
        return {
            "status": "skipped",
            "reason": "backup bundle completed successfully",
        }
    try:
        return notify_fn(webhook_url=webhook_url, summary=summary)
    except Exception as exc:
        return {
            "status": "failed",
            "error_type": exc.__class__.__name__,
            "message": _redact_secrets(str(exc)),
        }


def run_database_backup_bundle(
    *,
    sqlite_source_db: Path,
    sqlite_backup_dir: Path,
    postgres_database_url: str | None,
    postgres_snapshot_dir: Path,
    media_root: Path | None = None,
    media_backup_dir: Path | None = None,
    label: str = "scheduled",
    sqlite_retain: int = 14,
    summary_json: Path | None = None,
    notification_webhook_url: str | None = None,
    notify_mode: NotifyMode = "failure",
    create_sqlite_backup_fn: BackupCallable = create_sqlite_backup,
    export_postgres_snapshot_fn: SnapshotCallable = export_postgres_snapshot,
    create_media_archive_fn: MediaBackupCallable = create_media_archive,
    notify_fn: NotifyCallable = send_backup_webhook_notification,
) -> dict[str, Any]:
    sqlite_source_db = sqlite_source_db.expanduser().resolve()
    sqlite_backup_dir = sqlite_backup_dir.expanduser().resolve()
    postgres_snapshot_dir = postgres_snapshot_dir.expanduser().resolve()
    resolved_media_root = media_root.expanduser().resolve() if media_root else None
    resolved_media_backup_dir = (
        media_backup_dir.expanduser().resolve() if media_backup_dir else DEFAULT_MEDIA_BACKUP_DIR
    )

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
                "message": _redact_secrets(str(exc)),
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
                "message": _redact_secrets(str(exc)),
            }
    else:
        tasks["postgres_snapshot"] = {
            "status": "skipped",
            "reason": "DATABASE_URL was not supplied.",
        }

    if resolved_media_root is None:
        tasks["media_archive"] = {
            "status": "skipped",
            "reason": "MEDIA_ROOT was not supplied.",
        }
    elif resolved_media_root.exists():
        try:
            tasks["media_archive"] = {
                "status": "completed",
                "manifest": create_media_archive_fn(
                    media_root=resolved_media_root,
                    output_dir=resolved_media_backup_dir,
                    label=label,
                ),
            }
        except Exception as exc:  # pragma: no cover - exercised through injected tests.
            exit_code = 1
            tasks["media_archive"] = {
                "status": "failed",
                "error_type": exc.__class__.__name__,
                "message": _redact_secrets(str(exc)),
            }
    else:
        tasks["media_archive"] = {
            "status": "skipped",
            "reason": f"Media root not found: {resolved_media_root}",
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
    summary["notification"] = _maybe_send_notification(
        summary=summary,
        webhook_url=notification_webhook_url,
        notify_mode=notify_mode,
        notify_fn=notify_fn,
    )
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        "--media-root",
        default=os.getenv("MEDIA_ROOT") or str(DEFAULT_MEDIA_ROOT),
        help="Media root to archive with the database backups.",
    )
    parser.add_argument(
        "--media-backup-dir",
        default=os.getenv("MEDIA_BACKUP_DIR") or str(DEFAULT_MEDIA_BACKUP_DIR),
        help="Directory for media zip archives.",
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
    parser.add_argument(
        "--notification-webhook-url",
        default=os.getenv("DATABASE_BACKUP_WEBHOOK_URL") or "",
        help="Optional webhook URL for backup bundle notifications.",
    )
    parser.add_argument(
        "--notify",
        choices=("failure", "always", "never"),
        default=os.getenv("DATABASE_BACKUP_NOTIFY", "failure"),
        help="When to send webhook notifications. Defaults to failure.",
    )
    args = parser.parse_args()

    summary = run_database_backup_bundle(
        sqlite_source_db=Path(args.sqlite_source_db),
        sqlite_backup_dir=Path(args.sqlite_backup_dir),
        postgres_database_url=args.database_url.strip() or None,
        postgres_snapshot_dir=Path(args.postgres_snapshot_dir),
        media_root=Path(args.media_root) if args.media_root.strip() else None,
        media_backup_dir=Path(args.media_backup_dir),
        label=args.label,
        sqlite_retain=args.sqlite_retain,
        summary_json=Path(args.summary_json) if args.summary_json else None,
        notification_webhook_url=args.notification_webhook_url.strip() or None,
        notify_mode=args.notify,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return int(summary["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
