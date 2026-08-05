from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.media_storage import resolve_image_url
from services.sql_compat import adapt_placeholders


dashboard_bp = Blueprint("dashboard", __name__)

VALID_RANGES = {"1w", "1m", "3m", "all"}
RANGE_DAYS = {
    "1w": 7,
    "1m": 30,
    "3m": 90,
}
WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)

MOOD_SCORES = {
    "very bad": 1,
    "awful": 1,
    "bad": 2,
    "sad": 2,
    "grumpy": 2,
    "stressed": 2,
    "anxious": 2,
    "meh": 3,
    "quiet": 3,
    "neutral": 3,
    "okay": 3,
    "ok": 3,
    "not too bad": 3,
    "good": 4,
    "content": 4,
    "happy": 4,
    "very good": 5,
    "great": 5,
    "excellent": 5,
}

CBT_PATTERN_KEYWORDS = {
    "All-or-nothing": ("always", "never", "everything", "nothing", "ruined"),
    "Catastrophising": ("disaster", "catastrophe", "terrible", "worst", "panic"),
    "Mind reading": ("they think", "she thinks", "he thinks", "everyone thinks"),
    "Should statements": ("should", "must", "have to", "supposed to"),
    "Overgeneralising": ("every time", "again and again", "always happens"),
}


def _database_adapter() -> DatabaseAdapter:
    return current_app.config["DATABASE_ADAPTER"]


def _database_provider() -> str:
    return current_app.config.get("DATABASE_PROVIDER", SQLITE_PROVIDER)


def _sql(statement: str) -> str:
    return adapt_placeholders(statement, _database_provider())


def get_db():
    return _database_adapter().connect(timeout=10, foreign_keys=True)


