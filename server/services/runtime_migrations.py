"""Runtime database schema migrations for compatibility across deployed DBs."""

from __future__ import annotations

import sqlite3
from typing import Callable


_TARGET_COLUMNS: dict[str, dict[str, str]] = {
    'dailydiary_entries': {
        'import_id': 'INTEGER',
        'entry_time': 'TEXT',
        'mood': 'TEXT',
        'ai_style': 'TEXT',
        'ai_response': 'TEXT',
        'image_prompt': 'TEXT',
        'image_url': 'TEXT',
        'image_storage_key': 'TEXT',
        'image_source': 'TEXT',
        'recycled_image_prompt': 'TEXT',
        'image_position_x': 'REAL DEFAULT 50',
        'image_position_y': 'REAL DEFAULT 50',
        'analysis_attachment_refs': 'TEXT',
    },
    'dreamdiary_entries': {
        'import_id': 'INTEGER',
        'entry_time': 'TEXT',
        'mood': 'TEXT',
        'ai_style': 'TEXT',
        'summary': 'TEXT',
        'interpretation': 'TEXT',
        'image_prompt': 'TEXT',
        'image_url': 'TEXT',
        'image_storage_key': 'TEXT',
        'image_source': 'TEXT',
        'recycled_image_prompt': 'TEXT',
        'image_position_x': 'REAL DEFAULT 50',
        'image_position_y': 'REAL DEFAULT 50',
        'analysis_attachment_refs': 'TEXT',
    },
}

_ENTRY_LIST_INDEXES: dict[str, dict[str, str]] = {
    'dailydiary_entries': {
        'index_name': 'idx_daily_entries_user_list_order',
        'entry_time_fallback': '19:00',
    },
    'dreamdiary_entries': {
        'index_name': 'idx_dream_entries_user_list_order',
        'entry_time_fallback': '08:00',
    },
}

_USER_SETTINGS_COLUMNS: dict[str, str] = {
    'email': 'TEXT',
    'email_verified': 'INTEGER DEFAULT 0',
    'registered_at': 'TEXT',
    'profile_picture_storage_key': 'TEXT',
    'display_name': 'TEXT',
    'pronouns': 'TEXT',
    'gender': 'TEXT',
    'custom_guidance': 'TEXT',
    'timezone': "TEXT DEFAULT 'UTC'",
    'holiday_country_code': 'TEXT',
    'show_public_holidays': 'INTEGER DEFAULT 0',
    'show_on_this_day': 'INTEGER DEFAULT 0',
    'ai_tone': "TEXT DEFAULT 'friendly'",
    'ai_verbosity': "TEXT DEFAULT 'balanced'",
    'ai_focus': "TEXT DEFAULT 'reflective'",
    'ai_model': "TEXT DEFAULT 'gpt-4.1-mini'",
    'allow_ai_history': 'INTEGER DEFAULT 1',
    'allow_ai_attachment_context': 'INTEGER DEFAULT 0',
    'writing_reminders_enabled': 'INTEGER DEFAULT 0',
    'writing_reminder_days': 'TEXT',
    'writing_reminder_time': "TEXT DEFAULT '19:00'",
    'writing_reminder_silence_days': 'INTEGER DEFAULT 3',
    'writing_reminder_entry_types': "TEXT DEFAULT 'daily,dream'",
    'writing_rhythm_progress_enabled': 'INTEGER DEFAULT 0',
    'writing_rhythm_weekly_goal': 'INTEGER DEFAULT 4',
    'chat_enabled': 'INTEGER DEFAULT 1',
    'password_auth_enabled': 'INTEGER DEFAULT 1',
    'onboarding_completed': 'INTEGER DEFAULT 1',
}

_AUTH_IDENTITIES_DDL = """
CREATE TABLE IF NOT EXISTS auth_identities (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    provider            TEXT NOT NULL,
    provider_subject    TEXT NOT NULL,
    email               TEXT,
    email_verified      INTEGER NOT NULL DEFAULT 0,
    display_name        TEXT,
    profile_picture_url TEXT,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(provider, provider_subject)
)
"""

