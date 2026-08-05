import json
import os
import sqlite3
import tempfile
from datetime import date, timedelta

import pytest

from app import create_app


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET"] = "test-secret"

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        _create_dashboard_schema(db_path)
        yield client

    os.close(db_fd)
    os.unlink(db_path)


def _create_dashboard_schema(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                writing_rhythm_weekly_goal INTEGER DEFAULT 4,
                writing_reminder_entry_types TEXT DEFAULT 'daily,dream'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dailydiary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                entry_date TEXT,
                entry_time TEXT,
                title TEXT,
                user_message TEXT,
                ai_response TEXT,
                tags TEXT,
                daily_people_names TEXT,
                daily_places TEXT,
                mood TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dreamdiary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                entry_date TEXT,
                entry_time TEXT,
                title TEXT,
                plot TEXT,
                summary TEXT,
                interpretation TEXT,
                symbols_and_imagery TEXT,
                tags TEXT,
                dream_people_names TEXT,
                dream_places TEXT,
                mood TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cbt_worksheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                record_date TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cbt_thought_record_data (
                worksheet_id INTEGER PRIMARY KEY,
                situation TEXT NOT NULL DEFAULT '',
                unhelpful_thoughts TEXT NOT NULL DEFAULT '',
                evidence_for TEXT NOT NULL DEFAULT '',
                evidence_against TEXT NOT NULL DEFAULT '',
                balanced_thought TEXT NOT NULL DEFAULT '',
                next_step TEXT NOT NULL DEFAULT '',
                feelings_before_json TEXT NOT NULL DEFAULT '[]',
                feelings_after_json TEXT NOT NULL DEFAULT '[]'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS important_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                starts_on TEXT,
                month INTEGER NOT NULL,
                day INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                recurrence TEXT NOT NULL DEFAULT 'yearly',
                icon_name TEXT NOT NULL DEFAULT 'event',
                accent_color TEXT NOT NULL DEFAULT 'amber',
                note TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _register(client, username: str = "dash-user") -> dict[str, object]:
    response = client.post(
        "/api/register",
        data=json.dumps({
            "username": username,
            "password": "testpass123",
            "first_name": "Dash",
        }),
        content_type="application/json",
    )
    assert response.status_code == 201
    return json.loads(response.data)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_requires_auth(client):
    response = client.get("/api/dashboard/overview")

    assert response.status_code == 401


def test_dashboard_empty_account_returns_zeroed_overview(client):
    auth = _register(client)

    response = client.get(
        "/api/dashboard/overview",
        headers=_headers(auth["token"]),
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["streak"]["current_days"] == 0
    assert payload["streak"]["weekly_goal"] == 4
    assert payload["themes"] == []
    assert payload["cbt"]["total_records"] == 0
    assert payload["recent_activity"] == []
    assert {action["type"] for action in payload["quick_actions"]} == {
        "daily",
        "dream",
        "thought_record",
        "important_day",
    }


def test_dashboard_rejects_unknown_range(client):
    auth = _register(client)

    response = client.get(
        "/api/dashboard/overview?range=quarter",
        headers=_headers(auth["token"]),
    )

    assert response.status_code == 400
    payload = json.loads(response.data)
    assert "Range must be one of" in payload["error"]


def test_dashboard_overview_aggregates_entries_cbt_and_themes(client):
    auth = _register(client)
    user_id = auth["user"]["id"]
    today = date.today()
    yesterday = today - timedelta(days=1)
    previous_year = today.replace(year=today.year - 1)
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.execute(
            """
            UPDATE users
            SET writing_rhythm_weekly_goal = ?, writing_reminder_entry_types = ?
            WHERE id = ?
            """,
            (3, "daily,dream,thought_record", user_id),
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                user_id, entry_date, entry_time, title, user_message, tags,
                daily_people_names, daily_places, mood
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                today.isoformat(),
                "19:00",
                "Therapy reflection",
                "Today I wrote a grounded reflection about therapy progress.",
                "therapy,progress,lisa",
                "Penny,Lisa",
                "Clinic",
                "good",
            ),
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                user_id, entry_date, entry_time, title, user_message, tags,
                daily_people_names, daily_places, mood
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                previous_year.isoformat(),
                "19:00",
                "Previous therapy note",
                "A previous year reflection about therapy and progress.",
                "Therapy,Progress,Lisa",
                "Penny,lisa",
                "Clinic",
                "content",
            ),
        )
        conn.execute(
            """
            INSERT INTO dreamdiary_entries (
                user_id, entry_date, entry_time, title, plot, summary,
                interpretation, symbols_and_imagery, tags, dream_people_names,
                dream_places, mood
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                yesterday.isoformat(),
                "08:00",
                "Moon bridge",
                "I crossed a silver bridge under a moon.",
                "A dream about transition.",
                "The bridge suggested change.",
                "moon,bridge",
                "transition,dream",
                "",
                "Forest",
                "very good",
            ),
        )
        cursor = conn.execute(
            """
            INSERT INTO cbt_worksheets (user_id, title, status, record_date)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, "Therapy thought", "completed", today.isoformat()),
        )
        worksheet_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO cbt_thought_record_data (
                worksheet_id, situation, unhelpful_thoughts, balanced_thought,
                feelings_before_json, feelings_after_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                worksheet_id,
                "I worried I should have done better.",
                "I should always get everything right.",
                "I can improve without being perfect.",
                json.dumps([{"label": "Anxiety", "intensity": 80}]),
                json.dumps([{"label": "Anxiety", "intensity": 35}]),
            ),
        )
        conn.execute(
            """
            INSERT INTO important_days (
                user_id, label, starts_on, month, day, category, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, "Therapy milestone", today.isoformat(), today.month, today.day, "milestone", "First milestone."),
        )

    response = client.get(
        "/api/dashboard/overview?range=1w",
        headers=_headers(auth["token"]),
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["streak"]["current_days"] >= 1
    assert payload["streak"]["weekly_goal"] == 3
    assert payload["streak"]["week_count"] == 3
    assert any(day["daily_words"] > 0 for day in payload["series"])
    assert any(day["dream_words"] > 0 for day in payload["series"])
    assert any(theme["label"] == "therapy" for theme in payload["themes"])
    assert any(theme["label"] == "moon" for theme in payload["themes"])
    assert sum(1 for theme in payload["themes"] if theme["label"].casefold() == "lisa") == 1
    assert payload["cbt"]["total_records"] == 1
    assert payload["cbt"]["average_change"] == -45
    assert any(
        item["type"] == "important_day"
        for item in payload["recent_activity"]
    )
    assert len(payload["recent_activity_by_type"]["daily"]) == 1
    assert len(payload["recent_activity_by_type"]["dream"]) == 1
    assert payload["dream_insights"]["total_dreams"] == 1
    assert payload["dream_insights"]["latest"]["title"] == "Moon bridge"
    assert payload["dream_insights"]["recent"][0]["title"] == "Moon bridge"
    assert "moon" in payload["dream_insights"]["recent"][0]["symbols"]
    assert any(
        item["label"] == "moon"
        for item in payload["dream_insights"]["top_symbols"]
    )
    assert payload["focus_sections"]["memory_echo"]["count"] == 1
    assert payload["focus_sections"]["memory_echo"]["items"][0]["title"] == "Previous therapy note"
    assert 0 < len(payload["focus_sections"]["theme_drift"]) <= 4
    assert any(
        item["current_count"] > 0
        for item in payload["focus_sections"]["theme_drift"]
    )
    assert any(
        item["label"] == "therapy"
        and item["count"] == 2
        for item in payload["focus_sections"]["mood_anchors"]
    )
    assert sum(
        1
        for item in payload["focus_sections"]["mood_anchors"]
        if item["label"].casefold() == "lisa"
    ) == 1
    assert payload["focus_sections"]["important_day_cues"][0]["label"] == "Therapy milestone"


def test_dashboard_theme_focus_filters_chart_series(client):
    auth = _register(client)
    user_id = auth["user"]["id"]
    today = date.today()
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                user_id, entry_date, title, user_message, tags, mood
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                today.isoformat(),
                "Therapy note",
                "Therapy words count only here",
                "Therapy",
                "good",
            ),
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                user_id, entry_date, title, user_message, tags, mood
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                today.isoformat(),
                "Gym note",
                "Gym words should be excluded from focused chart",
                "gym",
                "good",
            ),
        )

    response = client.get(
        "/api/dashboard/overview?range=1w&theme_label=therapy&theme_kind=tag",
        headers=_headers(auth["token"]),
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    today_bucket = next(
        day for day in payload["series"] if day["date"] == today.isoformat()
    )
    assert payload["theme_filter"] == {"label": "therapy", "kind": "tag"}
    assert today_bucket["daily_words"] == 5


def test_dashboard_range_filter_excludes_older_series_rows(client):
    auth = _register(client)
    user_id = auth["user"]["id"]
    old_date = date.today() - timedelta(days=60)
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                user_id, entry_date, title, user_message, tags, mood
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, old_date.isoformat(), "Old entry", "Old words here", "old", "good"),
        )

    week_response = client.get(
        "/api/dashboard/overview?range=1w",
        headers=_headers(auth["token"]),
    )
    all_response = client.get(
        "/api/dashboard/overview?range=all",
        headers=_headers(auth["token"]),
    )

    assert week_response.status_code == 200
    assert all_response.status_code == 200
    week_payload = json.loads(week_response.data)
    all_payload = json.loads(all_response.data)
    assert old_date.isoformat() not in [day["date"] for day in week_payload["series"]]
    assert old_date.isoformat() in [day["date"] for day in all_payload["series"]]


def test_dashboard_is_user_scoped(client):
    first = _register(client, "first-dash")
    second = _register(client, "second-dash")
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                user_id, entry_date, title, user_message, tags, mood
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                first["user"]["id"],
                date.today().isoformat(),
                "Private entry",
                "Private words should not leak.",
                "private-tag",
                "good",
            ),
        )

    response = client.get(
        "/api/dashboard/overview?range=all",
        headers=_headers(second["token"]),
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["themes"] == []
    assert payload["recent_activity"] == []
