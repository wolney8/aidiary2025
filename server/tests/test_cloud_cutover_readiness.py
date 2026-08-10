import hashlib
import json

from scripts.validate_cloud_cutover_readiness import build_cutover_readiness
from scripts.rehearse_cloud_migration import TABLE_ORDER


def _write_report(path, *, total_rows=2, blockers=False):
    table_counts = {
        "users": 1,
        "configurations": 0,
        "dailydiary_entries": max(total_rows - 1, 0),
    }
    report = {
        "tables": [
            {
                "name": table_name,
                "exists": True,
                "row_count": table_counts.get(table_name, 0),
            }
            for table_name in TABLE_ORDER
        ],
        "summary": {
            "tables_present": 2,
            "tables_missing": ["dreamdiary_entries"] if blockers else [],
            "total_rows": total_rows,
            "orphan_issues": [
                {
                    "child_table": "dailydiary_entries",
                    "child_column": "user_id",
                    "parent_table": "users",
                    "parent_column": "id",
                    "orphan_count": 1,
                }
            ]
            if blockers
            else [],
        },
        "media_reference_checks": {
            "entry_assets_missing_storage_key": 1 if blockers else 0,
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def _write_export(export_dir):
    export_dir.mkdir()
    (export_dir / "users.jsonl").write_text('{"id": 1}\n', encoding="utf-8")
    (export_dir / "auth_identities.jsonl").write_text("", encoding="utf-8")
    (export_dir / "account_security_tokens.jsonl").write_text("", encoding="utf-8")
    (export_dir / "billing_customers.jsonl").write_text("", encoding="utf-8")
    (export_dir / "subscriptions.jsonl").write_text("", encoding="utf-8")
    (export_dir / "entitlements.jsonl").write_text("", encoding="utf-8")
    (export_dir / "billing_events.jsonl").write_text("", encoding="utf-8")
    (export_dir / "usage_events.jsonl").write_text("", encoding="utf-8")
    (export_dir / "configurations.jsonl").write_text("", encoding="utf-8")
    (export_dir / "dailydiary_entries.jsonl").write_text('{"id": 10}\n', encoding="utf-8")
    for table_name in [
        "dreamdiary_entries",
        "entry_ai_metadata",
        "import_history",
        "export_history",
        "entry_assets",
        "import_sessions",
        "import_jobs",
        "important_days",
        "public_holiday_cache",
        "entry_resurfacing_preferences",
        "reflection_summaries",
        "chat_messages",
        "chat_observability_events",
        "security_audit_events",
        "cbt_worksheets",
        "cbt_thought_record_data",
        "admin_announcements",
        "admin_announcement_targets",
        "admin_announcement_user_state",
    ]:
        (export_dir / f"{table_name}.jsonl").write_text("", encoding="utf-8")
    _write_manifest(export_dir)


def _write_manifest(export_dir):
    tables = []
    for table_name in TABLE_ORDER:
        path = export_dir / f"{table_name}.jsonl"
        if not path.exists():
            continue
        tables.append(
            {
                "table": table_name,
                "file": path.name,
                "row_count": sum(
                    1
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line
                ),
                "byte_size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    (export_dir / "manifest.json").write_text(
        json.dumps(
            {
                "created_at": "2026-07-27T10:00:00Z",
                "source_db": "/tmp/source.db",
                "tables": tables,
                "total_rows": sum(table["row_count"] for table in tables),
            }
        ),
        encoding="utf-8",
    )


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_clean_runtime_tree(path):
    route_dir = path / "server" / "routes"
    service_dir = path / "server" / "services"
    route_dir.mkdir(parents=True)
    service_dir.mkdir(parents=True)
    (route_dir / "entries.py").write_text(
        "from services.database_adapter import DatabaseAdapter\n",
        encoding="utf-8",
    )
    (service_dir / "database.py").write_text(
        "def connect_sqlite():\n"
        "    pass\n",
        encoding="utf-8",
    )


def test_cutover_readiness_blocks_without_required_evidence(tmp_path):
    report_path = tmp_path / "report.json"
    export_dir = tmp_path / "export"
    _write_report(report_path, blockers=True)
    _write_export(export_dir)

    readiness = build_cutover_readiness(
        migration_report_path=report_path,
        export_dir=export_dir,
        test_evidence={"backend_tests_passed": True},
        postgres_rehearsal_loaded=False,
    )

    assert readiness["ready_for_cutover"] is False
    gates = {blocker["gate"] for blocker in readiness["blockers"]}
    assert "sqlite_source_tables" in gates
    assert "sqlite_foreign_key_integrity" in gates
    assert "media_reference_integrity" in gates
    assert "regression_test_evidence" in gates
    assert "postgres_rehearsal" in gates


def test_cutover_readiness_passes_with_clean_evidence(tmp_path):
    report_path = tmp_path / "report.json"
    export_dir = tmp_path / "export"
    _write_report(report_path)
    _write_export(export_dir)
    _write_clean_runtime_tree(tmp_path)

    readiness = build_cutover_readiness(
        migration_report_path=report_path,
        export_dir=export_dir,
        repo_root=tmp_path,
        test_evidence={
            "backend_tests_passed": True,
            "frontend_lint_passed": True,
            "frontend_build_passed": True,
        },
        postgres_rehearsal_loaded=True,
    )

    assert readiness["ready_for_cutover"] is True
    assert readiness["blockers"] == []
    assert readiness["load_plan_summary"] == {
        "total_rows": 2,
        "missing_files": [],
        "manifest": {"present": True, "total_rows": 2},
        "manifest_mismatches": [],
    }
    assert readiness["runtime_sqlite_usage"]["passed"] is True


def test_cutover_readiness_blocks_export_columns_missing_from_postgres_schema(tmp_path):
    report_path = tmp_path / "report.json"
    export_dir = tmp_path / "export"
    _write_report(report_path, total_rows=1)
    _write_export(export_dir)
    (export_dir / "users.jsonl").write_text(
        '{"id": 1, "unexpected": "bad"}\n',
        encoding="utf-8",
    )
    _write_manifest(export_dir)

    readiness = build_cutover_readiness(
        migration_report_path=report_path,
        export_dir=export_dir,
        test_evidence={
            "backend_tests_passed": True,
            "frontend_lint_passed": True,
            "frontend_build_passed": True,
        },
        postgres_rehearsal_loaded=True,
    )

    assert readiness["ready_for_cutover"] is False
    assert {
        "gate": "postgres_schema_columns",
        "message": "Export contains columns missing from the Postgres schema.",
        "details": [{"table": "users", "unknown_columns": ["unexpected"]}],
    } in readiness["blockers"]


def test_cutover_readiness_blocks_per_table_export_count_mismatch(tmp_path):
    report_path = tmp_path / "report.json"
    export_dir = tmp_path / "export"
    _write_report(report_path, total_rows=2)
    _write_export(export_dir)
    (export_dir / "users.jsonl").write_text("", encoding="utf-8")
    (export_dir / "dailydiary_entries.jsonl").write_text(
        '{"id": 10}\n{"id": 11}\n',
        encoding="utf-8",
    )
    _write_manifest(export_dir)

    readiness = build_cutover_readiness(
        migration_report_path=report_path,
        export_dir=export_dir,
        test_evidence={
            "backend_tests_passed": True,
            "frontend_lint_passed": True,
            "frontend_build_passed": True,
        },
        postgres_rehearsal_loaded=True,
    )

    assert readiness["ready_for_cutover"] is False
    assert {
        "gate": "jsonl_export_table_counts",
        "message": "Exported table row counts do not match the migration report.",
        "details": [
            {"table": "dailydiary_entries", "report_rows": 1, "export_rows": 2},
            {"table": "users", "report_rows": 1, "export_rows": 0},
        ],
    } in readiness["blockers"]


def test_cutover_readiness_blocks_export_manifest_mismatch(tmp_path):
    report_path = tmp_path / "report.json"
    export_dir = tmp_path / "export"
    _write_report(report_path)
    _write_export(export_dir)
    with (export_dir / "users.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"id": 2}\n')

    readiness = build_cutover_readiness(
        migration_report_path=report_path,
        export_dir=export_dir,
        test_evidence={
            "backend_tests_passed": True,
            "frontend_lint_passed": True,
            "frontend_build_passed": True,
        },
        postgres_rehearsal_loaded=True,
    )

    assert readiness["ready_for_cutover"] is False
    manifest_blocker = next(
        blocker
        for blocker in readiness["blockers"]
        if blocker["gate"] == "jsonl_export_manifest"
    )
    gates = {detail["gate"] for detail in manifest_blocker["details"]}
    assert {"manifest_row_count", "manifest_byte_size", "manifest_sha256"}.issubset(
        gates
    )


def test_cutover_readiness_blocks_failed_media_audit(tmp_path):
    report_path = tmp_path / "report.json"
    media_audit_path = tmp_path / "media-audit.json"
    _write_report(report_path)
    media_audit_path.write_text(
        json.dumps(
            {
                "ready_for_cutover": False,
                "summary": {
                    "references_checked": 2,
                    "present": 1,
                    "missing": 1,
                    "invalid": 0,
                },
                "missing": [
                    {
                        "source": "daily_images",
                        "record_id": 10,
                        "storage_key": "entries/daily/1/missing.jpg",
                    }
                ],
                "invalid": [],
            }
        ),
        encoding="utf-8",
    )

    readiness = build_cutover_readiness(
        migration_report_path=report_path,
        media_audit_path=media_audit_path,
        test_evidence={
            "backend_tests_passed": True,
            "frontend_lint_passed": True,
            "frontend_build_passed": True,
        },
        postgres_rehearsal_loaded=True,
    )

    assert readiness["ready_for_cutover"] is False
    assert {
        "gate": "media_storage_files",
        "message": "Database media references do not match the active media store.",
        "details": {
            "summary": {
                "references_checked": 2,
                "present": 1,
                "missing": 1,
                "invalid": 0,
            },
            "missing": [
                {
                    "source": "daily_images",
                    "record_id": 10,
                    "storage_key": "entries/daily/1/missing.jpg",
                }
            ],
            "invalid": [],
        },
    } in readiness["blockers"]


def test_cutover_readiness_blocks_direct_sqlite_runtime_usage(tmp_path):
    report_path = tmp_path / "report.json"
    export_dir = tmp_path / "export"
    _write_report(report_path)
    _write_export(export_dir)
    _write_clean_runtime_tree(tmp_path)
    (tmp_path / "server" / "routes" / "bad.py").write_text(
        "from services.database import connect_sqlite\n",
        encoding="utf-8",
    )

    readiness = build_cutover_readiness(
        migration_report_path=report_path,
        export_dir=export_dir,
        repo_root=tmp_path,
        test_evidence={
            "backend_tests_passed": True,
            "frontend_lint_passed": True,
            "frontend_build_passed": True,
        },
        postgres_rehearsal_loaded=True,
    )

    assert readiness["ready_for_cutover"] is False
    assert readiness["runtime_sqlite_usage"]["passed"] is False
    assert {
        "gate": "runtime_sqlite_usage",
        "message": "Product runtime code still contains direct SQLite connection usage.",
        "details": [
            {
                "path": "server/routes/bad.py",
                "line": 1,
                "pattern": "connect_sqlite_import",
                "text": "from services.database import connect_sqlite",
            }
        ],
    } in readiness["blockers"]
