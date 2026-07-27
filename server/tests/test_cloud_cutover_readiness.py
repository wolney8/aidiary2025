import json

from scripts.validate_cloud_cutover_readiness import build_cutover_readiness


def _write_report(path, *, total_rows=2, blockers=False):
    report = {
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
        "cbt_worksheets",
        "cbt_thought_record_data",
    ]:
        (export_dir / f"{table_name}.jsonl").write_text("", encoding="utf-8")


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
