from flask import Flask

from routes import analyse


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _RecordingConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM users" in sql:
            return _Rows(
                [
                    {
                        "ai_tone": "friendly",
                        "ai_verbosity": "balanced",
                        "ai_focus": "reflective",
                        "ai_model": "gpt-4.1-mini",
                        "allow_ai_history": 1,
                        "display_name": "Will",
                        "pronouns": "he/him",
                        "gender": "man",
                        "custom_guidance": "Keep it practical",
                        "sex": "",
                        "goals": "",
                    }
                ]
            )
        if "FROM dailydiary_entries" in sql:
            return _Rows([])
        if "FROM cbt_worksheets" in sql:
            return _Rows([])
        return _Rows([])


def _app(provider="postgres"):
    app = Flask(__name__)
    app.config["DATABASE_PROVIDER"] = provider
    return app


def test_user_analysis_settings_adapts_placeholders_for_configured_provider():
    conn = _RecordingConnection()

    with _app("postgres").app_context():
        settings = analyse._load_user_analysis_settings(conn, 7)

    sql, params = conn.calls[0]
    assert "WHERE id = $1" in sql
    assert "?" not in sql
    assert params == (7,)
    assert settings["personal_context"] == (
        "Display name: Will\n"
        "Pronouns: he/him\n"
        "Gender: man\n"
        "Custom guidance: Keep it practical"
    )


def test_related_history_context_adapts_all_query_placeholders_for_configured_provider():
    conn = _RecordingConnection()

    with _app("postgres").app_context():
        context = analyse._build_related_history_context(
            conn,
            user_id=7,
            mode="daily",
            current_text="meeting Katie at the cafe",
            current_entry_id=22,
            reference_date="2026-07-21",
        )

    assert context is None
    daily_sql, daily_params = conn.calls[1]
    thought_record_sql, thought_record_params = conn.calls[2]
    assert "user_id = $1" in daily_sql
    assert "entry_date <= $3" in daily_sql
    assert "id != $5" in daily_sql
    assert "?" not in daily_sql
    assert daily_params == (7, "2026-07-21", "2026-07-21", 22, 22, analyse.RELATED_CONTEXT_SCAN_LIMIT)
    assert "w.user_id = $1" in thought_record_sql
    assert "w.record_date <= $3" in thought_record_sql
    assert "?" not in thought_record_sql
    assert thought_record_params == (7, "2026-07-21", "2026-07-21", analyse.RELATED_CONTEXT_SCAN_LIMIT)
