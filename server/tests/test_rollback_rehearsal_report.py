import json

import pytest

from scripts.create_rollback_rehearsal_report import build_rollback_rehearsal_report


def _write_baseline(path, *, error_count=0):
    path.write_text(
        json.dumps({"summary": {"error_count": error_count, "p95_latency_ms": 140}}),
        encoding="utf-8",
    )


def test_rollback_rehearsal_report_passes_with_required_evidence(tmp_path):
    sqlite_backup = tmp_path / "sqlite-backup.db"
    rollback_baseline = tmp_path / "rollback-baseline.json"
    sqlite_backup.write_text("backup", encoding="utf-8")
    _write_baseline(rollback_baseline)

    report = build_rollback_rehearsal_report(
        scenario="failed app smoke after config switch",
        sqlite_backup=str(sqlite_backup),
        rollback_baseline=str(rollback_baseline),
        postgres_target="neon/rehearsal-branch",
        failure_summary="Backend was pointed back to SQLite after a failed smoke.",
        config_restored=True,
        health_passed=True,
        auth_smoke_passed=True,
        entries_smoke_passed=True,
        export_smoke_passed=True,
        media_smoke_passed=True,
    )

    assert report["rollback_rehearsal_passed"] is True
    assert report["blockers"] == []
    assert report["postgres_target"] == "neon/rehearsal-branch"
    assert report["baseline_summary"]["error_count"] == 0


def test_rollback_rehearsal_report_blocks_missing_smoke_flags_and_baseline_errors(tmp_path):
    sqlite_backup = tmp_path / "sqlite-backup.db"
    rollback_baseline = tmp_path / "rollback-baseline.json"
    sqlite_backup.write_text("backup", encoding="utf-8")
    _write_baseline(rollback_baseline, error_count=1)

    report = build_rollback_rehearsal_report(
        scenario="failed readiness validation",
        sqlite_backup=str(sqlite_backup),
        rollback_baseline=str(rollback_baseline),
        config_restored=True,
        health_passed=True,
    )

    assert report["rollback_rehearsal_passed"] is False
    assert "auth_smoke_passed" in report["blockers"]
    assert "entries_smoke_passed" in report["blockers"]
    assert "export_smoke_passed" in report["blockers"]
    assert "media_smoke_passed" in report["blockers"]
    assert "rollback_baseline_errors" in report["blockers"]


def test_rollback_rehearsal_report_requires_existing_artifacts(tmp_path):
    rollback_baseline = tmp_path / "rollback-baseline.json"
    _write_baseline(rollback_baseline)

    with pytest.raises(ValueError, match="Required file not found"):
        build_rollback_rehearsal_report(
            scenario="missing backup",
            sqlite_backup=str(tmp_path / "missing.db"),
            rollback_baseline=str(rollback_baseline),
        )
