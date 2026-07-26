from pathlib import Path

from scripts.audit_runtime_sqlite_usage import audit_runtime_sqlite_usage


def test_runtime_sqlite_audit_passes_for_current_runtime_code():
    repo_root = Path(__file__).resolve().parents[2]

    report = audit_runtime_sqlite_usage(repo_root)

    assert report["passed"] is True
    assert report["violations"] == []


def test_runtime_sqlite_audit_flags_route_level_direct_sqlite_usage(tmp_path):
    route_dir = tmp_path / "server" / "routes"
    route_dir.mkdir(parents=True)
    (route_dir / "bad.py").write_text(
        "from services.database import connect_sqlite\n"
        "conn = sqlite3.connect('app.db')\n",
        encoding="utf-8",
    )
    allowed_dir = tmp_path / "server" / "services"
    allowed_dir.mkdir(parents=True)
    (allowed_dir / "database.py").write_text(
        "def connect_sqlite():\n"
        "    pass\n",
        encoding="utf-8",
    )

    report = audit_runtime_sqlite_usage(tmp_path)

    assert report["passed"] is False
    assert [violation["pattern"] for violation in report["violations"]] == [
        "connect_sqlite_import",
        "sqlite3_connect_call",
    ]
