from pathlib import Path

from scripts.run_database_backup_bundle import run_database_backup_bundle


def test_database_backup_bundle_runs_sqlite_and_postgres_tasks(tmp_path):
    source_db = tmp_path / "app.db"
    source_db.write_text("sqlite", encoding="utf-8")
    calls = {}

    def fake_sqlite_backup(**kwargs):
        calls["sqlite"] = kwargs
        return {
            "provider": "sqlite",
            "backup_path": str(kwargs["backup_dir"] / "openmynd-sqlite.db"),
            "total_rows": 2,
        }

    def fake_postgres_snapshot(**kwargs):
        calls["postgres"] = kwargs
        return {
            "provider": "postgres",
            "snapshot_dir": str(kwargs["output_dir"] / "postgres-snapshot"),
            "total_rows": 2,
        }

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url="postgresql://example/openmynd",
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        label="daily",
        sqlite_retain=7,
        summary_json=tmp_path / "summary.json",
        create_sqlite_backup_fn=fake_sqlite_backup,
        export_postgres_snapshot_fn=fake_postgres_snapshot,
    )

    assert summary["ok"] is True
    assert summary["counts"] == {"completed": 2, "failed": 0, "skipped": 0}
    assert summary["tasks"]["sqlite_backup"]["manifest"]["provider"] == "sqlite"
    assert summary["tasks"]["postgres_snapshot"]["manifest"]["provider"] == "postgres"
    assert calls["sqlite"]["source_db"] == source_db.resolve()
    assert calls["sqlite"]["retain"] == 7
    assert calls["postgres"]["label"] == "daily"
    assert Path(summary["summary_path"]).exists()


def test_database_backup_bundle_skips_postgres_when_url_missing(tmp_path):
    source_db = tmp_path / "app.db"
    source_db.write_text("sqlite", encoding="utf-8")

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        summary_json=tmp_path / "summary.json",
        create_sqlite_backup_fn=lambda **_kwargs: {"provider": "sqlite"},
    )

    assert summary["ok"] is True
    assert summary["counts"] == {"completed": 1, "failed": 0, "skipped": 1}
    assert summary["tasks"]["postgres_snapshot"] == {
        "status": "skipped",
        "reason": "DATABASE_URL was not supplied.",
    }


def test_database_backup_bundle_skips_missing_sqlite_source(tmp_path):
    summary = run_database_backup_bundle(
        sqlite_source_db=tmp_path / "missing.db",
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        summary_json=tmp_path / "summary.json",
    )

    assert summary["ok"] is True
    assert summary["counts"] == {"completed": 0, "failed": 0, "skipped": 2}
    assert summary["tasks"]["sqlite_backup"]["status"] == "skipped"
    assert "missing.db" in summary["tasks"]["sqlite_backup"]["reason"]


def test_database_backup_bundle_reports_task_failures(tmp_path):
    source_db = tmp_path / "app.db"
    source_db.write_text("sqlite", encoding="utf-8")

    def failing_sqlite_backup(**_kwargs):
        raise RuntimeError("disk full")

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        summary_json=tmp_path / "summary.json",
        create_sqlite_backup_fn=failing_sqlite_backup,
    )

    assert summary["ok"] is False
    assert summary["exit_code"] == 1
    assert summary["counts"] == {"completed": 0, "failed": 1, "skipped": 1}
    assert summary["tasks"]["sqlite_backup"] == {
        "status": "failed",
        "error_type": "RuntimeError",
        "message": "disk full",
    }