_ACCOUNT_SECURITY_TOKENS_DDL = """
CREATE TABLE IF NOT EXISTS account_security_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    purpose     TEXT NOT NULL CHECK(purpose IN ('email_verification', 'password_reset')),
    token_hash  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    consumed_at TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(purpose, token_hash)
)
"""

_BILLING_CUSTOMERS_DDL = """
CREATE TABLE IF NOT EXISTS billing_customers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    provider            TEXT NOT NULL DEFAULT 'stripe'
                        CHECK(provider IN ('stripe')),
    provider_customer_id TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(provider, provider_customer_id),
    UNIQUE(user_id, provider)
)
"""

_SUBSCRIPTIONS_DDL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                  INTEGER NOT NULL,
    provider                 TEXT NOT NULL DEFAULT 'stripe'
                             CHECK(provider IN ('stripe', 'manual')),
    provider_subscription_id TEXT,
    tier                     TEXT NOT NULL DEFAULT 'free',
    status                   TEXT NOT NULL DEFAULT 'inactive',
    current_period_start     TEXT,
    current_period_end       TEXT,
    cancel_at_period_end     INTEGER NOT NULL DEFAULT 0
                             CHECK(cancel_at_period_end IN (0, 1)),
    created_at               TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(provider, provider_subscription_id)
)
"""

_ENTITLEMENTS_DDL = """
CREATE TABLE IF NOT EXISTS entitlements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    tier        TEXT NOT NULL DEFAULT 'free'
                CHECK(tier IN ('free', 'personal', 'plus', 'therapeutic', 'lifetime', 'complimentary', 'administrator')),
    source      TEXT NOT NULL DEFAULT 'system'
                CHECK(source IN ('system', 'stripe', 'manual')),
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'inactive', 'past_due', 'cancelled', 'expired')),
    valid_until TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id)
)
"""

_BILLING_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS billing_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    provider          TEXT NOT NULL DEFAULT 'stripe'
                      CHECK(provider IN ('stripe', 'manual')),
    provider_event_id TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    user_id           INTEGER,
    processed_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json     TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(provider, provider_event_id)
)
"""

_USAGE_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS usage_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    event_type    TEXT NOT NULL,
    units         INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

_EXPORT_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS export_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL,
    exported_at           TEXT    NOT NULL,
    filename              TEXT    NOT NULL,
    from_date             TEXT,
    to_date               TEXT,
    include_daily         INTEGER NOT NULL DEFAULT 1,
    include_dreams        INTEGER NOT NULL DEFAULT 1,
    daily_count           INTEGER NOT NULL DEFAULT 0,
    dream_count           INTEGER NOT NULL DEFAULT 0,
    is_full_range         INTEGER NOT NULL DEFAULT 0,
    guard_token           TEXT,
    used_for_bulk_delete  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

