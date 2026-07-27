"""Create a structured rollback rehearsal report for cloud cutover evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROLLBACK_SMOKE_FLAGS = [
    "config_restored",
    "health_passed",
    "auth_smoke_passed",
    "entries_smoke_passed",
    "export_smoke_passed",
    "media_smoke_passed",
]


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


def build_rollback_rehearsal_report(
    *,
    scenario: str,
    sqlite_backup: str,
    rollback_baseline: str,
    postgres_target: str = "",
    failure_summary: str = "",
    config_restored: bool = False,
    health_passed: bool = False,
    auth_smoke_passed: bool = False,
    entries_smoke_passed: bool = False,
    export_smoke_passed: bool = False,
    media_smoke_passed: bool = False,
) -> dict[str, Any]:
    baseline_data = _load_json(rollback_baseline)
    smoke_evidence = {
        "config_restored": config_restored,
        "health_passed": health_passed,
        "auth_smoke_passed": auth_smoke_passed,
        "entries_smoke_passed": entries_smoke_passed,
        "export_smoke_passed": export_smoke_passed,
        "media_smoke_passed": media_smoke_passed,
    }
    blockers = [key for key, passed in smoke_evidence.items() if passed is not True]
    baseline_summary = baseline_data.get("summary") or {}
    if int(baseline_summary.get("error_count") or 0) > 0:
        blockers.append("rollback_baseline_errors")

    return {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scenario": scenario,
        "postgres_target": postgres_target,
        "failure_summary": failure_summary,
        "artifacts": {
            "sqlite_backup": _resolve_existing_file(sqlite_backup),
            "rollback_baseline": _resolve_existing_file(rollback_baseline),
        },
        "baseline_summary": baseline_summary,
        "smoke_evidence": smoke_evidence,
        "rollback_rehearsal_passed": not blockers,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a JSON rollback rehearsal report for cloud cutover sign-off."
    )
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--sqlite-backup", required=True)
    parser.add_argument("--rollback-baseline", required=True)
    parser.add_argument("--postgres-target", default="")
    parser.add_argument("--failure-summary", default="")
    parser.add_argument("--config-restored", action="store_true")
    parser.add_argument("--health-passed", action="store_true")
    parser.add_argument("--auth-smoke-passed", action="store_true")
    parser.add_argument("--entries-smoke-passed", action="store_true")
    parser.add_argument("--export-smoke-passed", action="store_true")
    parser.add_argument("--media-smoke-passed", action="store_true")
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    report = build_rollback_rehearsal_report(
        scenario=args.scenario,
        sqlite_backup=args.sqlite_backup,
        rollback_baseline=args.rollback_baseline,
        postgres_target=args.postgres_target,
        failure_summary=args.failure_summary,
        config_restored=args.config_restored,
        health_passed=args.health_passed,
        auth_smoke_passed=args.auth_smoke_passed,
        entries_smoke_passed=args.entries_smoke_passed,
        export_smoke_passed=args.export_smoke_passed,
        media_smoke_passed=args.media_smoke_passed,
    )
    output_path = Path(args.output_json).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["rollback_rehearsal_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
