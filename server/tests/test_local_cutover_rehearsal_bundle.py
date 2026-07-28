import json
import sqlite3
from pathlib import Path

import pytest

from scripts.run_local_cutover_rehearsal_bundle import (
    build_local_cutover_rehearsal_bundle,
)


def _seed_source_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute(
            """
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date TEXT,
                title TEXT
            )
            """
        )
        conn.execute("INSERT INTO users (id, username) VALUES (1, 'rehearsal-user')")
        conn.execute(
            """
            INSERT INTO dailydiary_entries (id, user_id, entry_date, title)
            VALUES (1, 1, '2026-07-28', 'Bundle rehearsal')
            """
        )


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


def test_local_cutover_rehearsal_bundle_writes_safe_artifacts(tmp_path):
    source_db = tmp_path / "source.db"
    work_dir = tmp_path / "bundle"
    repo_root = tmp_path / "repo"
    _seed_source_db(source_db)
    _write_clean_runtime_tree(repo_root)

    bundle = build_local_cutover_rehearsal_bundle(
        source_db=source_db,
        work_dir=work_dir,
        repo_root=repo_root,
        test_evidence={
            "backend_tests_passed": True,
            "frontend_lint_passed": True,
            "frontend_build_passed": True,
        },
    )

    assert bundle["summary"]["source_total_rows"] == 2
    assert bundle["summary"]["export_total_rows"] == 2
    assert bundle["summary"]["manifest_valid"] is True
    assert bundle["summary"]["ready_for_cutover"] is False
    assert "Apply the export to a disposable Postgres branch" in " ".join(
        bundle["next_required_actions"]
    )
    for path_value in bundle["artifacts"].values():
        assert Path(path_value).exists()

    saved_bundle = json.loads(
        (work_dir / "local-cutover-rehearsal-bundle.json").read_text(encoding="utf-8")
    )
    assert saved_bundle["artifacts"]["export_manifest"].endswith("manifest.json")
    assert saved_bundle["artifacts"]["operator_summary"].endswith(
        "operator-summary.md"
    )

    operator_summary = (work_dir / "operator-summary.md").read_text(encoding="utf-8")
    assert "Status: NOT READY" in operator_summary
    assert "SQLite source rows: 2" in operator_summary
    assert "postgres_rehearsal" in operator_summary


def test_local_cutover_rehearsal_bundle_refuses_non_empty_work_dir(tmp_path):
    source_db = tmp_path / "source.db"
    work_dir = tmp_path / "bundle"
    repo_root = tmp_path / "repo"
    _seed_source_db(source_db)
    _write_clean_runtime_tree(repo_root)
    work_dir.mkdir()
    (work_dir / "old.txt").write_text("stale", encoding="utf-8")

    with pytest.raises(ValueError, match="Work directory is not empty"):
        build_local_cutover_rehearsal_bundle(
            source_db=source_db,
            work_dir=work_dir,
            repo_root=repo_root,
        )


def test_local_cutover_rehearsal_bundle_overwrite_replaces_artifacts(tmp_path):
    source_db = tmp_path / "source.db"
    work_dir = tmp_path / "bundle"
    repo_root = tmp_path / "repo"
    _seed_source_db(source_db)
    _write_clean_runtime_tree(repo_root)
    work_dir.mkdir()
    (work_dir / "old.txt").write_text("stale", encoding="utf-8")

    bundle = build_local_cutover_rehearsal_bundle(
        source_db=source_db,
        work_dir=work_dir,
        repo_root=repo_root,
        overwrite=True,
    )

    assert not (work_dir / "old.txt").exists()
    assert (work_dir / "export" / "manifest.json").exists()
    assert bundle["summary"]["manifest_valid"] is True
