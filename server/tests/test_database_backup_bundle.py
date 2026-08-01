from pathlib import Path

from scripts.run_database_backup_bundle import _redact_secrets, run_database_backup_bundle


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
    assert summary["notification"] == {
        "status": "skipped",
        "reason": "notification disabled",
    }


def test_database_backup_bundle_skips_failure_notification_after_success(tmp_path):
    source_db = tmp_path / "app.db"
    source_db.write_text("sqlite", encoding="utf-8")
    notifications = []

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        summary_json=tmp_path / "summary.json",
        notification_webhook_url="https://monitor.example/hooks/db",
        notify_mode="failure",
        create_sqlite_backup_fn=lambda **_kwargs: {"provider": "sqlite"},
        notify_fn=lambda **kwargs: notifications.append(kwargs) or {"status": "sent"},
    )

    assert summary["ok"] is True
    assert notifications == []
    assert summary["notification"] == {
        "status": "skipped",
        "reason": "backup bundle completed successfully",
    }


def test_database_backup_bundle_sends_failure_notification(tmp_path):
    source_db = tmp_path / "app.db"
    source_db.write_text("sqlite", encoding="utf-8")
    notifications = []

    def failing_sqlite_backup(**_kwargs):
        raise RuntimeError(
            "could not connect to postgresql://user:secret@example.test/openmynd"
        )

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        summary_json=tmp_path / "summary.json",
        notification_webhook_url="https://monitor.example/hooks/db",
        notify_mode="failure",
        create_sqlite_backup_fn=failing_sqlite_backup,
        notify_fn=lambda **kwargs: notifications.append(kwargs) or {"status": "sent"},
    )

    assert summary["ok"] is False
    assert summary["notification"] == {"status": "sent"}
    assert notifications[0]["webhook_url"] == "https://monitor.example/hooks/db"
    assert "secret" not in str(summary)
    assert "postgresql://<redacted>" in summary["tasks"]["sqlite_backup"]["message"]


def test_database_backup_bundle_can_notify_on_success(tmp_path):
    source_db = tmp_path / "app.db"
    source_db.write_text("sqlite", encoding="utf-8")
    notifications = []

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        summary_json=tmp_path / "summary.json",
        notification_webhook_url="https://monitor.example/hooks/db",
        notify_mode="always",
        create_sqlite_backup_fn=lambda **_kwargs: {"provider": "sqlite"},
        notify_fn=lambda **kwargs: notifications.append(kwargs) or {"status": "sent"},
    )

    assert summary["ok"] is True
    assert summary["notification"] == {"status": "sent"}
    assert len(notifications) == 1


def test_database_backup_bundle_records_notification_failure(tmp_path):
    source_db = tmp_path / "app.db"
    source_db.write_text("sqlite", encoding="utf-8")

    def failing_notify(**_kwargs):
        raise RuntimeError(
            "webhook rejected postgresql://user:secret@example.test/openmynd"
        )

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        summary_json=tmp_path / "summary.json",
        notification_webhook_url="https://monitor.example/hooks/db",
        notify_mode="always",
        create_sqlite_backup_fn=lambda **_kwargs: {"provider": "sqlite"},
        notify_fn=failing_notify,
    )

    assert summary["ok"] is True
    assert summary["notification"] == {
        "status": "failed",
        "error_type": "RuntimeError",
        "message": "webhook rejected postgresql://<redacted>",
    }


def test_database_backup_bundle_redacts_postgres_urls_recursively():
    assert _redact_secrets(
        {
            "message": "failed postgresql://user:secret@example.test/openmynd",
            "nested": ["postgres://user:secret@example.test/db"],
        }
    ) == {
        "message": "failed postgresql://<redacted>",
        "nested": ["postgresql://<redacted>"],
    }
