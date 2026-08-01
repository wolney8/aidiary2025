from pathlib import Path

from scripts.run_database_backup_bundle import (
    _redact_secrets,
    create_media_archive,
    run_database_backup_bundle,
)


def test_database_backup_bundle_runs_sqlite_and_postgres_tasks(tmp_path):
    source_db = tmp_path / "app.db"
    media_root = tmp_path / "media"
    source_db.write_text("sqlite", encoding="utf-8")
    media_root.mkdir()
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

    def fake_media_archive(**kwargs):
        calls["media"] = kwargs
        return {
            "provider": "local_media",
            "archive_path": str(kwargs["output_dir"] / "media.zip"),
            "file_count": 1,
        }

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url="postgresql://example/openmynd",
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        media_root=media_root,
        media_backup_dir=tmp_path / "media-backups",
        label="daily",
        sqlite_retain=7,
        summary_json=tmp_path / "summary.json",
        create_sqlite_backup_fn=fake_sqlite_backup,
        export_postgres_snapshot_fn=fake_postgres_snapshot,
        create_media_archive_fn=fake_media_archive,
    )

    assert summary["ok"] is True
    assert summary["counts"] == {"completed": 3, "failed": 0, "skipped": 0}
    assert summary["tasks"]["sqlite_backup"]["manifest"]["provider"] == "sqlite"
    assert summary["tasks"]["postgres_snapshot"]["manifest"]["provider"] == "postgres"
    assert summary["tasks"]["media_archive"]["manifest"]["provider"] == "local_media"
    assert calls["sqlite"]["source_db"] == source_db.resolve()
    assert calls["sqlite"]["retain"] == 7
    assert calls["postgres"]["label"] == "daily"
    assert calls["media"]["media_root"] == media_root.resolve()
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
    assert summary["counts"] == {"completed": 1, "failed": 0, "skipped": 2}
    assert summary["tasks"]["postgres_snapshot"] == {
        "status": "skipped",
        "reason": "DATABASE_URL was not supplied.",
    }
    assert summary["tasks"]["media_archive"] == {
        "status": "skipped",
        "reason": "MEDIA_ROOT was not supplied.",
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
    assert summary["counts"] == {"completed": 0, "failed": 0, "skipped": 3}
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
    assert summary["counts"] == {"completed": 0, "failed": 1, "skipped": 2}
    assert summary["tasks"]["sqlite_backup"] == {
        "status": "failed",
        "error_type": "RuntimeError",
        "message": "disk full",
    }
    assert summary["notification"] == {
        "status": "skipped",
        "reason": "notification disabled",
    }


def test_database_backup_bundle_archives_media_when_root_supplied(tmp_path):
    source_db = tmp_path / "app.db"
    media_root = tmp_path / "media"
    source_db.write_text("sqlite", encoding="utf-8")
    (media_root / "entries/daily/1").mkdir(parents=True)
    (media_root / "entries/daily/1/photo.jpg").write_bytes(b"image")

    summary = run_database_backup_bundle(
        sqlite_source_db=source_db,
        sqlite_backup_dir=tmp_path / "sqlite-backups",
        postgres_database_url=None,
        postgres_snapshot_dir=tmp_path / "postgres-snapshots",
        media_root=media_root,
        media_backup_dir=tmp_path / "media-backups",
        summary_json=tmp_path / "summary.json",
        create_sqlite_backup_fn=lambda **_kwargs: {"provider": "sqlite"},
    )

    media_manifest = summary["tasks"]["media_archive"]["manifest"]
    assert summary["ok"] is True
    assert summary["counts"] == {"completed": 2, "failed": 0, "skipped": 1}
    assert media_manifest["provider"] == "local_media"
    assert media_manifest["file_count"] == 1
    assert Path(media_manifest["archive_path"]).exists()
    assert Path(media_manifest["manifest_path"]).exists()


def test_create_media_archive_stores_media_under_stable_zip_prefix(tmp_path):
    media_root = tmp_path / "media"
    (media_root / "entries/daily/1").mkdir(parents=True)
    (media_root / "entries/daily/1/photo.jpg").write_bytes(b"image")

    manifest = create_media_archive(
        media_root=media_root,
        output_dir=tmp_path / "media-backups",
        label="daily",
    )

    archive_path = Path(manifest["archive_path"])
    assert manifest["file_count"] == 1
    assert manifest["source_bytes"] == 5
    assert len(manifest["sha256"]) == 64
    assert archive_path.exists()

    import zipfile

    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == ["media/entries/daily/1/photo.jpg"]


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
