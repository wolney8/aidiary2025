"""Validate evidence required before a cloud database cutover.

The script does not connect to production. It checks local rehearsal artifacts and
explicit test-evidence flags, then emits a go/no-go JSON report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.audit_runtime_sqlite_usage import audit_runtime_sqlite_usage
from scripts.load_cloud_migration import build_load_plan


REQUIRED_TEST_FLAGS = [
    "backend_tests_passed",
    "frontend_lint_passed",
    "frontend_build_passed",
]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc


def _compare_export_table_counts(
    *,
    migration_report: dict[str, Any],
    load_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    expected_counts = {
        str(table["name"]): int(table.get("row_count") or 0)
        for table in migration_report.get("tables") or []
        if table.get("exists") is True and table.get("name")
    }
    if not expected_counts:
        return []

    exported_counts = {
        str(table["table"]): int(table.get("row_count") or 0)
        for table in load_plan.get("tables") or []
        if table.get("exists") is True and table.get("table")
    }
    mismatches = []
    for table_name, expected_count in sorted(expected_counts.items()):
        exported_count = exported_counts.get(table_name)
        if exported_count != expected_count:
            mismatches.append(
                {
                    "table": table_name,
                    "report_rows": expected_count,
                    "export_rows": exported_count,
                }
            )
    return mismatches


def build_cutover_readiness(
    *,
    migration_report_path: Path,
    export_dir: Path | None = None,
    repo_root: Path | None = None,
    test_evidence: dict[str, bool] | None = None,
    postgres_rehearsal_loaded: bool = False,
) -> dict[str, Any]:
    migration_report = _load_json(migration_report_path)
    summary = migration_report.get("summary") or {}
    media_checks = migration_report.get("media_reference_checks") or {}
    blockers = []

    missing_tables = summary.get("tables_missing") or []
    if missing_tables:
        blockers.append(
            {
                "gate": "sqlite_source_tables",
                "message": "Expected source tables are missing.",
                "details": missing_tables,
            }
        )

    orphan_issues = summary.get("orphan_issues") or []
    if orphan_issues:
        blockers.append(
            {
                "gate": "sqlite_foreign_key_integrity",
                "message": "Source data has orphaned child rows.",
                "details": orphan_issues,
            }
        )

    media_failures = {
        key: value
        for key, value in media_checks.items()
        if isinstance(value, int) and value > 0
    }
    if media_failures:
        blockers.append(
            {
                "gate": "media_reference_integrity",
                "message": "Media references need repair before cloud migration.",
                "details": media_failures,
            }
        )

    load_plan = None
    if export_dir is not None:
        load_plan = build_load_plan(export_dir)
        if load_plan["missing_files"]:
            blockers.append(
                {
                    "gate": "jsonl_export_completeness",
                    "message": "Expected JSONL export files are missing.",
                    "details": load_plan["missing_files"],
                }
            )
        if int(load_plan["total_rows"]) != int(summary.get("total_rows") or 0):
            blockers.append(
                {
                    "gate": "jsonl_export_row_count",
                    "message": "Export row count does not match the migration report.",
                    "details": {
                        "report_rows": int(summary.get("total_rows") or 0),
                        "export_rows": int(load_plan["total_rows"]),
                    },
                }
            )
        table_count_mismatches = _compare_export_table_counts(
            migration_report=migration_report,
            load_plan=load_plan,
        )
        if table_count_mismatches:
            blockers.append(
                {
                    "gate": "jsonl_export_table_counts",
                    "message": "Exported table row counts do not match the migration report.",
                    "details": table_count_mismatches,
                }
            )
        if load_plan["schema_column_mismatches"]:
            blockers.append(
                {
                    "gate": "postgres_schema_columns",
                    "message": "Export contains columns missing from the Postgres schema.",
                    "details": load_plan["schema_column_mismatches"],
                }
            )

    sqlite_usage_audit = None
    if repo_root is not None:
        sqlite_usage_audit = audit_runtime_sqlite_usage(repo_root)
        if not sqlite_usage_audit["passed"]:
            blockers.append(
                {
                    "gate": "runtime_sqlite_usage",
                    "message": "Product runtime code still contains direct SQLite connection usage.",
                    "details": sqlite_usage_audit["violations"],
                }
            )

    evidence = test_evidence or {}
    missing_evidence = [
        flag for flag in REQUIRED_TEST_FLAGS if evidence.get(flag) is not True
    ]
    if missing_evidence:
        blockers.append(
            {
                "gate": "regression_test_evidence",
                "message": "Required validation commands have not been marked passed.",
                "details": missing_evidence,
            }
        )

    if not postgres_rehearsal_loaded:
        blockers.append(
            {
                "gate": "postgres_rehearsal",
                "message": "A disposable Postgres rehearsal load has not been marked complete.",
                "details": "Run load_cloud_migration.py --apply against a rehearsal branch.",
            }
        )

    return {
        "ready_for_cutover": not blockers,
        "blockers": blockers,
        "source_summary": {
            "tables_present": summary.get("tables_present"),
            "total_rows": summary.get("total_rows"),
        },
        "load_plan_summary": (
            {
                "total_rows": load_plan["total_rows"],
                "missing_files": load_plan["missing_files"],
            }
            if load_plan
            else None
        ),
        "runtime_sqlite_usage": sqlite_usage_audit,
        "test_evidence": {flag: bool(evidence.get(flag)) for flag in REQUIRED_TEST_FLAGS},
        "postgres_rehearsal_loaded": postgres_rehearsal_loaded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate cloud database cutover readiness evidence."
    )
    parser.add_argument(
        "--migration-report",
        required=True,
        help="JSON report produced by rehearse_cloud_migration.py.",
    )
    parser.add_argument(
        "--export-dir",
        help="Optional JSONL export directory to compare against the migration report.",
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        help="Repository root to scan for direct SQLite runtime usage.",
    )
    parser.add_argument("--backend-tests-passed", action="store_true")
    parser.add_argument("--frontend-lint-passed", action="store_true")
    parser.add_argument("--frontend-build-passed", action="store_true")
    parser.add_argument(
        "--postgres-rehearsal-loaded",
        action="store_true",
        help="Set only after a disposable Postgres load and spot-check succeeded.",
    )
    args = parser.parse_args()

    readiness = build_cutover_readiness(
        migration_report_path=Path(args.migration_report).expanduser().resolve(),
        export_dir=(
            Path(args.export_dir).expanduser().resolve()
            if args.export_dir
            else None
        ),
        repo_root=Path(args.repo_root).expanduser().resolve(),
        test_evidence={
            "backend_tests_passed": args.backend_tests_passed,
            "frontend_lint_passed": args.frontend_lint_passed,
            "frontend_build_passed": args.frontend_build_passed,
        },
        postgres_rehearsal_loaded=args.postgres_rehearsal_loaded,
    )
    print(json.dumps(readiness, ensure_ascii=False, indent=2))
    return 0 if readiness["ready_for_cutover"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
