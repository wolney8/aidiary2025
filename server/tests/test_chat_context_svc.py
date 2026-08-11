import sqlite3

from services.chat_context_svc import ChatContextService, estimate_tokens
from services.runtime_migrations import ensure_chat_messages_table


def _create_context_database(path: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                display_name TEXT,
                first_name TEXT,
                pronouns TEXT,
                gender TEXT,
                custom_guidance TEXT,
                allow_ai_history INTEGER,
                dailydiary_api_key TEXT
            );
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                entry_date TEXT,
                entry_number INTEGER,
                title TEXT,
                user_message TEXT,
                tags TEXT,
                daily_people_names TEXT
            );
            CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                entry_date TEXT,
                entry_number INTEGER,
                title TEXT,
                plot TEXT,
                summary TEXT,
                tags TEXT,
                dream_people_names TEXT
            );
            CREATE TABLE cbt_worksheets (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title TEXT,
                status TEXT,
                current_step INTEGER,
                record_date TEXT,
                updated_at TEXT
            );
            CREATE TABLE cbt_thought_record_data (
                worksheet_id INTEGER PRIMARY KEY,
                situation TEXT,
                balanced_thought TEXT
            );
            CREATE TABLE important_days (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                label TEXT,
                starts_on TEXT,
                month INTEGER,
                day INTEGER,
                category TEXT,
                note TEXT,
                updated_at TEXT
            );
            """
        )


def test_chat_context_is_user_scoped_and_omits_secrets(tmp_path):
    database_path = str(tmp_path / 'context.db')
    _create_context_database(database_path)

    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO users (
                id, username, password, display_name, pronouns, custom_guidance,
                dailydiary_api_key
            ) VALUES (1, 'one', 'hash', 'Alex', 'they/them', 'Be practical', 'secret-key')
            """
        )
        conn.execute(
            "INSERT INTO users (id, username, password, display_name) VALUES (2, 'two', 'hash', 'Sam')"
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                id, user_id, entry_date, entry_number, title, user_message, tags,
                daily_people_names
            ) VALUES (1, 1, '2026-07-20', 1, 'A good walk', 'I walked with Jamie.', 'health,outdoors', 'Jamie')
            """
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                id, user_id, entry_date, entry_number, title, user_message, tags,
                daily_people_names
            ) VALUES (2, 2, '2026-07-21', 1, 'Private', 'Other user secret.', 'private', 'Taylor')
            """
        )

    context = ChatContextService(database_path).build_context(1)

    assert 'Name: Alex' in context
    assert 'Pronouns: they/them' in context
    assert 'A good walk' in context
    assert 'health' in context
    assert 'jamie' in context
    assert 'Other user secret' not in context
    assert 'secret-key' not in context