_IMPORT_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS import_sessions (
    id              TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    created_at      TEXT NOT NULL,
    filename        TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    payload_json    TEXT NOT NULL,
    consumed_at     TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

_IMPORT_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS import_jobs (
    id                TEXT PRIMARY KEY,
    user_id           INTEGER NOT NULL,
    import_session_id TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'queued',
    processed         INTEGER NOT NULL DEFAULT 0,
    total             INTEGER NOT NULL DEFAULT 0,
    percent           INTEGER NOT NULL DEFAULT 0,
    message           TEXT NOT NULL DEFAULT '',
    error             TEXT,
    request_json      TEXT NOT NULL DEFAULT '{}',
    result_json       TEXT,
    import_id         INTEGER,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    started_at        TEXT,
    completed_at      TEXT,
    attempt_count     INTEGER NOT NULL DEFAULT 0,
    worker_token      TEXT,
    lease_expires_at  TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

_ENTRY_ASSETS_DDL = """
CREATE TABLE IF NOT EXISTS entry_assets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    entry_type        TEXT NOT NULL,
    entry_id          INTEGER NOT NULL,
    asset_role        TEXT NOT NULL DEFAULT 'attachment',
    storage_key       TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type         TEXT NOT NULL,
    file_size_bytes   INTEGER NOT NULL DEFAULT 0,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

_ENTRY_ASSET_COLUMNS: dict[str, str] = {
    'derived_text': 'TEXT',
    'derived_text_source': 'TEXT',
    'derived_text_updated_at': 'TEXT',
}

_IMPORTANT_DAYS_DDL = """
CREATE TABLE IF NOT EXISTS important_days (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    label         TEXT NOT NULL,
    starts_on     TEXT,
    month         INTEGER NOT NULL,
    day           INTEGER NOT NULL,
    original_year INTEGER,
    category      TEXT NOT NULL DEFAULT 'other',
    recurrence    TEXT NOT NULL DEFAULT 'yearly',
    icon_name     TEXT NOT NULL DEFAULT 'event',
    accent_color  TEXT NOT NULL DEFAULT 'amber',
    ends_on       TEXT,
    linked_entry_refs TEXT,
    image_url     TEXT,
    image_storage_key TEXT,
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

_IMPORTANT_DAY_COLUMNS: dict[str, str] = {
    'starts_on': 'TEXT',
    'recurrence': "TEXT NOT NULL DEFAULT 'yearly'",
    'icon_name': "TEXT NOT NULL DEFAULT 'event'",
    'accent_color': "TEXT NOT NULL DEFAULT 'amber'",
    'ends_on': 'TEXT',
    'linked_entry_refs': 'TEXT',
    'image_url': 'TEXT',
    'image_storage_key': 'TEXT',
}

_PUBLIC_HOLIDAY_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS public_holiday_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code  TEXT NOT NULL,
    holiday_year  INTEGER NOT NULL,
    payload_json  TEXT NOT NULL,
    fetched_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, holiday_year)
)
"""

_ENTRY_RESURFACING_PREFERENCES_DDL = """
CREATE TABLE IF NOT EXISTS entry_resurfacing_preferences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    entry_type TEXT NOT NULL
               CHECK(entry_type IN ('daily', 'dream', 'thought_record')),
    entry_id   INTEGER NOT NULL,
    hidden_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, entry_type, entry_id)
)
"""

_REFLECTION_SUMMARIES_DDL = """
CREATE TABLE IF NOT EXISTS reflection_summaries (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    period_type        TEXT NOT NULL CHECK(period_type IN ('weekly', 'monthly')),
    period_start       TEXT NOT NULL,
    period_end         TEXT NOT NULL,
    title              TEXT NOT NULL,
    summary_text       TEXT NOT NULL,
    themes_json        TEXT NOT NULL DEFAULT '[]',
    source_refs_json   TEXT NOT NULL DEFAULT '[]',
    model              TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, period_type, period_start)
)
"""

_CHAT_MESSAGES_DDL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    conversation_id TEXT NOT NULL,
    request_id      TEXT,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    token_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

_CHAT_OBSERVABILITY_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS chat_observability_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    conversation_id TEXT,
    request_id      TEXT,
    event_type      TEXT NOT NULL,
    error_code      TEXT,
    latency_ms      INTEGER,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    model           TEXT,
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

_SECURITY_AUDIT_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS security_audit_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,
    event_type      TEXT NOT NULL,
    outcome         TEXT NOT NULL DEFAULT 'success',
    ip_hash         TEXT,
    user_agent_hash TEXT,
    metadata_json   TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

_CBT_WORKSHEETS_DDL = """
CREATE TABLE IF NOT EXISTS cbt_worksheets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    worksheet_type    TEXT NOT NULL DEFAULT 'thought_record',
    title             TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK(status IN ('draft', 'completed')),
    current_step      INTEGER NOT NULL DEFAULT 1 CHECK(current_step BETWEEN 1 AND 7),
    record_date       TEXT NOT NULL DEFAULT CURRENT_DATE,
    linked_entry_type TEXT CHECK(linked_entry_type IN ('daily', 'dream')),
    linked_entry_id   INTEGER,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at      TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK(
        (linked_entry_type IS NULL AND linked_entry_id IS NULL) OR
        (linked_entry_type IS NOT NULL AND linked_entry_id IS NOT NULL)
    )
)
"""

_CBT_THOUGHT_RECORD_DATA_DDL = """
CREATE TABLE IF NOT EXISTS cbt_thought_record_data (
    worksheet_id         INTEGER PRIMARY KEY,
    situation            TEXT NOT NULL DEFAULT '',
    feelings_before_json TEXT NOT NULL DEFAULT '[]',
    unhelpful_thoughts   TEXT NOT NULL DEFAULT '',
    evidence_for         TEXT NOT NULL DEFAULT '',
    evidence_against     TEXT NOT NULL DEFAULT '',
    balanced_thought     TEXT NOT NULL DEFAULT '',
    feelings_after_json  TEXT NOT NULL DEFAULT '[]',
    next_step            TEXT NOT NULL DEFAULT '',
    ai_response          TEXT NOT NULL DEFAULT '',
    ai_responded_at      TEXT,
    ai_response_outdated INTEGER NOT NULL DEFAULT 0
                         CHECK(ai_response_outdated IN (0, 1)),
    FOREIGN KEY (worksheet_id) REFERENCES cbt_worksheets(id) ON DELETE CASCADE
)
"""

_CBT_THOUGHT_RECORD_DATA_COLUMNS: dict[str, str] = {
    'ai_response': "TEXT NOT NULL DEFAULT ''",
    'ai_responded_at': 'TEXT',
    'ai_response_outdated': 'INTEGER NOT NULL DEFAULT 0 CHECK(ai_response_outdated IN (0, 1))',
}


def ensure_entry_mood_style_columns(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> int:
    """Ensure runtime diary tables include compatibility columns.

    Returns the number of columns added across all target tables.
    Safe to run repeatedly (idempotent).
    """
    added_columns = 0

    with sqlite3.connect(database_path, timeout=10) as conn:
        cursor = conn.cursor()

        for table_name, required_columns in _TARGET_COLUMNS.items():
            table_exists = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if not table_exists:
                if log:
                    log('Runtime migration skipped missing table: %s', table_name)
                continue

            table_columns = {
                row[1]
                for row in cursor.execute(f'PRAGMA table_info({table_name})').fetchall()
            }

            for column_name, column_definition in required_columns.items():
                if column_name in table_columns:
                    continue
                cursor.execute(
                    f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}'
                )
                added_columns += 1
                table_columns.add(column_name)
                if log:
                    log('Runtime migration added column %s.%s', table_name, column_name)

            index_config = _ENTRY_LIST_INDEXES.get(table_name)
            index_columns = {'user_id', 'entry_date', 'entry_time', 'entry_number', 'id'}
            if index_config and index_columns.issubset(table_columns):
                cursor.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {index_config['index_name']}
                    ON {table_name}(
                        user_id,
                        entry_date DESC,
                        COALESCE(entry_time, '{index_config['entry_time_fallback']}') DESC,
                        entry_number DESC,
                        id DESC
                    )
                    """
                )

    return added_columns


