"""Run the safe local cloud-cutover rehearsal checks as one bundle.

This command does not connect to Postgres and does not modify the source database. It
creates the same local artifacts used by the cutover checklist so a rehearsal can be
reviewed before a disposable cloud database is involved.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.audit_runtime_sqlite_usage import audit_runtime_sqlite_usage
from scripts.load_cloud_migration import build_load_plan
from scripts.rehearse_cloud_migration import DEFAULT_DB_PATH, build_report, export_jsonl
from scripts.validate_cloud_cutover_readiness import build_cutover_readiness


def _prepare_work_dir(work_dir: Path, *, overwrite: bool) -> Path:
    work_dir = work_dir.expanduser().resolve()
    if work_dir.exists() and any(work_dir.iterdir()):
        if not overwrite:
            raise ValueError(
                f"Work directory is not empty: {work_dir}. "
                "Use --overwrite to replace local rehearsal artifacts."
            )
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(path)


def build_local_cutover_rehearsal_bundle(
    *,
    source_db: Path,
    work_dir: Path,
    repo_root: Path,
    overwrite: bool = False,
    test_evidence: dict[str, bool] | None = None,
    postgres_rehearsal_loaded: bool = False,
) -> dict[str, Any]:
    source_db = source_db.expanduser().resolve()
    if not source_db.is_file():
        raise ValueError(f"Source database not found: {source_db}")

    work_dir = _prepare_work_dir(work_dir, overwrite=overwrite)
    export_dir = work_dir / "export"
    migration_report_path = work_dir / "migration-report.json"
    load_plan_path = work_dir / "load-plan.json"
    readiness_report_path = work_dir / "cutover-readiness.json"
    sqlite_usage_path = work_dir / "runtime-sqlite-usage.json"

    migration_report = build_report(source_db)
    migration_report["exported_files"] = export_jsonl(source_db, export_dir)
    migration_report["export_manifest"] = str(export_dir / "manifest.json")
    _write_json(migration_report_path, migration_report)

    load_plan = build_load_plan(export_dir)
    _write_json(load_plan_path, load_plan)

    sqlite_usage = audit_runtime_sqlite_usage(repo_root.expanduser().resolve())
    _write_json(sqlite_usage_path, sqlite_usage)

    readiness = build_cutover_readiness(
        migration_report_path=migration_report_path,
        export_dir=export_dir,
        repo_root=repo_root.expanduser().resolve(),
        test_evidence=test_evidence or {},
        postgres_rehearsal_loaded=postgres_rehearsal_loaded,
    )
    _write_json(readiness_report_path, readiness)

    bundle = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_db": str(source_db),
        "work_dir": str(work_dir),
        "artifacts": {
            "migration_report": str(migration_report_path),
            "export_dir": str(export_dir),
            "export_manifest": str(export_dir / "manifest.json"),
            "load_plan": str(load_plan_path),
            "runtime_sqlite_usage": str(sqlite_usage_path),
            "cutover_readiness": str(readiness_report_path),
        },
        "summary": {
            "source_total_rows": migration_report["summary"]["total_rows"],
            "export_total_rows": load_plan["total_rows"],
            "manifest_valid": not load_plan["manifest_mismatches"],
            "runtime_sqlite_usage_passed": bool(sqlite_usage["passed"]),
            "ready_for_cutover": bool(readiness["ready_for_cutover"]),
            "blocker_count": len(readiness["blockers"]),
        },
        "next_required_actions": _next_required_actions(readiness),
    }
    _write_json(work_dir / "local-cutover-rehearsal-bundle.json", bundle)
    return bundle


def _next_required_actions(readiness: dict[str, Any]) -> list[str]:
    gates = {blocker["gate"] for blocker in readiness.get("blockers") or []}
    actions = []
    if "postgres_rehearsal" in gates:
        actions.append(
            "Apply the export to a disposable Postgres branch and spot-check it."
        )
    if "regression_test_evidence" in gates:
        actions.append(
            "Run backend tests, frontend lint, and frontend build, then rerun with "
            "evidence flags."
        )
    if "runtime_sqlite_usage" in gates:
        actions.append("Remove direct SQLite runtime usage from product routes/services.")
    if "jsonl_export_manifest" in gates:
        actions.append("Regenerate the export because manifest validation failed.")
    if "jsonl_export_row_count" in gates or "jsonl_export_table_counts" in gates:
        actions.append("Regenerate export from the same SQLite source used for the audit.")
    if "postgres_schema_columns" in gates:
        actions.append("Update Postgres schema or source export mapping before loading.")
    if not actions and readiness.get("ready_for_cutover") is True:
        actions.append(
            "Proceed to disposable Postgres rehearsal and rollback rehearsal sign-off."
        )
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a local cloud-cutover rehearsal bundle without connecting to "
            "Postgres."
        )
    )
    parser.add_argument(
        "--source-db",
        default=str(DEFAULT_DB_PATH),
        help="SQLite source database. Defaults to server/db/app.db.",
    )
    parser.add_argument(
        "--work-dir",
        required=True,
        help="Directory where local rehearsal artifacts will be written.",
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        help="Repository root for runtime SQLite usage audit.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--backend-tests-passed", action="store_true")
    parser.add_argument("--frontend-lint-passed", action="store_true")
    parser.add_argument("--frontend-build-passed", action="store_true")
    parser.add_argument("--postgres-rehearsal-loaded", action="store_true")
    args = parser.parse_args()

    bundle = build_local_cutover_rehearsal_bundle(
        source_db=Path(args.source_db),
        work_dir=Path(args.work_dir),
        repo_root=Path(args.repo_root),
        overwrite=args.overwrite,
        test_evidence={
            "backend_tests_passed": args.backend_tests_passed,
            "frontend_lint_passed": args.frontend_lint_passed,
            "frontend_build_passed": args.frontend_build_passed,
        },
        postgres_rehearsal_loaded=args.postgres_rehearsal_loaded,
    )
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0 if bundle["summary"]["manifest_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