def test_chat_context_combines_modes_newest_first(tmp_path):
    database_path = str(tmp_path / 'context.db')
    _create_context_database(database_path)

    with sqlite3.connect(database_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, password, first_name) VALUES (1, 'one', 'hash', 'Alex')"
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                id, user_id, entry_date, entry_number, title, user_message, tags,
                daily_people_names
            ) VALUES (1, 1, '2026-07-19', 1, 'Older daily', ?, 'work,health', 'Jamie')
            """,
            ('daily body ' * 100,),
        )
        conn.execute(
            """
            INSERT INTO dreamdiary_entries (
                id, user_id, entry_date, entry_number, title, plot, summary, tags,
                dream_people_names
            ) VALUES (1, 1, '2026-07-20', 1, 'Newer dream', 'plot', 'A concise dream summary', 'health,dream', 'Jamie')
            """
        )

    context = ChatContextService(database_path).build_context(1)

    assert context.index('Newer dream') < context.index('Older daily')
    assert 'Frequent themes: health' in context


def test_chat_context_omits_prior_entries_when_history_is_disabled(tmp_path):
    database_path = str(tmp_path / 'context.db')
    _create_context_database(database_path)

    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO users (
                id, username, password, display_name, allow_ai_history
            ) VALUES (1, 'one', 'hash', 'Alex', 0)
            """
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                id, user_id, entry_date, entry_number, title, user_message, tags,
                daily_people_names
            ) VALUES (1, 1, '2026-07-20', 1, 'Private callback', 'This prior detail should stay out.', 'health', 'Jamie')
            """
        )

    context = ChatContextService(database_path).build_context(1)

    assert 'Name: Alex' in context
    assert 'Prior-entry memory is disabled' in context
    assert 'Private callback' not in context
    assert 'This prior detail should stay out' not in context
    assert 'Frequent themes' not in context


def test_chat_context_includes_thought_records_and_important_days_when_history_allowed(tmp_path):
    database_path = str(tmp_path / 'context.db')
    _create_context_database(database_path)

    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO users (
                id, username, password, display_name, allow_ai_history
            ) VALUES (1, 'one', 'hash', 'Alex', 1)
            """
        )
        conn.execute(
            """
            INSERT INTO cbt_worksheets (
                id, user_id, title, status, current_step, record_date, updated_at
            ) VALUES (1, 1, 'Reframing work anxiety', 'completed', 7, '2026-07-22', '2026-07-22')
            """
        )
        conn.execute(
            """
            INSERT INTO cbt_thought_record_data (
                worksheet_id, situation, balanced_thought
            ) VALUES (1, 'Felt judged in a meeting', 'I had evidence that the meeting went fine')
            """
        )
        conn.execute(
            """
            INSERT INTO important_days (
                id, user_id, label, starts_on, month, day, category, note, updated_at
            ) VALUES (1, 1, 'Therapy milestone', '2026-07-20', 7, 20, 'milestone', 'First clear progress marker', '2026-07-20')
            """
        )

    context = ChatContextService(database_path).build_context(1)
    status = ChatContextService(database_path).build_context_status(1)

    assert 'Thought Record | Reframing work anxiety' in context
    assert 'Situation: Felt judged in a meeting' in context
    assert 'Important Day | Therapy milestone' in context
    assert 'First clear progress marker' in context
    source_counts = {source['label']: source['count'] for source in status['sources']}
    assert source_counts['Thought records'] == 1
    assert source_counts['Important days'] == 1


def test_chat_context_status_does_not_count_prior_records_when_history_disabled(tmp_path):
    database_path = str(tmp_path / 'context.db')
    _create_context_database(database_path)

    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            INSERT INTO users (
                id, username, password, display_name, allow_ai_history
            ) VALUES (1, 'one', 'hash', 'Alex', 0)
            """
        )
        conn.execute(
            """
            INSERT INTO important_days (
                id, user_id, label, starts_on, month, day, category, note, updated_at
            ) VALUES (1, 1, 'Private milestone', '2026-07-20', 7, 20, 'milestone', 'Do not count', '2026-07-20')
            """
        )

    status = ChatContextService(database_path).build_context_status(1)

    assert status['history_enabled'] is False
    assert all(source['count'] == 0 for source in status['sources'])
    assert all(source['enabled'] is False for source in status['sources'])


def test_chat_context_trims_oldest_entries_to_respect_budget(tmp_path):
    database_path = str(tmp_path / 'context.db')
    _create_context_database(database_path)

    with sqlite3.connect(database_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, password, first_name) VALUES (1, 'one', 'hash', 'Alex')"
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (
                id, user_id, entry_date, entry_number, title, user_message, tags,
                daily_people_names
            ) VALUES (1, 1, '2026-07-19', 1, 'Older daily', ?, 'work', 'Jamie')
            """,
            ('daily body ' * 100,),
        )
        conn.execute(
            """
            INSERT INTO dreamdiary_entries (
                id, user_id, entry_date, entry_number, title, plot, summary, tags,
                dream_people_names
            ) VALUES (1, 1, '2026-07-20', 1, 'Newer dream', 'plot', 'A concise dream summary', 'dream', 'Jamie')
            """
        )

    context = ChatContextService(database_path, token_budget=220).build_context(1)

    assert estimate_tokens(context) <= 220
    assert 'Newer dream' in context
    assert 'Older daily' not in context


def test_chat_context_handles_missing_diary_tables(tmp_path):
    database_path = str(tmp_path / 'context.db')
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT, first_name TEXT)"
        )
        conn.execute(
            "INSERT INTO users (id, username, password, first_name) VALUES (1, 'one', 'hash', 'Alex')"
        )

    context = ChatContextService(database_path).build_context(1)

    assert 'Name: Alex' in context
    assert 'Recent diary entries' not in context


