import json

from scripts.create_cloud_parity_report import (
    build_cloud_parity_report,
    render_markdown_report,
)


def _write_readiness(path, *, ready=True):
    path.write_text(
        json.dumps(
            {
                "ready_for_cutover": ready,
                "blockers": [] if ready else [{"gate": "example"}],
                "source_summary": {"tables_present": 18, "total_rows": 1193},
                "load_plan_summary": {
                    "total_rows": 1193,
                    "missing_files": [],
                    "manifest": {"present": True, "total_rows": 1193},
                    "manifest_mismatches": [],
                },
                "runtime_sqlite_usage": {"passed": True, "violations": []},
            }
        ),
        encoding="utf-8",
    )


def _all_evidence():
    return {
        "backend_tests_passed": True,
        "frontend_lint_passed": True,
        "frontend_build_passed": True,
        "frontend_smoke_passed": True,
        "frontend_a11y_passed": True,
        "manual_rehearsal_smoke_passed": True,
    }


def test_cloud_parity_report_is_ready_when_all_gates_pass(tmp_path):
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path)

    report = build_cloud_parity_report(
        readiness_report_path=readiness_path,
        postgres_target="neon/rehearsal",
        evidence=_all_evidence(),
    )

    assert report["parity_ready"] is True
    assert report["blockers"] == []
    assert report["source_summary"]["total_rows"] == 1193
    assert report["load_plan_summary"]["total_rows"] == 1193
    assert report["next_required_actions"] == [
        "Proceed to cutover runbook and rollback rehearsal sign-off."
    ]


def test_cloud_parity_report_blocks_missing_evidence(tmp_path):
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path)

    report = build_cloud_parity_report(
        readiness_report_path=readiness_path,
        evidence={"backend_tests_passed": True},
    )

    assert report["parity_ready"] is False
    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert gates == {"automated_regression_evidence", "manual_rehearsal_smoke"}


def test_cloud_parity_report_blocks_failed_readiness(tmp_path):
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path, ready=False)

    report = build_cloud_parity_report(
        readiness_report_path=readiness_path,
        evidence=_all_evidence(),
    )

    assert report["parity_ready"] is False
    assert report["blockers"][0]["gate"] == "readiness_report"


def test_markdown_report_summarises_status_and_evidence(tmp_path):
    readiness_path = tmp_path / "readiness.json"
    _write_readiness(readiness_path)
    report = build_cloud_parity_report(
        readiness_report_path=readiness_path,
        postgres_target="neon/rehearsal",
        evidence=_all_evidence(),
    )

    markdown = render_markdown_report(report)

    assert "# Cloud Parity Report" in markdown
    assert "Status: READY" in markdown
    assert "Postgres target: neon/rehearsal" in markdown
    assert "- backend_tests_passed: passed" in markdown
