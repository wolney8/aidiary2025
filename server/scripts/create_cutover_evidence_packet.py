"""Create a cutover evidence packet from migration and verification artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _resolve_existing_path(path_value: str, *, must_be_dir: bool = False) -> str:
    path = Path(path_value).expanduser().resolve()
    if must_be_dir:
        if not path.is_dir():
            raise ValueError(f"Required directory not found: {path}")
    elif not path.is_file():
        raise ValueError(f"Required file not found: {path}")
    return str(path)


def _load_json(path_value: str) -> dict[str, Any]:
    path = Path(_resolve_existing_path(path_value))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc


def build_evidence_packet(
    *,
    sqlite_backup: str,
    export_dir: str,
    migration_report: str,
    readiness_report: str,
    post_cutover_baseline: str | None = None,
    postgres_target: str = "",
    backend_tests_passed: bool = False,
    frontend_lint_passed: bool = False,
    frontend_build_passed: bool = False,
    manual_smoke_passed: bool = False,
    rollback_rehearsed: bool = False,
) -> dict[str, Any]:
    migration_data = _load_json(migration_report)
    readiness_data = _load_json(readiness_report)
    baseline_data = _load_json(post_cutover_baseline) if post_cutover_baseline else None

    evidence = {
        "backend_tests_passed": backend_tests_passed,
        "frontend_lint_passed": frontend_lint_passed,
        "frontend_build_passed": frontend_build_passed,
        "manual_smoke_passed": manual_smoke_passed,
        "rollback_rehearsed": rollback_rehearsed,
    }
    blockers = [
        key for key, passed in evidence.items() if passed is not True
    ]
    if readiness_data.get("ready_for_cutover") is not True:
        blockers.append("readiness_report_ready_for_cutover")
    if baseline_data and int((baseline_data.get("summary") or {}).get("error_count") or 0) > 0:
        blockers.append("post_cutover_baseline_errors")

    return {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "postgres_target": postgres_target,
        "artifacts": {
            "sqlite_backup": _resolve_existing_path(sqlite_backup),
            "export_dir": _resolve_existing_path(export_dir, must_be_dir=True),
            "migration_report": _resolve_existing_path(migration_report),
            "readiness_report": _resolve_existing_path(readiness_report),
            "post_cutover_baseline": (
                _resolve_existing_path(post_cutover_baseline)
                if post_cutover_baseline
                else None
            ),
        },
        "migration_summary": migration_data.get("summary"),
        "readiness_summary": {
            "ready_for_cutover": bool(readiness_data.get("ready_for_cutover")),
            "blockers": readiness_data.get("blockers") or [],
        },
        "baseline_summary": (
            baseline_data.get("summary") if baseline_data else None
        ),
        "evidence": evidence,
        "packet_complete": not blockers,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a JSON evidence packet for cloud cutover sign-off."
    )
    parser.add_argument("--sqlite-backup", required=True)
    parser.add_argument("--export-dir", required=True)
    parser.add_argument("--migration-report", required=True)
    parser.add_argument("--readiness-report", required=True)
    parser.add_argument("--post-cutover-baseline")
    parser.add_argument("--postgres-target", default="")
    parser.add_argument("--backend-tests-passed", action="store_true")
    parser.add_argument("--frontend-lint-passed", action="store_true")
    parser.add_argument("--frontend-build-passed", action="store_true")
    parser.add_argument("--manual-smoke-passed", action="store_true")
    parser.add_argument("--rollback-rehearsed", action="store_true")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    packet = build_evidence_packet(
        sqlite_backup=args.sqlite_backup,
        export_dir=args.export_dir,
        migration_report=args.migration_report,
        readiness_report=args.readiness_report,
        post_cutover_baseline=args.post_cutover_baseline,
        postgres_target=args.postgres_target,
        backend_tests_passed=args.backend_tests_passed,
        frontend_lint_passed=args.frontend_lint_passed,
        frontend_build_passed=args.frontend_build_passed,
        manual_smoke_passed=args.manual_smoke_passed,
        rollback_rehearsed=args.rollback_rehearsed,
    )
    output_path = Path(args.output_json).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    return 0 if packet["packet_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