@dashboard_bp.route("/dashboard/overview", methods=["GET"])
@jwt_required()
def get_dashboard_overview():
    user_id = int(get_jwt_identity())
    selected_range = str(request.args.get("range") or "1m").strip().lower()
    if selected_range not in VALID_RANGES:
        return jsonify({"error": "Range must be one of 1w, 1m, 3m, or all"}), 400
    theme_label = str(request.args.get("theme_label") or "").strip()
    theme_kind = str(request.args.get("theme_kind") or "").strip()

    today = date.today()
    start_date = _range_start(today, selected_range)

    with get_db() as conn:
        settings = _fetch_user_settings(conn, user_id)
        all_daily_rows = _fetch_daily_rows(conn, user_id, start_date)
        all_dream_rows = _fetch_dream_rows(conn, user_id, start_date)
        cbt_rows = _fetch_cbt_rows(conn, user_id, start_date)
        important_day_rows = _fetch_important_day_rows(conn, user_id)
        history_daily_rows = _fetch_daily_rows(conn, user_id, None)
        history_dream_rows = _fetch_dream_rows(conn, user_id, None)

    themes = _build_themes(all_daily_rows, all_dream_rows)
    daily_rows, dream_rows = _filter_rows_by_theme(
        all_daily_rows,
        all_dream_rows,
        theme_label,
        theme_kind,
    )
    series = _build_series(today, selected_range, start_date, daily_rows, dream_rows, cbt_rows)
    streak = _build_streak(settings, today, daily_rows, dream_rows, cbt_rows)
    cbt = _build_cbt_summary(cbt_rows)
    recent_activity = _build_recent_activity(
        daily_rows,
        dream_rows,
        cbt_rows,
        important_day_rows,
    )
    recent_activity_by_type = _group_recent_activity(recent_activity)
    dream_insights = _build_dream_insights(history_dream_rows)
    focus_sections = _build_focus_sections(
        today,
        history_daily_rows,
        history_dream_rows,
        important_day_rows,
    )

    today_key = today.isoformat()
    return jsonify({
        "range": selected_range,
        "theme_filter": (
            {"label": theme_label, "kind": theme_kind}
            if theme_label and theme_kind
            else None
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "streak": streak,
        "series": series,
        "themes": themes,
        "cbt": cbt,
        "recent_activity": recent_activity,
        "recent_activity_by_type": recent_activity_by_type,
        "dream_insights": dream_insights,
        "focus_sections": focus_sections,
        "quick_actions": [
            {
                "type": "daily",
                "label": "Diary",
                "icon": "book",
                "route": f"/entries/create?date={today_key}&type=daily",
            },
            {
                "type": "dream",
                "label": "Dream",
                "icon": "nights_stay",
                "route": f"/entries/create?date={today_key}&type=dream",
            },
            {
                "type": "thought_record",
                "label": "Thought record",
                "icon": "psychology_alt",
                "route": f"/entries/create?date={today_key}&type=thought_record",
            },
            {
                "type": "important_day",
                "label": "Important day",
                "icon": "event",
                "route": f"/entries/create?date={today_key}&type=important_day",
            },
        ],
    }), 200


def _range_start(today: date, selected_range: str) -> date | None:
    days = RANGE_DAYS.get(selected_range)
    if not days:
        return None
    return today - timedelta(days=days - 1)


def _fetch_user_settings(conn, user_id: int) -> dict[str, Any]:
    try:
        columns = _database_adapter().table_columns(conn, "users")
        select_parts = ["id"]
        select_parts.append(
            "writing_rhythm_weekly_goal"
            if "writing_rhythm_weekly_goal" in columns
            else "4 AS writing_rhythm_weekly_goal"
        )
        select_parts.append(
            "writing_reminder_entry_types"
            if "writing_reminder_entry_types" in columns
            else "'daily,dream' AS writing_reminder_entry_types"
        )
        row = conn.execute(
            _sql(f"SELECT {', '.join(select_parts)} FROM users WHERE id = ?"),
            (user_id,),
        ).fetchone()
    except Exception:
        row = None
    return _row_to_dict(row) if row else {
        "writing_rhythm_weekly_goal": 4,
        "writing_reminder_entry_types": "daily,dream",
    }


def _fetch_daily_rows(conn, user_id: int, start_date: date | None) -> list[dict[str, Any]]:
    where = "WHERE user_id = ?"
    params: list[Any] = [user_id]
    if start_date:
        where += " AND entry_date >= ?"
        params.append(start_date.isoformat())
    try:
        rows = conn.execute(_sql(f"""
            SELECT id, entry_date, entry_time, title, user_message, ai_response,
                   tags, daily_people_names, daily_places, mood
            FROM dailydiary_entries
            {where}
            ORDER BY entry_date DESC, COALESCE(entry_time, '19:00') DESC, id DESC
        """), params).fetchall()
    except Exception:
        return []
    return [_row_to_dict(row) | {"type": "daily"} for row in rows]


def _fetch_dream_rows(conn, user_id: int, start_date: date | None) -> list[dict[str, Any]]:
    where = "WHERE user_id = ?"
    params: list[Any] = [user_id]
    if start_date:
        where += " AND entry_date >= ?"
        params.append(start_date.isoformat())
    try:
        columns = set(_database_adapter().table_columns(conn, "dreamdiary_entries"))
    except Exception:
        columns = set()
    image_select = [
        "image_url" if "image_url" in columns else "NULL AS image_url",
        "image_storage_key" if "image_storage_key" in columns else "NULL AS image_storage_key",
        "image_source" if "image_source" in columns else "NULL AS image_source",
    ]
    try:
        rows = conn.execute(_sql(f"""
            SELECT id, entry_date, entry_time, title, plot, summary, interpretation,
                   symbols_and_imagery, tags, dream_people_names, dream_places, mood,
                   {', '.join(image_select)}
            FROM dreamdiary_entries
            {where}
            ORDER BY entry_date DESC, COALESCE(entry_time, '08:00') DESC, id DESC
        """), params).fetchall()
    except Exception:
        return []
    return [_row_to_dict(row) | {"type": "dream"} for row in rows]


def _fetch_cbt_rows(conn, user_id: int, start_date: date | None) -> list[dict[str, Any]]:
    where = "WHERE w.user_id = ?"
    params: list[Any] = [user_id]
    if start_date:
        where += " AND w.record_date >= ?"
        params.append(start_date.isoformat())
    try:
        rows = conn.execute(_sql(f"""
            SELECT w.id, w.title, w.status, w.record_date, w.updated_at,
                   d.situation, d.unhelpful_thoughts, d.evidence_for,
                   d.evidence_against, d.balanced_thought, d.next_step,
                   d.feelings_before_json, d.feelings_after_json
            FROM cbt_worksheets w
            LEFT JOIN cbt_thought_record_data d ON d.worksheet_id = w.id
            {where}
            ORDER BY w.record_date DESC, w.updated_at DESC, w.id DESC
        """), params).fetchall()
    except Exception:
        return []
    return [_row_to_dict(row) | {"type": "thought_record"} for row in rows]


def _fetch_important_day_rows(conn, user_id: int) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(_sql("""
            SELECT id, label, starts_on, month, day, category, recurrence,
                   icon_name, accent_color, note, updated_at
            FROM important_days
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
        """), (user_id,)).fetchall()
    except Exception:
        return []
    return [_row_to_dict(row) | {"type": "important_day"} for row in rows]


def _build_series(
    today: date,
    selected_range: str,
    start_date: date | None,
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
    cbt_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "daily_words": 0,
            "dream_words": 0,
            "thought_records": 0,
            "mood_values": [],
        }
    )
    for row in daily_rows:
        key = _date_key(row.get("entry_date"))
        if not key:
            continue
        buckets[key]["daily_words"] += _word_count(row.get("user_message"))
        mood_score = _mood_score(row.get("mood"))
        if mood_score:
            buckets[key]["mood_values"].append(mood_score)
    for row in dream_rows:
        key = _date_key(row.get("entry_date"))
        if not key:
            continue
        buckets[key]["dream_words"] += _word_count(
            " ".join(str(row.get(field) or "") for field in ("plot", "summary", "interpretation"))
        )
        mood_score = _mood_score(row.get("mood"))
        if mood_score:
            buckets[key]["mood_values"].append(mood_score)
    for row in cbt_rows:
        key = _date_key(row.get("record_date"))
        if key:
            buckets[key]["thought_records"] += 1

    if selected_range == "all":
        keys = sorted(buckets.keys())
    else:
        start = start_date or today
        keys = [(start + timedelta(days=offset)).isoformat() for offset in range((today - start).days + 1)]

    return [_serialise_series_day(key, buckets[key]) for key in keys]


