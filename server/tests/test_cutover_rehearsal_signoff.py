import json

import pytest

from scripts.create_cutover_rehearsal_signoff import build_cutover_rehearsal_signoff


def _write_packet(path, *, complete=True, rollback_passed=True):
    path.write_text(
        json.dumps(
            {
                "packet_complete": complete,
                "postgres_target": "neon/rehearsal-branch",
                "blockers": [] if complete else ["manual_smoke_passed"],
                "rollback_summary": {
                    "rollback_rehearsal_passed": rollback_passed,
                    "scenario": "failed app smoke after config switch",
                    "blockers": [] if rollback_passed else ["entries_smoke_passed"],
                },
            }
        ),
        encoding="utf-8",
    )


def _roles():
    return {
        "cutover_lead": "Will",
        "backend_operator": "Will",
        "frontend_operator": "Will",
        "rollback_owner": "Will",
        "recorder": "Will",
    }


def _timings():
    return {
        "freeze_started_at": "2026-07-27T10:00:00Z",
        "migration_started_at": "2026-07-27T10:05:00Z",
        "config_switched_at": "2026-07-27T10:20:00Z",
        "decision_due_at": "2026-07-27T10:35:00Z",
    }


def test_cutover_rehearsal_signoff_passes_with_roles_timing_and_go_decision(tmp_path):
    packet = tmp_path / "evidence-packet.json"
    _write_packet(packet)

    report = build_cutover_rehearsal_signoff(
        evidence_packet=str(packet),
        role_assignments=_roles(),
        timing_markers=_timings(),
        decision="go",
        notes="Disposable branch rehearsal completed.",
    )

    assert report["rehearsal_signed_off"] is True
    assert report["blockers"] == []
    assert report["postgres_target"] == "neon/rehearsal-branch"
    assert report["role_assignments"]["rollback_owner"] == "Will"
    assert report["timing_markers"]["decision_due_at"] == "2026-07-27T10:35:00Z"


def test_cutover_rehearsal_signoff_blocks_missing_operational_evidence(tmp_path):
    packet = tmp_path / "evidence-packet.json"
    _write_packet(packet)
    roles = _roles()
    roles["rollback_owner"] = " "
    timings = _timings()
    timings["config_switched_at"] = ""

    report = build_cutover_rehearsal_signoff(
        evidence_packet=str(packet),
        role_assignments=roles,
        timing_markers=timings,
        decision="go",
    )

    assert report["rehearsal_signed_off"] is False
    assert "role_assignments" in report["blockers"]
    assert "timing_markers" in report["blockers"]
    assert report["missing_roles"] == ["rollback_owner"]
    assert report["missing_timings"] == ["config_switched_at"]


def test_cutover_rehearsal_signoff_blocks_incomplete_packet_and_failed_rollback(tmp_path):
    packet = tmp_path / "evidence-packet.json"
    _write_packet(packet, complete=False, rollback_passed=False)

    report = build_cutover_rehearsal_signoff(
        evidence_packet=str(packet),
        role_assignments=_roles(),
        timing_markers=_timings(),
        decision="go",
    )

    assert report["rehearsal_signed_off"] is False
    assert "evidence_packet_complete" in report["blockers"]
    assert "rollback_rehearsal_passed" in report["blockers"]
    assert report["evidence_summary"]["blockers"] == ["manual_smoke_passed"]


def test_cutover_rehearsal_signoff_blocks_no_go_decision(tmp_path):
    packet = tmp_path / "evidence-packet.json"
    _write_packet(packet)

    report = build_cutover_rehearsal_signoff(
        evidence_packet=str(packet),
        role_assignments=_roles(),
        timing_markers=_timings(),
        decision="no-go",
    )

    assert report["rehearsal_signed_off"] is False
    assert "decision_not_go" in report["blockers"]


def test_cutover_rehearsal_signoff_requires_existing_packet(tmp_path):
    with pytest.raises(ValueError, match="Required file not found"):
        build_cutover_rehearsal_signoff(
            evidence_packet=str(tmp_path / "missing.json"),
            role_assignments=_roles(),
            timing_markers=_timings(),
            decision="go",
        )
