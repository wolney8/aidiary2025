import json
import sqlite3

from services.runtime_migrations import ensure_security_audit_events_table
from services.security_audit import record_security_event


class _Request:
    remote_addr = "203.0.113.10"
    headers = {
        "User-Agent": "OpenMynd test browser",
    }


def test_security_audit_event_hashes_request_metadata(tmp_path):
    db_path = tmp_path / "audit.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        ensure_security_audit_events_table(str(db_path))

        assert record_security_event(
            conn,
            database_provider="sqlite",
            secret="test-secret",
            user_id=7,
            event_type="login_success",
            request_obj=_Request(),
            metadata={"provider": "password", "ignored bad key": "discard"},
        )

        row = conn.execute("SELECT * FROM security_audit_events").fetchone()

    assert row["user_id"] == 7
    assert row["event_type"] == "login_success"
    assert row["outcome"] == "success"
    assert row["ip_hash"]
    assert row["user_agent_hash"]
    assert row["ip_hash"] != "203.0.113.10"
    assert row["user_agent_hash"] != "OpenMynd test browser"
    assert json.loads(row["metadata_json"]) == {"provider": "password"}


def test_security_audit_rejects_invalid_event_names_without_raising(tmp_path):
    db_path = tmp_path / "audit.db"
    ensure_security_audit_events_table(str(db_path))

    with sqlite3.connect(db_path) as conn:
        assert record_security_event(
            conn,
            database_provider="sqlite",
            secret="test-secret",
            user_id=None,
            event_type="bad event <script>",
        ) is False
        assert conn.execute("SELECT COUNT(*) FROM security_audit_events").fetchone()[0] == 0
