import json
import sqlite3
from pathlib import Path

from scripts.create_sqlite_backup import create_sqlite_backup


def _seed_db(path, *, title="entry"):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.execute("CREATE TABLE dailydiary_entries (id INTEGER PRIMARY KEY, title TEXT)")
        conn.execute("INSERT INTO users (id, username) VALUES (1, 'will')")
        conn.execute("INSERT INTO dailydiary_entries (id, title) VALUES (1, ?)", (title,))


def test_create_sqlite_backup_writes_consistent_snapshot_and_manifest(tmp_path):
    source_db = tmp_path / "app.db"
    backup_dir = tmp_path / "backups"
    _seed_db(source_db, title="real entry")

    manifest = create_sqlite_backup(
        source_db=source_db,
        backup_dir=backup_dir,
        label="pre-cutover",
        retain=5,
    )

    backup_path = Path(manifest["backup_path"])
    manifest_path = backup_path.with_suffix(".manifest.json")
    assert backup_path.exists()
    assert manifest_path.exists()
    assert manifest["label"] == "pre-cutover"
    assert manifest["table_counts"] == {"dailydiary_entries": 1, "users": 1}
    assert manifest["total_rows"] == 2
    assert len(manifest["sha256"]) == 64

    with sqlite3.connect(backup_path) as conn:
        row = conn.execute("SELECT title FROM dailydiary_entries").fetchone()
    assert row == ("real entry",)

    written_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written_manifest["backup_path"] == manifest["backup_path"]
    assert "table_counts" in written_manifest


def test_create_sqlite_backup_prunes_old_backups_with_manifests(tmp_path):
    source_db = tmp_path / "app.db"
    backup_dir = tmp_path / "backups"
    _seed_db(source_db)

    first = create_sqlite_backup(
        source_db=source_db,
        backup_dir=backup_dir,
        label="one",
        retain=10,
    )
    second = create_sqlite_backup(
        source_db=source_db,
        backup_dir=backup_dir,
        label="two",
        retain=10,
    )
    third = create_sqlite_backup(
        source_db=source_db,
        backup_dir=backup_dir,
        label="three",
        retain=2,
    )

    remaining_backups = sorted(backup_dir.glob("openmynd-sqlite-*.db"))
    assert len(remaining_backups) == 2
    assert not Path(first["backup_path"]).exists()
    assert not Path(first["backup_path"]).with_suffix(".manifest.json").exists()
    assert Path(second["backup_path"]).exists()
    assert Path(third["backup_path"]).exists()
    assert third["retention"]["removed"] == [first["backup_path"]]
