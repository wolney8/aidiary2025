"""Create a structured cutover rehearsal sign-off report.

This intentionally sits after the evidence packet. The packet proves technical
artifacts exist; this report proves the rehearsal had assigned owners, timing
markers, rollback evidence, and an explicit go/no-go decision.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_ROLES = (
    "cutover_lead",
    "backend_operator",
    "frontend_operator",
    "rollback_owner",
    "recorder",
)

REQUIRED_TIMINGS = (
    "freeze_started_at",
    "migration_started_at",
    "config_switched_at",
    "decision_due_at",
)


def _resolve_existing_file(path_value: str) -> str:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Required file not found: {path}")
    return str(path)


def _load_json(path_value: str) -> dict[str, Any]:
    path = Path(_resolve_existing_file(path_value))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc


def _normalise_value(value: str | None) -> str:
    return (value or "").strip()


def build_cutover_rehearsal_signoff(
    *,
    evidence_packet: str,
    role_assignments: dict[str, str],
    timing_markers: dict[str, str],
    decision: str,
    notes: str = "",
) -> dict[str, Any]:
    packet_data = _load_json(evidence_packet)
    normalised_roles = {
        role: _normalise_value(role_assignments.get(role))
        for role in REQUIRED_ROLES
    }
    normalised_timings = {
        timing: _normalise_value(timing_markers.get(timing))
        for timing in REQUIRED_TIMINGS
    }
    normalised_decision = _normalise_value(decision).lower()

    blockers: list[str] = []
    missing_roles = [role for role, owner in normalised_roles.items() if not owner]
    missing_timings = [
        timing for timing, marker in normalised_timings.items() if not marker
    ]
    if missing_roles:
        blockers.append("role_assignments")
    if missing_timings:
        blockers.append("timing_markers")
    if packet_data.get("packet_complete") is not True:
        blockers.append("evidence_packet_complete")
    if normalised_decision not in {"go", "no-go"}:
        blockers.append("go_no_go_decision")
    elif normalised_decision != "go":
        blockers.append("decision_not_go")
    rollback_summary = packet_data.get("rollback_summary") or {}
    if rollback_summary.get("rollback_rehearsal_passed") is not True:
        blockers.append("rollback_rehearsal_passed")

    return {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "artifacts": {
            "evidence_packet": _resolve_existing_file(evidence_packet),
        },
        "postgres_target": packet_data.get("postgres_target"),
        "role_assignments": normalised_roles,
        "timing_markers": normalised_timings,
        "decision": normalised_decision,
        "notes": notes.strip(),
        "evidence_summary": {
            "packet_complete": bool(packet_data.get("packet_complete")),
            "blockers": packet_data.get("blockers") or [],
            "rollback_summary": rollback_summary,
        },
        "missing_roles": missing_roles,
        "missing_timings": missing_timings,
        "rehearsal_signed_off": not blockers,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a JSON sign-off report for cloud cutover rehearsal."
    )
    parser.add_argument("--evidence-packet", required=True)
    parser.add_argument("--cutover-lead", required=True)
    parser.add_argument("--backend-operator", required=True)
    parser.add_argument("--frontend-operator", required=True)
    parser.add_argument("--rollback-owner", required=True)
    parser.add_argument("--recorder", required=True)
    parser.add_argument("--freeze-started-at", required=True)
    parser.add_argument("--migration-started-at", required=True)
    parser.add_argument("--config-switched-at", required=True)
    parser.add_argument("--decision-due-at", required=True)
    parser.add_argument("--decision", choices=("go", "no-go"), required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    report = build_cutover_rehearsal_signoff(
        evidence_packet=args.evidence_packet,
        role_assignments={
            "cutover_lead": args.cutover_lead,
            "backend_operator": args.backend_operator,
            "frontend_operator": args.frontend_operator,
            "rollback_owner": args.rollback_owner,
            "recorder": args.recorder,
        },
        timing_markers={
            "freeze_started_at": args.freeze_started_at,
            "migration_started_at": args.migration_started_at,
            "config_switched_at": args.config_switched_at,
            "decision_due_at": args.decision_due_at,
        },
        decision=args.decision,
        notes=args.notes,
    )
    output_path = Path(args.output_json).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["rehearsal_signed_off"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
