import json

import pytest

from scripts.create_cutover_evidence_packet import build_evidence_packet


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_cutover_artifacts(tmp_path, *, ready=True, baseline_errors=0):
    sqlite_backup = tmp_path / "aidiary.sqlite.bak"
    sqlite_backup.write_text("backup", encoding="utf-8")
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    migration_report = tmp_path / "migration-report.json"
    readiness_report = tmp_path / "readiness-report.json"
    baseline_report = tmp_path / "post-cutover-baseline.json"
    _write_json(
        migration_report,
        {"summary": {"tables_present": 18, "total_rows": 42}},
    )
    _write_json(
        readiness_report,
        {
            "ready_for_cutover": ready,
            "blockers": [] if ready else [{"gate": "postgres_rehearsal"}],
        },
    )
    _write_json(
        baseline_report,
        {"summary": {"error_count": baseline_errors, "p95_latency_ms": 120}},
    )
    return sqlite_backup, export_dir, migration_report, readiness_report, baseline_report


def test_cutover_evidence_packet_is_complete_with_required_artifacts(tmp_path):
    sqlite_backup, export_dir, migration_report, readiness_report, baseline_report = (
        _write_cutover_artifacts(tmp_path)
    )

    packet = build_evidence_packet(
        sqlite_backup=str(sqlite_backup),
        export_dir=str(export_dir),
        migration_report=str(migration_report),
        readiness_report=str(readiness_report),
        post_cutover_baseline=str(baseline_report),
        postgres_target="neon/rehearsal-branch",
        backend_tests_passed=True,
        frontend_lint_passed=True,
        frontend_build_passed=True,
        manual_smoke_passed=True,
        rollback_rehearsed=True,
    )

    assert packet["packet_complete"] is True
    assert packet["blockers"] == []
    assert packet["postgres_target"] == "neon/rehearsal-branch"
    assert packet["migration_summary"]["total_rows"] == 42
    assert packet["baseline_summary"]["error_count"] == 0


def test_cutover_evidence_packet_reports_missing_evidence_flags(tmp_path):
    sqlite_backup, export_dir, migration_report, readiness_report, baseline_report = (
        _write_cutover_artifacts(tmp_path, ready=False, baseline_errors=1)
    )

    packet = build_evidence_packet(
        sqlite_backup=str(sqlite_backup),
        export_dir=str(export_dir),
        migration_report=str(migration_report),
        readiness_report=str(readiness_report),
        post_cutover_baseline=str(baseline_report),
        backend_tests_passed=True,
    )

    assert packet["packet_complete"] is False
    assert "frontend_lint_passed" in packet["blockers"]
    assert "frontend_build_passed" in packet["blockers"]
    assert "manual_smoke_passed" in packet["blockers"]
    assert "rollback_rehearsed" in packet["blockers"]
    assert "readiness_report_ready_for_cutover" in packet["blockers"]
    assert "post_cutover_baseline_errors" in packet["blockers"]


def test_cutover_evidence_packet_requires_existing_artifacts(tmp_path):
    sqlite_backup, export_dir, migration_report, readiness_report, _baseline_report = (
        _write_cutover_artifacts(tmp_path)
    )
    sqlite_backup.unlink()

    with pytest.raises(ValueError, match="Required file not found"):
        build_evidence_packet(
            sqlite_backup=str(sqlite_backup),
            export_dir=str(export_dir),
            migration_report=str(migration_report),
            readiness_report=str(readiness_report),
        )
