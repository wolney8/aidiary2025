"""Validate database backup, restore, and maintenance evidence.

This script is read-only. It checks the operational evidence produced by the existing
backup/snapshot tools so public-readiness checks can fail before backup drift becomes a
production incident.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.create_sqlite_backup import BACKUP_FILE_PREFIX, DEFAULT_BACKUP_DIR
from scripts.export_postgres_snapshot import DEFAULT_SNAPSHOT_DIR
from scripts.run_database_backup_bundle import DEFAULT_MEDIA_BACKUP_DIR


DEFAULT_MAX_AGE_HOURS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_hours(value: Any, *, now: datetime) -> float | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return data


def _latest_file(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _add_gate(
    collection: list[dict[str, Any]],
    *,
    gate: str,
    message: str,
    severity: str = "blocker",
    **extra: Any,
) -> None:
    collection.append(
        {
            "gate": gate,
            "severity": severity,
            "message": message,
            **extra,
        }
    )


def _evidence_report(
    *,
    name: str,
    manifest: dict[str, Any],
    path: Path,
    now: datetime,
    max_age_hours: int,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    timestamp_key: str = "created_at",
) -> dict[str, Any]:
    created_at = manifest.get(timestamp_key)
    age = _age_hours(created_at, now=now)
    report = {
        "path": str(path),
        "created_at": created_at,
        "age_hours": round(age, 2) if age is not None else None,
    }
    if age is None:
        _add_gate(
            blockers,
            gate=f"{name}_timestamp",
            message=f"{name} evidence has no valid {timestamp_key} timestamp.",
            path=str(path),
        )
    elif age > max_age_hours:
        _add_gate(
            blockers,
            gate=f"{name}_stale",
            message=f"{name} evidence is older than {max_age_hours} hours.",
            path=str(path),
            age_hours=round(age, 2),
        )

    if manifest.get("ok") is False:
        _add_gate(
            blockers,
            gate=f"{name}_failed",
            message=f"{name} evidence reports failure.",
            path=str(path),
        )

    if name == "backup_bundle":
        counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
        report["counts"] = counts
        if int(counts.get("failed") or 0) > 0:
            _add_gate(
                blockers,
                gate="backup_bundle_failed_tasks",
                message="Backup bundle contains failed tasks.",
                path=str(path),
                failed=counts.get("failed"),
            )
        if int(counts.get("completed") or 0) == 0:
            _add_gate(
                warnings,
                gate="backup_bundle_no_completed_tasks",
                severity="warning",
                message="Backup bundle completed no tasks.",
                path=str(path),
            )

    return report


def _find_latest_bundle_summary(summary_dir: Path) -> Path | None:
    return _latest_file(sorted(summary_dir.glob("database-backup-bundle-*.json")))


def _find_latest_sqlite_manifest(sqlite_backup_dir: Path) -> Path | None:
    return _latest_file(
        sorted(sqlite_backup_dir.glob(f"{BACKUP_FILE_PREFIX}-*.manifest.json"))
    )


def _find_latest_postgres_manifest(postgres_snapshot_dir: Path) -> Path | None:
    return _latest_file(sorted(postgres_snapshot_dir.glob("**/manifest.json")))


def _find_latest_media_manifest(media_backup_dir: Path) -> Path | None:
    return _latest_file(sorted(media_backup_dir.glob("*.manifest.json")))


def build_database_maintenance_report(
    *,
    backup_summary_dir: Path,
    sqlite_backup_dir: Path,
    postgres_snapshot_dir: Path,
    media_backup_dir: Path,
    restore_report: Path | None = None,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
    require_backup_bundle: bool = True,
    require_sqlite_backup: bool = True,
    require_postgres_snapshot: bool = False,
    require_media_archive: bool = False,
    require_restore_rehearsal: bool = False,
    warn_total_rows: int | None = None,
    warn_backup_bytes: int | None = None,
) -> dict[str, Any]:
    now = _now()
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}

    backup_summary_dir = backup_summary_dir.expanduser().resolve()
    sqlite_backup_dir = sqlite_backup_dir.expanduser().resolve()
    postgres_snapshot_dir = postgres_snapshot_dir.expanduser().resolve()
    media_backup_dir = media_backup_dir.expanduser().resolve()

    latest_bundle = _find_latest_bundle_summary(backup_summary_dir)
    if latest_bundle:
        bundle = _load_json(latest_bundle)
        evidence["backup_bundle"] = _evidence_report(
            name="backup_bundle",
            manifest=bundle,
            path=latest_bundle,
            now=now,
            max_age_hours=max_age_hours,
            blockers=blockers,
            warnings=warnings,
        )
    elif require_backup_bundle:
        _add_gate(
            blockers,
            gate="backup_bundle_missing",
            message="No backup bundle summary was found.",
            directory=str(backup_summary_dir),
        )

    latest_sqlite = _find_latest_sqlite_manifest(sqlite_backup_dir)
    if latest_sqlite:
        sqlite_manifest = _load_json(latest_sqlite)
        sqlite_report = _evidence_report(
            name="sqlite_backup",
            manifest=sqlite_manifest,
            path=latest_sqlite,
            now=now,
            max_age_hours=max_age_hours,
            blockers=blockers,
            warnings=warnings,
        )
        sqlite_report["total_rows"] = sqlite_manifest.get("total_rows")
        sqlite_report["byte_size"] = sqlite_manifest.get("byte_size")
        evidence["sqlite_backup"] = sqlite_report
        if warn_total_rows and int(sqlite_manifest.get("total_rows") or 0) >= warn_total_rows:
            _add_gate(
                warnings,
                gate="sqlite_backup_row_capacity",
                severity="warning",
                message="SQLite backup row count is at or above the configured warning threshold.",
                total_rows=sqlite_manifest.get("total_rows"),
                threshold=warn_total_rows,
            )
        if warn_backup_bytes and int(sqlite_manifest.get("byte_size") or 0) >= warn_backup_bytes:
            _add_gate(
                warnings,
                gate="sqlite_backup_size_capacity",
                severity="warning",
                message="SQLite backup size is at or above the configured warning threshold.",
                byte_size=sqlite_manifest.get("byte_size"),
                threshold=warn_backup_bytes,
            )
    elif require_sqlite_backup:
        _add_gate(
            blockers,
            gate="sqlite_backup_missing",
            message="No SQLite backup manifest was found.",
            directory=str(sqlite_backup_dir),
        )

    latest_postgres = _find_latest_postgres_manifest(postgres_snapshot_dir)
    if latest_postgres:
        postgres_manifest = _load_json(latest_postgres)
        postgres_report = _evidence_report(
            name="postgres_snapshot",
            manifest=postgres_manifest,
            path=latest_postgres,
            now=now,
            max_age_hours=max_age_hours,
            blockers=blockers,
            warnings=warnings,
        )
        postgres_report["total_rows"] = postgres_manifest.get("total_rows")
        postgres_report["table_count"] = len(postgres_manifest.get("tables") or [])
        evidence["postgres_snapshot"] = postgres_report
        if warn_total_rows and int(postgres_manifest.get("total_rows") or 0) >= warn_total_rows:
            _add_gate(
                warnings,
                gate="postgres_snapshot_row_capacity",
                severity="warning",
                message="Postgres snapshot row count is at or above the configured warning threshold.",
                total_rows=postgres_manifest.get("total_rows"),
                threshold=warn_total_rows,
            )
    elif require_postgres_snapshot:
        _add_gate(
            blockers,
            gate="postgres_snapshot_missing",
            message="No Postgres snapshot manifest was found.",
            directory=str(postgres_snapshot_dir),
        )

    latest_media = _find_latest_media_manifest(media_backup_dir)
    if latest_media:
        media_manifest = _load_json(latest_media)
        media_report = _evidence_report(
            name="media_archive",
            manifest=media_manifest,
            path=latest_media,
            now=now,
            max_age_hours=max_age_hours,
            blockers=blockers,
            warnings=warnings,
        )
        media_report["file_count"] = media_manifest.get("file_count")
        media_report["archive_bytes"] = media_manifest.get("archive_bytes")
        evidence["media_archive"] = media_report
    elif require_media_archive:
        _add_gate(
            blockers,
            gate="media_archive_missing",
            message="No media archive manifest was found.",
            directory=str(media_backup_dir),
        )

    if restore_report:
        restore_report = restore_report.expanduser().resolve()
        if restore_report.exists():
            restore = _load_json(restore_report)
            restore_evidence = _evidence_report(
                name="restore_rehearsal",
                manifest=restore,
                path=restore_report,
                now=now,
                max_age_hours=max_age_hours,
                blockers=blockers,
                warnings=warnings,
            )
            restore_evidence["restored"] = restore.get("restored")
            restore_evidence["total_loaded"] = restore.get("total_loaded")
            evidence["restore_rehearsal"] = restore_evidence
            if restore.get("restored") is not True:
                _add_gate(
                    blockers,
                    gate="restore_rehearsal_failed",
                    message="Restore rehearsal report does not show a successful restore.",
                    path=str(restore_report),
                )
        elif require_restore_rehearsal:
            _add_gate(
                blockers,
                gate="restore_rehearsal_missing",
                message="Required restore rehearsal report was not found.",
                path=str(restore_report),
            )
    elif require_restore_rehearsal:
        _add_gate(
            blockers,
            gate="restore_rehearsal_missing",
            message="Restore rehearsal evidence is required but no restore report path was supplied.",
        )

    return {
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ready_for_database_maintenance": len(blockers) == 0,
        "max_age_hours": max_age_hours,
        "blockers": blockers,
        "warnings": warnings,
        "evidence": evidence,
        "summary": {
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "required": {
                "backup_bundle": require_backup_bundle,
                "sqlite_backup": require_sqlite_backup,
                "postgres_snapshot": require_postgres_snapshot,
                "media_archive": require_media_archive,
                "restore_rehearsal": require_restore_rehearsal,
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate OpenMynd database backup and restore maintenance evidence."
    )
    parser.add_argument(
        "--backup-summary-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing database-backup-bundle-*.json summaries.",
    )
    parser.add_argument(
        "--sqlite-backup-dir",
        default=str(DEFAULT_BACKUP_DIR),
        help="Directory containing openmynd-sqlite-*.manifest.json files.",
    )
    parser.add_argument(
        "--postgres-snapshot-dir",
        default=str(DEFAULT_SNAPSHOT_DIR),
        help="Directory containing Postgres snapshot manifest.json files.",
    )
    parser.add_argument(
        "--media-backup-dir",
        default=str(DEFAULT_MEDIA_BACKUP_DIR),
        help="Directory containing media archive manifest JSON files.",
    )
    parser.add_argument("--restore-report", help="Optional restore rehearsal report JSON.")
    parser.add_argument("--max-age-hours", type=int, default=DEFAULT_MAX_AGE_HOURS)
    parser.add_argument("--skip-backup-bundle", action="store_true")
    parser.add_argument("--skip-sqlite-backup", action="store_true")
    parser.add_argument("--require-postgres-snapshot", action="store_true")
    parser.add_argument("--require-media-archive", action="store_true")
    parser.add_argument("--require-restore-rehearsal", action="store_true")
    parser.add_argument("--warn-total-rows", type=int)
    parser.add_argument("--warn-backup-bytes", type=int)
    parser.add_argument("--output-json", help="Optional path to write the report JSON.")
    args = parser.parse_args()

    report = build_database_maintenance_report(
        backup_summary_dir=Path(args.backup_summary_dir),
        sqlite_backup_dir=Path(args.sqlite_backup_dir),
        postgres_snapshot_dir=Path(args.postgres_snapshot_dir),
        media_backup_dir=Path(args.media_backup_dir),
        restore_report=Path(args.restore_report) if args.restore_report else None,
        max_age_hours=args.max_age_hours,
        require_backup_bundle=not args.skip_backup_bundle,
        require_sqlite_backup=not args.skip_sqlite_backup,
        require_postgres_snapshot=args.require_postgres_snapshot,
        require_media_archive=args.require_media_archive,
        require_restore_rehearsal=args.require_restore_rehearsal,
        warn_total_rows=args.warn_total_rows,
        warn_backup_bytes=args.warn_backup_bytes,
    )
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready_for_database_maintenance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
