import sqlite3
from pathlib import Path

from scripts.run_neon_cutover_rehearsal import run_neon_cutover_rehearsal


def _create_minimal_sqlite(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO users (id, username, password) VALUES (1, 'will', 'hash')"
        )


def test_neon_cutover_rehearsal_dry_run_creates_artifacts(tmp_path):
    source_db = tmp_path / "app.db"
    work_dir = tmp_path / "rehearsal"
    _create_minimal_sqlite(source_db)

    result = run_neon_cutover_rehearsal(
        source_db=source_db,
        work_dir=work_dir,
        apply=False,
    )

    assert result["apply"] is False
    assert result["postgres_migrations"] is None
    assert result["postgres_load"] is None
    assert Path(result["sqlite_backup"]["backup_path"]).exists()
    assert Path(result["migration_report_path"]).exists()
    assert Path(result["load_plan_path"]).exists()
    assert Path(result["export_dir"], "users.jsonl").exists()
    assert result["load_plan_summary"]["total_rows"] == 1
    assert Path(result["result_path"]).exists()