def ensure_entry_ai_metadata_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime metadata table exists for AI context headers.

    Returns True when creation check is executed successfully.
    Safe to run repeatedly (idempotent).
    """
    with sqlite3.connect(database_path, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entry_ai_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                reference_date DATE,
                summary_header TEXT,
                tags TEXT,
                people_names TEXT,
                places TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'entry_ai_metadata')

    return True


def ensure_user_settings_columns(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> int:
    """Ensure runtime users table includes settings and personalisation columns."""
    added_columns = 0

    with sqlite3.connect(database_path, timeout=10) as conn:
        cursor = conn.cursor()

        table_exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ('users',),
        ).fetchone()
        if not table_exists:
            if log:
                log('Runtime migration skipped missing table: %s', 'users')
            return 0

        table_columns = {
            row[1]
            for row in cursor.execute('PRAGMA table_info(users)').fetchall()
        }

        for column_name, column_definition in _USER_SETTINGS_COLUMNS.items():
            if column_name in table_columns:
                continue
            cursor.execute(
                f'ALTER TABLE users ADD COLUMN {column_name} {column_definition}'
            )
            added_columns += 1
            if log:
                log('Runtime migration added column %s.%s', 'users', column_name)

        refreshed_columns = table_columns | set(_USER_SETTINGS_COLUMNS)
        if 'registered_at' in refreshed_columns:
            cursor.execute(
                """
                UPDATE users
                SET registered_at = CURRENT_TIMESTAMP
                WHERE registered_at IS NULL OR registered_at = ''
                """
            )
        auth_identities_exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ('auth_identities',),
        ).fetchone()
        if (
            auth_identities_exists
            and 'password_auth_enabled' in refreshed_columns
            and 'onboarding_completed' in refreshed_columns
        ):
            cursor.execute(
                """
                UPDATE users
                SET password_auth_enabled = 0
                WHERE id IN (SELECT DISTINCT user_id FROM auth_identities)
                """
            )

    return added_columns


def ensure_auth_identities_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure future OAuth/OIDC identities can be linked to local accounts."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_AUTH_IDENTITIES_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_identities_user_provider
            ON auth_identities(user_id, provider)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'auth_identities')

    return True


def ensure_account_security_tokens_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure email verification and password-reset tokens can be stored."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_ACCOUNT_SECURITY_TOKENS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_account_security_tokens_user_purpose
            ON account_security_tokens(user_id, purpose, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_account_security_tokens_lookup
            ON account_security_tokens(purpose, token_hash, expires_at)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'account_security_tokens')

    return True


def ensure_billing_tables(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure billing and entitlement tables exist for SaaS feature gates."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_BILLING_CUSTOMERS_DDL)
        conn.execute(_SUBSCRIPTIONS_DDL)
        conn.execute(_ENTITLEMENTS_DDL)
        conn.execute(_BILLING_EVENTS_DDL)
        conn.execute(_USAGE_EVENTS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status
            ON subscriptions(user_id, status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_entitlements_tier_status
            ON entitlements(tier, status)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_billing_events_user_processed
            ON billing_events(user_id, processed_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_usage_events_user_type_created
            ON usage_events(user_id, event_type, created_at DESC)
            """
        )

    if log:
        log('Runtime migration ensured billing and usage tables exist')

    return True


