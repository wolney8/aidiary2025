import json
from datetime import datetime, timedelta, timezone

from scripts.validate_database_maintenance import build_database_maintenance_report


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _iso(hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _write_complete_evidence(tmp_path, *, created_at=None):
    created_at = created_at or _iso()
    backup_dir = tmp_path / "backups"
    postgres_dir = tmp_path / "postgres-snapshots" / "postgres-20260808T120000Z-daily"
    media_dir = tmp_path / "media-backups"
    restore_report = tmp_path / "restore-report.json"

    _write_json(
        backup_dir / "database-backup-bundle-20260808T120000Z.json",
        {
            "created_at": created_at,
            "ok": True,
            "counts": {"completed": 3, "failed": 0, "skipped": 0},
        },
    )
    _write_json(
        backup_dir / "openmynd-sqlite-20260808T120000Z-daily.manifest.json",
        {
            "created_at": created_at,
            "provider": "sqlite",
            "total_rows": 42,
            "byte_size": 2048,
        },
    )
    _write_json(
        postgres_dir / "manifest.json",
        {
            "created_at": created_at,
            "provider": "postgres",
            "tables": [{"table": "users"}],
            "total_rows": 42,
        },
    )
    _write_json(
        media_dir / "openmynd-media-20260808T120000Z-daily.manifest.json",
        {
            "created_at": created_at,
            "provider": "local_media",
            "file_count": 2,
            "archive_bytes": 4096,
        },
    )
    _write_json(
        restore_report,
        {
            "created_at": created_at,
            "restored": True,
            "total_loaded": 42,
        },
    )
    return backup_dir, postgres_dir.parent, media_dir, restore_report


def test_database_maintenance_validation_passes_with_complete_recent_evidence(tmp_path):
    backup_dir, postgres_dir, media_dir, restore_report = _write_complete_evidence(tmp_path)

    report = build_database_maintenance_report(
        backup_summary_dir=backup_dir,
        sqlite_backup_dir=backup_dir,
        postgres_snapshot_dir=postgres_dir,
        media_backup_dir=media_dir,
        restore_report=restore_report,
        require_postgres_snapshot=True,
        require_media_archive=True,
        require_restore_rehearsal=True,
    )

    assert report["ready_for_database_maintenance"] is True
    assert report["blockers"] == []
    assert report["evidence"]["backup_bundle"]["counts"]["completed"] == 3
    assert report["evidence"]["sqlite_backup"]["total_rows"] == 42
    assert report["evidence"]["postgres_snapshot"]["table_count"] == 1
    assert report["evidence"]["restore_rehearsal"]["restored"] is True


def test_database_maintenance_validation_blocks_stale_evidence(tmp_path):
    backup_dir, postgres_dir, media_dir, restore_report = _write_complete_evidence(
        tmp_path,
        created_at=_iso(hours_ago=48),
    )

    report = build_database_maintenance_report(
        backup_summary_dir=backup_dir,
        sqlite_backup_dir=backup_dir,
        postgres_snapshot_dir=postgres_dir,
        media_backup_dir=media_dir,
        restore_report=restore_report,
        max_age_hours=24,
        require_postgres_snapshot=True,
        require_media_archive=True,
        require_restore_rehearsal=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_database_maintenance"] is False
    assert "backup_bundle_stale" in gates
    assert "sqlite_backup_stale" in gates
    assert "postgres_snapshot_stale" in gates
    assert "media_archive_stale" in gates
    assert "restore_rehearsal_stale" in gates


def test_database_maintenance_validation_blocks_failed_backup_summary(tmp_path):
    backup_dir = tmp_path / "backups"
    _write_json(
        backup_dir / "database-backup-bundle-20260808T120000Z.json",
        {
            "created_at": _iso(),
            "ok": False,
            "counts": {"completed": 1, "failed": 1, "skipped": 1},
        },
    )

    report = build_database_maintenance_report(
        backup_summary_dir=backup_dir,
        sqlite_backup_dir=backup_dir,
        postgres_snapshot_dir=tmp_path / "missing-postgres",
        media_backup_dir=tmp_path / "missing-media",
        require_sqlite_backup=False,
        require_postgres_snapshot=False,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_database_maintenance"] is False
    assert "backup_bundle_failed" in gates
    assert "backup_bundle_failed_tasks" in gates


def test_database_maintenance_validation_blocks_missing_required_postgres_and_restore(tmp_path):
    backup_dir, _postgres_dir, media_dir, _restore_report = _write_complete_evidence(tmp_path)

    report = build_database_maintenance_report(
        backup_summary_dir=backup_dir,
        sqlite_backup_dir=backup_dir,
        postgres_snapshot_dir=tmp_path / "empty-postgres",
        media_backup_dir=media_dir,
        require_postgres_snapshot=True,
        require_restore_rehearsal=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_database_maintenance"] is False
    assert "postgres_snapshot_missing" in gates
    assert "restore_rehearsal_missing" in gates


def test_database_maintenance_validation_warns_on_capacity_thresholds(tmp_path):
    backup_dir, postgres_dir, media_dir, _restore_report = _write_complete_evidence(tmp_path)

    report = build_database_maintenance_report(
        backup_summary_dir=backup_dir,
        sqlite_backup_dir=backup_dir,
        postgres_snapshot_dir=postgres_dir,
        media_backup_dir=media_dir,
        warn_total_rows=40,
        warn_backup_bytes=1024,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_database_maintenance"] is True
    assert "sqlite_backup_row_capacity" in warning_gates
    assert "sqlite_backup_size_capacity" in warning_gates
    assert "postgres_snapshot_row_capacity" in warning_gates
