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

    assert {'user_id', 'conversation_id', 'role', 'content', 'token_count'} <= columns
    assert 'idx_chat_messages_conversation' in indexes
    assert 'idx_chat_messages_user_created' in indexes