def ensure_export_history_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime export-history table exists for guarded bulk delete."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_EXPORT_HISTORY_DDL)

    if log:
        log('Runtime migration ensured table exists: %s', 'export_history')

    return True


def ensure_import_sessions_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime staged import-sessions table exists for duplicate review."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_IMPORT_SESSIONS_DDL)

    if log:
        log('Runtime migration ensured table exists: %s', 'import_sessions')

    return True


def ensure_import_jobs_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure durable background import jobs survive process restarts."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_IMPORT_JOBS_DDL)
        columns = {
            row[1] for row in conn.execute('PRAGMA table_info(import_jobs)').fetchall()
        }
        if 'worker_token' not in columns:
            conn.execute('ALTER TABLE import_jobs ADD COLUMN worker_token TEXT')
        if 'lease_expires_at' not in columns:
            conn.execute('ALTER TABLE import_jobs ADD COLUMN lease_expires_at TEXT')
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_import_jobs_user_status
            ON import_jobs(user_id, status, updated_at)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'import_jobs')
    return True


def ensure_entry_assets_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime entry-assets table exists for non-hero attachments."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_ENTRY_ASSETS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_entry_assets_lookup
            ON entry_assets(user_id, entry_type, entry_id, sort_order, id)
            """
        )
        table_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(entry_assets)').fetchall()
        }
        for column_name, column_definition in _ENTRY_ASSET_COLUMNS.items():
            if column_name in table_columns:
                continue
            conn.execute(
                f'ALTER TABLE entry_assets ADD COLUMN {column_name} {column_definition}'
            )
            if log:
                log('Runtime migration added column %s.%s', 'entry_assets', column_name)

    if log:
        log('Runtime migration ensured table exists: %s', 'entry_assets')

    return True


def ensure_important_days_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime important-days table exists for user-managed recurring dates."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_IMPORTANT_DAYS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_important_days_user_lookup
            ON important_days(user_id, month, day)
            """
        )
        table_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(important_days)').fetchall()
        }
        for column_name, column_definition in _IMPORTANT_DAY_COLUMNS.items():
            if column_name in table_columns:
                continue
            conn.execute(
                f'ALTER TABLE important_days ADD COLUMN {column_name} {column_definition}'
            )
            if log:
                log('Runtime migration added column %s.%s', 'important_days', column_name)

    if log:
        log('Runtime migration ensured table exists: %s', 'important_days')

    return True