def test_chat_system_prompt_stays_within_context_budget(tmp_path):
    database_path = str(tmp_path / 'context.db')
    _create_context_database(database_path)
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, password, first_name) VALUES (1, 'one', 'hash', 'Alex')"
        )

    prompt = ChatContextService(database_path, token_budget=100).build_system_prompt(1)

    assert estimate_tokens(prompt) <= 100
    assert prompt.startswith('You are a supportive OpenMynd diary companion.')


class _FakePostgresConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if 'FROM information_schema.tables' in sql:
            return _FakeRows([{'exists': 1}])
        if 'FROM information_schema.columns' in sql:
            table_name = params[0]
            columns = {
                'users': [
                    'display_name',
                    'first_name',
                    'pronouns',
                    'gender',
                    'custom_guidance',
                    'allow_ai_history',
                ],
                'dailydiary_entries': [
                    'entry_date',
                    'entry_number',
                    'title',
                    'user_message',
                    'tags',
                    'daily_people_names',
                ],
                'dreamdiary_entries': [
                    'entry_date',
                    'entry_number',
                    'title',
                    'plot',
                    'summary',
                    'tags',
                    'dream_people_names',
                ],
            }.get(table_name, [])
            return _FakeRows([{'column_name': column} for column in columns])
        if 'FROM users' in sql:
            return _FakeRows([
                {
                    'display_name': 'Alex',
                    'first_name': '',
                    'pronouns': 'they/them',
                    'gender': '',
                    'custom_guidance': 'Be practical',
                    'allow_ai_history': 1,
                }
            ])
        if 'FROM dailydiary_entries' in sql:
            return _FakeRows([
                {
                    'entry_date': '2026-07-20',
                    'entry_number': 1,
                    'title': 'Postgres daily',
                    'body': 'A portable context row.',
                    'tags': 'health',
                    'people': 'Jamie',
                }
            ])
        if 'FROM dreamdiary_entries' in sql:
            return _FakeRows([])
        return _FakeRows([])


class _FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _FakePostgresAdapter:
    provider = 'postgres'

    def __init__(self):
        self.connection = _FakePostgresConnection()

    def connect(self, **_kwargs):
        adapter = self

        class _Context:
            def __enter__(self):
                return adapter.connection

            def __exit__(self, exc_type, exc, traceback):
                return False

        return _Context()

    def table_exists(self, conn, table_name):
        return conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        ).fetchone() is not None

    def table_columns(self, conn, table_name):
        return {
            row['column_name']
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                """,
                (table_name,),
            ).fetchall()
        }


def test_chat_context_uses_adapter_and_postgres_placeholders():
    adapter = _FakePostgresAdapter()

    context = ChatContextService('/unused/sqlite.db', adapter=adapter).build_context(1)

    assert 'Name: Alex' in context
    assert 'Postgres daily' in context
    user_query = next(sql for sql, _params in adapter.connection.calls if 'FROM users' in sql)
    daily_query = next(
        sql for sql, _params in adapter.connection.calls if 'FROM dailydiary_entries' in sql
    )
    assert '%s' in user_query
    assert '%s' in daily_query


def test_chat_messages_runtime_migration_is_idempotent(tmp_path):
    database_path = str(tmp_path / 'chat.db')
    with sqlite3.connect(database_path) as conn:
        conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY)')

    assert ensure_chat_messages_table(database_path) is True
    assert ensure_chat_messages_table(database_path) is True

    with sqlite3.connect(database_path) as conn:
        columns = {
            row[1] for row in conn.execute('PRAGMA table_info(chat_messages)').fetchall()
        }
        indexes = {
            row[1] for row in conn.execute('PRAGMA index_list(chat_messages)').fetchall()
        }

    assert {
        'user_id', 'conversation_id', 'request_id', 'role', 'content', 'token_count'
    } <= columns
    assert 'idx_chat_messages_conversation' in indexes
    assert 'idx_chat_messages_user_created' in indexes
    assert 'idx_chat_messages_request_role' in indexes
