import pytest

from services.sql_compat import (
    adapt_placeholders,
    append_returning_id,
    bind_values,
    in_placeholders,
    inserted_id,
    placeholder,
    placeholders,
)


class _Cursor:
    def __init__(self, *, lastrowid=None, row=None):
        self.lastrowid = lastrowid
        self._row = row

    def fetchone(self):
        return self._row


def test_placeholder_uses_sqlite_question_marks():
    assert placeholder(1, "sqlite") == "?"
    assert placeholders(3, "sqlite") == "?, ?, ?"


def test_placeholder_uses_postgres_numbered_parameters():
    assert placeholder(1, "postgres") == "$1"
    assert placeholders(3, "postgres", start=2) == "$2, $3, $4"


def test_placeholder_rejects_invalid_postgres_index():
    with pytest.raises(ValueError, match="1-based"):
        placeholder(0, "postgres")


def test_in_placeholders_rejects_empty_values():
    with pytest.raises(ValueError, match="cannot be empty"):
        in_placeholders([], "sqlite")


def test_adapt_placeholders_passes_sqlite_through():
    sql = "SELECT * FROM users WHERE id = ? AND username = '?'"

    assert adapt_placeholders(sql, "sqlite") == sql


def test_adapt_placeholders_converts_postgres_markers_outside_strings():
    sql = "SELECT * FROM users WHERE id = ? AND note = '?' AND username = ?"

    assert (
        adapt_placeholders(sql, "postgres")
        == "SELECT * FROM users WHERE id = $1 AND note = '?' AND username = $2"
    )


def test_adapt_placeholders_handles_escaped_single_quotes():
    sql = "SELECT * FROM notes WHERE text = 'it''s ? literal' AND id = ?"

    assert (
        adapt_placeholders(sql, "postgres")
        == "SELECT * FROM notes WHERE text = 'it''s ? literal' AND id = $1"
    )


def test_append_returning_id_only_for_postgres():
    sql = "INSERT INTO users (username) VALUES (?)"

    assert append_returning_id(sql, "sqlite") == sql
    assert (
        append_returning_id(sql, "postgres")
        == "INSERT INTO users (username) VALUES (?) RETURNING id"
    )


def test_append_returning_id_preserves_statement_semicolon():
    sql = "INSERT INTO users (username) VALUES (?);"

    assert (
        append_returning_id(sql, "postgres")
        == "INSERT INTO users (username) VALUES (?) RETURNING id;"
    )


def test_append_returning_id_is_idempotent():
    sql = "INSERT INTO users (username) VALUES ($1) RETURNING id"

    assert append_returning_id(sql, "postgres") == sql


def test_bind_values_flattens_parameter_groups():
    assert bind_values([1, 2], ("three",), []) == (1, 2, "three")


def test_inserted_id_uses_sqlite_lastrowid():
    assert inserted_id(_Cursor(lastrowid=42), "sqlite") == 42


def test_inserted_id_uses_postgres_returning_tuple():
    assert inserted_id(_Cursor(row=(43,)), "postgres") == 43


def test_inserted_id_uses_postgres_returning_mapping():
    assert inserted_id(_Cursor(row={"id": 44}), "postgres") == 44


def test_inserted_id_requires_postgres_returned_row():
    with pytest.raises(RuntimeError, match="did not return a row"):
        inserted_id(_Cursor(row=None), "postgres")