def ensure_public_holiday_cache_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime public-holiday cache table exists for provider responses."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_PUBLIC_HOLIDAY_CACHE_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_public_holiday_cache_lookup
            ON public_holiday_cache(country_code, holiday_year)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'public_holiday_cache')

    return True


def ensure_entry_resurfacing_preferences_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure per-user hidden-memory preferences are stored durably."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_ENTRY_RESURFACING_PREFERENCES_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_entry_resurfacing_user_lookup
            ON entry_resurfacing_preferences(user_id, entry_type, entry_id)
            """
        )

    if log:
        log(
            'Runtime migration ensured table exists: %s',
            'entry_resurfacing_preferences',
        )
    return True


def ensure_reflection_summaries_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure generated weekly/monthly reflection summaries are persisted."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_REFLECTION_SUMMARIES_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reflection_summaries_user_period
            ON reflection_summaries(user_id, period_type, period_start DESC)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'reflection_summaries')

    return True


def ensure_chat_messages_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure durable, user-scoped storage exists for chat conversations."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_CHAT_MESSAGES_DDL)
        columns = {
            row[1] for row in conn.execute('PRAGMA table_info(chat_messages)').fetchall()
        }
        if 'request_id' not in columns:
            conn.execute('ALTER TABLE chat_messages ADD COLUMN request_id TEXT')
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
            ON chat_messages(user_id, conversation_id, created_at, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created
            ON chat_messages(user_id, created_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_messages_request_role
            ON chat_messages(user_id, request_id, role)
            WHERE request_id IS NOT NULL
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'chat_messages')

    return True


def ensure_chat_observability_events_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure measurable chat lifecycle events can be reviewed after requests."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_CHAT_OBSERVABILITY_EVENTS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_observability_user_created
            ON chat_observability_events(user_id, created_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_observability_event_created
            ON chat_observability_events(event_type, created_at DESC)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'chat_observability_events')

    return True


def ensure_security_audit_events_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure durable security-event audit storage exists."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_SECURITY_AUDIT_EVENTS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_security_audit_user_created
            ON security_audit_events(user_id, created_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_security_audit_event_created
            ON security_audit_events(event_type, created_at DESC)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'security_audit_events')

    return True


def ensure_cbt_worksheet_tables(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure additive, user-scoped storage exists for structured CBT worksheets."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute(_CBT_WORKSHEETS_DDL)
        conn.execute(_CBT_THOUGHT_RECORD_DATA_DDL)
        worksheet_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(cbt_worksheets)').fetchall()
        }
        if 'record_date' not in worksheet_columns:
            conn.execute('ALTER TABLE cbt_worksheets ADD COLUMN record_date TEXT')
            if log:
                log('Runtime migration added column %s.%s', 'cbt_worksheets', 'record_date')
        data_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(cbt_thought_record_data)').fetchall()
        }
        for column_name, column_definition in _CBT_THOUGHT_RECORD_DATA_COLUMNS.items():
            if column_name in data_columns:
                continue
            conn.execute(
                f'ALTER TABLE cbt_thought_record_data ADD COLUMN {column_name} {column_definition}'
            )
            if log:
                log(
                    'Runtime migration added column %s.%s',
                    'cbt_thought_record_data',
                    column_name,
                )
        conn.execute(
            """
            UPDATE cbt_worksheets
            SET record_date = COALESCE(
                CASE linked_entry_type
                    WHEN 'daily' THEN (
                        SELECT entry_date
                        FROM dailydiary_entries
                        WHERE id = linked_entry_id AND user_id = cbt_worksheets.user_id
                    )
                    WHEN 'dream' THEN (
                        SELECT entry_date
                        FROM dreamdiary_entries
                        WHERE id = linked_entry_id AND user_id = cbt_worksheets.user_id
                    )
                END,
                date(created_at),
                date('now')
            )
            WHERE record_date IS NULL OR record_date = ''
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_user_status
            ON cbt_worksheets(user_id, status, updated_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_linked_entry
            ON cbt_worksheets(user_id, linked_entry_type, linked_entry_id)
            WHERE linked_entry_id IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_user_date
            ON cbt_worksheets(user_id, record_date, id)
            """
        )

    if log:
        log('Runtime migration ensured CBT worksheet tables exist')
    return True
