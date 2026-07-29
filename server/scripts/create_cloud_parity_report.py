"""Create an operator-facing cloud parity go/no-go report.

This report sits after the migration rehearsal and before cutover. It does not perform
the checks itself; it records the evidence flags and the readiness artifact that were
produced by the rehearsal, regression, and manual smoke steps.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUTOMATED_EVIDENCE_FLAGS = [
    "backend_tests_passed",
    "frontend_lint_passed",
    "frontend_build_passed",
    "frontend_smoke_passed",
    "frontend_a11y_passed",
]

MANUAL_EVIDENCE_FLAGS = [
    "manual_rehearsal_smoke_passed",
]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc


def build_cloud_parity_report(
    *,
    readiness_report_path: Path,
    postgres_target: str = "",
    evidence: dict[str, bool] | None = None,
) -> dict[str, Any]:
    readiness = _load_json(readiness_report_path)
    evidence = evidence or {}
    normalized_evidence = {
        flag: bool(evidence.get(flag))
        for flag in [*AUTOMATED_EVIDENCE_FLAGS, *MANUAL_EVIDENCE_FLAGS]
    }

    blockers: list[dict[str, Any]] = []
    if readiness.get("ready_for_cutover") is not True:
        blockers.append(
            {
                "gate": "readiness_report",
                "message": "Cloud cutover readiness report is not green.",
                "details": readiness.get("blockers") or [],
            }
        )

    missing_automated = [
        flag for flag in AUTOMATED_EVIDENCE_FLAGS if normalized_evidence[flag] is not True
    ]
    if missing_automated:
        blockers.append(
            {
                "gate": "automated_regression_evidence",
                "message": "Required automated parity checks are not marked passed.",
                "details": missing_automated,
            }
        )

    missing_manual = [
        flag for flag in MANUAL_EVIDENCE_FLAGS if normalized_evidence[flag] is not True
    ]
    if missing_manual:
        blockers.append(
            {
                "gate": "manual_rehearsal_smoke",
                "message": "Manual app smoke against the rehearsal database is not marked passed.",
                "details": missing_manual,
            }
        )

    source_summary = readiness.get("source_summary") or {}
    load_plan_summary = readiness.get("load_plan_summary") or {}
    return {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "postgres_target": postgres_target,
        "readiness_report": str(readiness_report_path.expanduser().resolve()),
        "source_summary": source_summary,
        "load_plan_summary": load_plan_summary,
        "runtime_sqlite_usage_passed": bool(
            (readiness.get("runtime_sqlite_usage") or {}).get("passed")
        ),
        "evidence": normalized_evidence,
        "parity_ready": not blockers,
        "blockers": blockers,
        "next_required_actions": _next_required_actions(blockers),
    }


def _next_required_actions(blockers: list[dict[str, Any]]) -> list[str]:
    gates = {blocker["gate"] for blocker in blockers}
    actions = []
    if "readiness_report" in gates:
        actions.append("Regenerate the migration/readiness bundle until it is green.")
    if "automated_regression_evidence" in gates:
        actions.append(
            "Run backend tests, frontend lint/build, smoke, and WCAG checks, then rerun this report with evidence flags."
        )
    if "manual_rehearsal_smoke" in gates:
        actions.append(
            "Run the manual parity smoke against the Postgres-backed rehearsal app and rerun with --manual-rehearsal-smoke-passed."
        )
    if not actions:
        actions.append("Proceed to cutover runbook and rollback rehearsal sign-off.")
    return actions


def render_markdown_report(report: dict[str, Any]) -> str:
    status = "READY" if report["parity_ready"] else "NOT READY"
    source_rows = (report.get("source_summary") or {}).get("total_rows")
    load_rows = (report.get("load_plan_summary") or {}).get("total_rows")
    lines = [
        "# Cloud Parity Report",
        "",
        f"Created: {report['created_at']}",
        f"Status: {status}",
        f"Postgres target: {report.get('postgres_target') or 'not recorded'}",
        "",
        "## Migration Parity",
        "",
        f"- SQLite source rows: {source_rows}",
        f"- Postgres export/load-plan rows: {load_rows}",
        f"- Runtime SQLite usage audit passed: {'yes' if report['runtime_sqlite_usage_passed'] else 'no'}",
        "",
        "## Evidence",
        "",
    ]
    for flag, passed in report["evidence"].items():
        lines.append(f"- {flag}: {'passed' if passed else 'missing'}")
    lines.append("")

    if report["blockers"]:
        lines.extend(["## Blockers", ""])
        for blocker in report["blockers"]:
            lines.append(f"- {blocker['gate']}: {blocker['message']}")
        lines.append("")

    lines.extend(["## Next Required Actions", ""])
    for action in report["next_required_actions"]:
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a cloud parity report from readiness and test evidence."
    )
    parser.add_argument("--readiness-report", required=True)
    parser.add_argument("--postgres-target", default="")
    parser.add_argument("--backend-tests-passed", action="store_true")
    parser.add_argument("--frontend-lint-passed", action="store_true")
    parser.add_argument("--frontend-build-passed", action="store_true")
    parser.add_argument("--frontend-smoke-passed", action="store_true")
    parser.add_argument("--frontend-a11y-passed", action="store_true")
    parser.add_argument("--manual-rehearsal-smoke-passed", action="store_true")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    args = parser.parse_args()

    report = build_cloud_parity_report(
        readiness_report_path=Path(args.readiness_report).expanduser().resolve(),
        postgres_target=args.postgres_target,
        evidence={
            "backend_tests_passed": args.backend_tests_passed,
            "frontend_lint_passed": args.frontend_lint_passed,
            "frontend_build_passed": args.frontend_build_passed,
            "frontend_smoke_passed": args.frontend_smoke_passed,
            "frontend_a11y_passed": args.frontend_a11y_passed,
            "manual_rehearsal_smoke_passed": args.manual_rehearsal_smoke_passed,
        },
    )

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        output_json = Path(args.output_json).expanduser().resolve()
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(output + "\n", encoding="utf-8")
    if args.output_md:
        output_md = Path(args.output_md).expanduser().resolve()
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown_report(report), encoding="utf-8")
    if not args.output_json:
        print(output)
    return 0 if report["parity_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