def _serialise_series_day(key: str, bucket: dict[str, Any]) -> dict[str, Any]:
    mood_values = bucket["mood_values"]
    mood_score = round(sum(mood_values) / len(mood_values), 2) if mood_values else None
    return {
        "date": key,
        "daily_words": bucket["daily_words"],
        "dream_words": bucket["dream_words"],
        "thought_records": bucket["thought_records"],
        "mood_score": mood_score,
        "sentiment_score": mood_score,
    }


def _build_streak(
    settings: dict[str, Any],
    today: date,
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
    cbt_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    included_types = _included_entry_types(settings)
    date_keys = []
    if "daily" in included_types:
        date_keys.extend(_date_key(row.get("entry_date")) for row in daily_rows)
    if "dream" in included_types:
        date_keys.extend(_date_key(row.get("entry_date")) for row in dream_rows)
    if "thought_record" in included_types:
        date_keys.extend(_date_key(row.get("record_date")) for row in cbt_rows)
    unique_dates = sorted({key for key in date_keys if key})
    weekly_goal = min(max(_safe_int(settings.get("writing_rhythm_weekly_goal"), 4), 1), 21)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    week_count = sum(1 for key in date_keys if key and key >= week_start.isoformat())
    month_count = sum(1 for key in date_keys if key and key >= month_start.isoformat())
    return {
        "current_days": _current_streak_days(unique_dates, today),
        "best_days": _best_streak_days(unique_dates),
        "weekly_goal": weekly_goal,
        "week_count": week_count,
        "month_count": month_count,
        "weekly_progress": min(round((week_count / weekly_goal) * 100), 100),
        "included_entry_types": included_types,
    }


def _included_entry_types(settings: dict[str, Any]) -> list[str]:
    selected = str(settings.get("writing_reminder_entry_types") or "daily,dream")
    values = [
        item.strip().lower().replace("-", "_")
        for item in selected.split(",")
        if item.strip()
    ]
    allowed = [item for item in values if item in {"daily", "dream", "thought_record"}]
    return allowed or ["daily", "dream"]


def _current_streak_days(unique_dates: list[str], today: date) -> int:
    active_dates = set(unique_dates)
    cursor = today
    if today.isoformat() not in active_dates:
        cursor = today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _best_streak_days(unique_dates: list[str]) -> int:
    best = 0
    current = 0
    previous: date | None = None
    for key in unique_dates:
        current_date = date.fromisoformat(key)
        if previous and (current_date - previous).days == 1:
            current += 1
        else:
            current = 1
        best = max(best, current)
        previous = current_date
    return best


def _build_themes(
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in daily_rows:
        _count_csv_values(counts, row.get("tags"), "tag")
        _count_csv_values(counts, row.get("daily_people_names"), "person")
        _count_csv_values(counts, row.get("daily_places"), "place")
    for row in dream_rows:
        _count_csv_values(counts, row.get("tags"), "tag")
        _count_csv_values(counts, row.get("dream_people_names"), "person")
        _count_csv_values(counts, row.get("dream_places"), "place")
        _count_csv_values(counts, row.get("symbols_and_imagery"), "dream_symbol")
    return _merged_theme_count_items(counts, 18)


def _filter_rows_by_theme(
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
    theme_label: str,
    theme_kind: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not theme_label or theme_kind not in {
        "tag",
        "person",
        "place",
        "dream_symbol",
    }:
        return daily_rows, dream_rows
    label = theme_label.strip().casefold()
    return (
        [
            row
            for row in daily_rows
            if _row_has_theme(row, theme_kind, label, "daily")
            or _row_has_any_theme(row, label, "daily")
        ],
        [
            row
            for row in dream_rows
            if _row_has_theme(row, theme_kind, label, "dream")
            or _row_has_any_theme(row, label, "dream")
        ],
    )


def _row_has_theme(row: dict[str, Any], kind: str, label: str, mode: str) -> bool:
    field_map = {
        ("daily", "tag"): "tags",
        ("daily", "person"): "daily_people_names",
        ("daily", "place"): "daily_places",
        ("dream", "tag"): "tags",
        ("dream", "person"): "dream_people_names",
        ("dream", "place"): "dream_places",
        ("dream", "dream_symbol"): "symbols_and_imagery",
    }
    field = field_map.get((mode, kind))
    if not field:
        return False
    return any(value.casefold() == label for value in _split_values(row.get(field)))


def _row_has_any_theme(row: dict[str, Any], label: str, mode: str) -> bool:
    fields = ["tags"]
    if mode == "daily":
        fields.extend(["daily_people_names", "daily_places"])
    else:
        fields.extend(["dream_people_names", "dream_places", "symbols_and_imagery"])
    return any(
        value.casefold() == label
        for field in fields
        for value in _split_values(row.get(field))
    )


def _count_csv_values(counts: Counter[tuple[str, str]], raw: object, kind: str) -> None:
    for value in re.split(r"[,;\n]+", str(raw or "")):
        cleaned = value.strip()
        if cleaned:
            counts[(kind, cleaned.casefold())] += 1


def _build_cbt_summary(cbt_rows: list[dict[str, Any]]) -> dict[str, Any]:
    before_values = []
    after_values = []
    pattern_counts: Counter[str] = Counter()
    reflections = []
    for row in cbt_rows:
        before_values.extend(_feeling_intensities(row.get("feelings_before_json")))
        after_values.extend(_feeling_intensities(row.get("feelings_after_json")))
        thought_text = str(row.get("unhelpful_thoughts") or "").lower()
        for label, keywords in CBT_PATTERN_KEYWORDS.items():
            if any(keyword in thought_text for keyword in keywords):
                pattern_counts[label] += 1
        if row.get("balanced_thought") or row.get("situation"):
            reflections.append({
                "id": row.get("id"),
                "title": row.get("title") or "Thought record",
                "date": _date_key(row.get("record_date")),
                "situation": _truncate(row.get("situation"), 120),
                "balanced_thought": _truncate(row.get("balanced_thought"), 160),
            })
    before_average = _average(before_values)
    after_average = _average(after_values)
    return {
        "total_records": len(cbt_rows),
        "common_patterns": [
            {"label": label, "count": count}
            for label, count in pattern_counts.most_common(5)
        ],
        "average_before": before_average,
        "average_after": after_average,
        "average_change": (
            round(after_average - before_average, 2)
            if before_average is not None and after_average is not None
            else None
        ),
        "recent_reflections": reflections[:3],
    }


def _build_recent_activity(
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
    cbt_rows: list[dict[str, Any]],
    important_day_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for row in daily_rows[:6]:
        records.append({
            "type": "daily",
            "id": row.get("id"),
            "title": row.get("title") or "Diary entry",
            "date": _date_key(row.get("entry_date")),
            "summary": _truncate(row.get("user_message"), 140),
            "route": f"/entries/{row.get('id')}",
        })
    for row in dream_rows[:6]:
        records.append({
            "type": "dream",
            "id": row.get("id"),
            "title": row.get("title") or "Dream entry",
            "date": _date_key(row.get("entry_date")),
            "summary": _truncate(row.get("plot") or row.get("summary"), 140),
            "route": f"/entries/{row.get('id')}?type=dream",
        })
    for row in cbt_rows[:6]:
        records.append({
            "type": "thought_record",
            "id": row.get("id"),
            "title": row.get("title") or "Thought record",
            "date": _date_key(row.get("record_date")),
            "summary": _truncate(row.get("balanced_thought") or row.get("situation"), 140),
            "route": f"/cbt/{row.get('id')}",
        })
    for row in important_day_rows[:4]:
        records.append({
            "type": "important_day",
            "id": row.get("id"),
            "title": row.get("label") or "Important day",
            "date": row.get("starts_on") or _month_day_label(row.get("month"), row.get("day")),
            "summary": _truncate(row.get("note") or row.get("category"), 140),
            "route": "/important-days",
        })
    return sorted(
        records,
        key=lambda item: str(item.get("date") or ""),
        reverse=True,
    )[:8]


def _group_recent_activity(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {
        "daily": [],
        "dream": [],
        "thought_record": [],
        "important_day": [],
    }
    for record in records:
        record_type = str(record.get("type") or "")
        if record_type in grouped and len(grouped[record_type]) < 3:
            grouped[record_type].append(record)
    return grouped


def _build_dream_insights(dream_rows: list[dict[str, Any]]) -> dict[str, Any]:
    symbol_counts: Counter[str] = Counter()
    people_counts: Counter[str] = Counter()
    place_counts: Counter[str] = Counter()
    recent_pattern_counts: Counter[tuple[str, str]] = Counter()
    for row in dream_rows:
        for value in _split_values(row.get("symbols_and_imagery")):
            symbol_counts[value.casefold()] += 1
        for value in _split_values(row.get("dream_people_names")):
            people_counts[value.casefold()] += 1
        for value in _split_values(row.get("dream_places")):
            place_counts[value.casefold()] += 1

    recent_dreams = []
    for row in dream_rows[:3]:
        for key in _row_theme_keys(row, "dream"):
            recent_pattern_counts[key] += 1
        recent_dreams.append({
            "id": row.get("id"),
            "title": row.get("title") or "Dream entry",
            "date": _date_key(row.get("entry_date")),
            "summary": _truncate(
                row.get("interpretation") or row.get("summary") or row.get("plot"),
                180,
            ),
            "image_url": _resolve_dashboard_image(row),
            "route": f"/entries/{row.get('id')}?type=dream",
            "symbols": [
                _display_theme_label(value.casefold(), "dream_symbol")
                for value in _split_values(row.get("symbols_and_imagery"))[:4]
            ],
            "people": [
                _display_theme_label(value.casefold(), "person")
                for value in _split_values(row.get("dream_people_names"))[:3]
            ],
            "places": [
                _display_theme_label(value.casefold(), "place")
                for value in _split_values(row.get("dream_places"))[:3]
            ],
        })

    latest = dream_rows[0] if dream_rows else None
    latest_payload = None
    if latest:
        latest_payload = {
            "id": latest.get("id"),
            "title": latest.get("title") or "Dream entry",
            "date": _date_key(latest.get("entry_date")),
            "summary": _truncate(
                latest.get("interpretation") or latest.get("summary") or latest.get("plot"),
                220,
            ),
            "image_url": _resolve_dashboard_image(latest),
            "route": f"/entries/{latest.get('id')}?type=dream",
        }

    return {
        "total_dreams": len(dream_rows),
        "top_symbols": _counter_items(symbol_counts, 8, "dream_symbol"),
        "top_people": _counter_items(people_counts, 6, "person"),
        "top_places": _counter_items(place_counts, 6, "place"),
        "recent": recent_dreams,
        "recent_repeating_patterns": [
            item
            for item in _merged_theme_count_items(recent_pattern_counts, 8)
            if item["count"] > 1
        ],
        "latest": latest_payload,
    }


def _build_focus_sections(
    today: date,
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
    important_day_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "memory_echo": _build_memory_echo(today, daily_rows, dream_rows),
        "theme_drift": _build_theme_drift(today, daily_rows, dream_rows),
        "mood_anchors": _build_mood_anchors(daily_rows, dream_rows),
        "important_day_cues": _build_important_day_cues(today, important_day_rows),
    }


def _build_memory_echo(
    today: date,
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in daily_rows:
        entry_date = _parse_date(row.get("entry_date"))
        if not entry_date or entry_date.year >= today.year:
            continue
        if _month_day_distance(today, entry_date) <= 10:
            items.append({
                "type": "daily",
                "id": row.get("id"),
                "title": row.get("title") or "Diary entry",
                "date": entry_date.isoformat(),
                "summary": _truncate(row.get("user_message"), 130),
                "route": f"/entries/{row.get('id')}",
            })
    for row in dream_rows:
        entry_date = _parse_date(row.get("entry_date"))
        if not entry_date or entry_date.year >= today.year:
            continue
        if _month_day_distance(today, entry_date) <= 10:
            items.append({
                "type": "dream",
                "id": row.get("id"),
                "title": row.get("title") or "Dream entry",
                "date": entry_date.isoformat(),
                "summary": _truncate(row.get("summary") or row.get("interpretation") or row.get("plot"), 130),
                "route": f"/entries/{row.get('id')}?type=dream",
            })
    items = sorted(items, key=lambda item: str(item.get("date") or ""), reverse=True)[:4]
    return {
        "label": "This time in previous years",
        "count": len(items),
        "items": items,
    }


def _build_theme_drift(
    today: date,
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current_start = today - timedelta(days=29)
    previous_start = today - timedelta(days=59)
    previous_end = current_start - timedelta(days=1)
    current_counts: Counter[tuple[str, str]] = Counter()
    previous_counts: Counter[tuple[str, str]] = Counter()

    for row, mode in [(row, "daily") for row in daily_rows] + [(row, "dream") for row in dream_rows]:
        entry_date = _parse_date(row.get("entry_date"))
        if not entry_date:
            continue
        target = None
        if current_start <= entry_date <= today:
            target = current_counts
        elif previous_start <= entry_date <= previous_end:
            target = previous_counts
        if target is None:
            continue
        for label, kind in _row_theme_label_kinds(row, mode).items():
            target[(kind, label)] += 1

    keys = set(current_counts) | set(previous_counts)
    merged_drift: dict[str, dict[str, Any]] = {}
    for kind, label in keys:
        current_count = current_counts[(kind, label)]
        previous_count = previous_counts[(kind, label)]
        change = current_count - previous_count
        if current_count == 0 and change <= 0:
            continue
        bucket = merged_drift.setdefault(label, {
            "label": label,
            "kind": kind,
            "current_count": 0,
            "previous_count": 0,
            "change": 0,
        })
        if _theme_kind_priority(kind) > _theme_kind_priority(str(bucket["kind"])):
            bucket["kind"] = kind
        bucket["current_count"] += current_count
        bucket["previous_count"] += previous_count
        bucket["change"] += change
    drift = [
        {
            **item,
            "label": _display_theme_label(str(item["label"]), str(item["kind"])),
        }
        for item in merged_drift.values()
    ]
    return sorted(
        drift,
        key=lambda item: (abs(int(item["change"])), int(item["current_count"])),
        reverse=True,
    )[:4]


def _build_mood_anchors(
    daily_rows: list[dict[str, Any]],
    dream_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    anchors: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row, mode in [(row, "daily") for row in daily_rows] + [(row, "dream") for row in dream_rows]:
        mood_score = _mood_score(row.get("mood"))
        if not mood_score:
            continue
        for label, kind in _row_theme_label_kinds(row, mode).items():
            anchors[(kind, label)].append(mood_score)

    merged_anchors: dict[str, dict[str, Any]] = {}
    for (kind, label), values in anchors.items():
        if len(values) < 2:
            continue
        bucket = merged_anchors.setdefault(label, {"kind": kind, "values": []})
        if _theme_kind_priority(kind) > _theme_kind_priority(str(bucket["kind"])):
            bucket["kind"] = kind
        bucket["values"].extend(values)
    results = []
    for label, bucket in merged_anchors.items():
        values = bucket["values"]
        if len(values) < 2:
            continue
        kind = str(bucket["kind"])
        results.append({
            "label": _display_theme_label(label, kind),
            "kind": kind,
            "average_mood": round(sum(values) / len(values), 2),
            "count": len(values),
        })
    return sorted(
        results,
        key=lambda item: (
            int(item["count"]),
            abs(float(item["average_mood"]) - 3),
            float(item["average_mood"]),
        ),
        reverse=True,
    )[:4]


def _build_important_day_cues(
    today: date,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    cues = []
    for row in rows:
        next_date = _next_important_day_date(today, row)
        if not next_date:
            continue
        cues.append({
            "id": row.get("id"),
            "label": row.get("label") or "Important day",
            "date": next_date.isoformat(),
            "category": row.get("category") or "Other",
            "note": _truncate(row.get("note"), 120),
            "icon_name": row.get("icon_name") or "event",
            "accent_color": row.get("accent_color") or "blue",
            "days_until": (next_date - today).days,
            "route": "/important-days",
        })
    return sorted(cues, key=lambda item: int(item.get("days_until") or 0))[:4]


def _count_row_theme_values(
    counts: Counter[tuple[str, str]],
    row: dict[str, Any],
    mode: str,
) -> None:
    _count_csv_values(counts, row.get("tags"), "tag")
    if mode == "daily":
        _count_csv_values(counts, row.get("daily_people_names"), "person")
        _count_csv_values(counts, row.get("daily_places"), "place")
    else:
        _count_csv_values(counts, row.get("dream_people_names"), "person")
        _count_csv_values(counts, row.get("dream_places"), "place")
        _count_csv_values(counts, row.get("symbols_and_imagery"), "dream_symbol")


def _row_theme_keys(row: dict[str, Any], mode: str) -> set[tuple[str, str]]:
    return {
        (kind, label)
        for label, kind in _row_theme_label_kinds(row, mode).items()
    }


def _row_theme_label_kinds(row: dict[str, Any], mode: str) -> dict[str, str]:
    counts: Counter[tuple[str, str]] = Counter()
    _count_row_theme_values(counts, row, mode)
    labels: dict[str, str] = {}
    for kind, label in counts:
        current_kind = labels.get(label)
        if current_kind is None or _theme_kind_priority(kind) > _theme_kind_priority(current_kind):
            labels[label] = kind
    return labels


def _counter_items(counter: Counter[str], limit: int, kind: str) -> list[dict[str, Any]]:
    return [
        {"label": _display_theme_label(label, kind), "count": count, "kind": kind}
        for label, count in counter.most_common(limit)
    ]


def _merged_theme_count_items(
    counts: Counter[tuple[str, str]],
    limit: int,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for (kind, label), count in counts.items():
        bucket = merged.setdefault(label, {"label": label, "kind": kind, "count": 0})
        if _theme_kind_priority(kind) > _theme_kind_priority(str(bucket["kind"])):
            bucket["kind"] = kind
        bucket["count"] += count
    items = [
        {
            "label": _display_theme_label(str(item["label"]), str(item["kind"])),
            "count": int(item["count"]),
            "kind": str(item["kind"]),
        }
        for item in merged.values()
    ]
    return sorted(items, key=lambda item: int(item["count"]), reverse=True)[:limit]


def _theme_kind_priority(kind: str) -> int:
    priorities = {
        "person": 4,
        "place": 3,
        "dream_symbol": 2,
        "tag": 1,
    }
    return priorities.get(kind, 0)


def _split_values(raw: object) -> list[str]:
    return [
        value.strip()
        for value in re.split(r"[,;\n]+", str(raw or ""))
        if value.strip()
    ]


def _display_theme_label(label: str, kind: str) -> str:
    cleaned = " ".join(str(label or "").split())
    if kind in {"person", "place"}:
        return cleaned.title()
    return cleaned


def _resolve_dashboard_image(row: dict[str, Any]) -> str | None:
    storage_key = str(row.get("image_storage_key") or "").strip()
    if storage_key:
        return resolve_image_url(storage_key)
    image_url = str(row.get("image_url") or "").strip()
    return image_url or None


def _feeling_intensities(raw: object) -> list[int]:
    try:
        parsed = json.loads(str(raw or "[]"))
    except json.JSONDecodeError:
        return []
    values = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                intensity = _safe_int(item.get("intensity"), -1)
                if 0 <= intensity <= 100:
                    values.append(intensity)
    return values


def _average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _mood_score(raw: object) -> int | None:
    mood = str(raw or "").strip().lower()
    if not mood:
        return None
    return MOOD_SCORES.get(mood)


def _word_count(raw: object) -> int:
    return len(WORD_RE.findall(str(raw or "")))


def _date_key(raw: object) -> str | None:
    value = str(raw or "")[:10]
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _parse_date(raw: object) -> date | None:
    value = str(raw or "")[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _month_day_distance(anchor: date, candidate: date) -> int:
    try:
        normalised = date(anchor.year, candidate.month, candidate.day)
    except ValueError:
        normalised = date(anchor.year, 2, 28)
    return abs((normalised - anchor).days)


def _next_important_day_date(today: date, row: dict[str, Any]) -> date | None:
    starts_on = _parse_date(row.get("starts_on"))
    if not starts_on:
        month = _safe_int(row.get("month"), 0)
        day = _safe_int(row.get("day"), 0)
        try:
            starts_on = date(today.year, month, day)
        except ValueError:
            return None
    recurrence = str(row.get("recurrence") or "yearly").lower()
    if recurrence in {"none", "once", "one-off", "one_off"}:
        return starts_on if starts_on >= today else None
    try:
        upcoming = date(today.year, starts_on.month, starts_on.day)
    except ValueError:
        upcoming = date(today.year, 2, 28)
    if upcoming < today:
        try:
            upcoming = date(today.year + 1, starts_on.month, starts_on.day)
        except ValueError:
            upcoming = date(today.year + 1, 2, 28)
    return upcoming


def _month_day_label(month: object, day: object) -> str:
    return f"{_safe_int(day, 1):02d}/{_safe_int(month, 1):02d}"


def _truncate(raw: object, max_length: int) -> str:
    text = " ".join(str(raw or "").split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _safe_int(raw: object, fallback: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def _row_to_dict(row: object) -> dict[str, Any]:
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)
