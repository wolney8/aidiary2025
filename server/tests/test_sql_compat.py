import pytest

from services.sql_compat import (
    adapt_placeholders,
    append_returning_id,
    bind_values,
    current_date_expr,
    date_expr,
    date_month_day_expr,
    date_month_expr,
    date_year_expr,
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


def test_placeholder_uses_postgres_psycopg_parameters():
    assert placeholder(1, "postgres") == "%s"
    assert placeholders(3, "postgres", start=2) == "%s, %s, %s"


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
        == "SELECT * FROM users WHERE id = %s AND note = '?' AND username = %s"
    )


def test_adapt_placeholders_handles_escaped_single_quotes():
    sql = "SELECT * FROM notes WHERE text = 'it''s ? literal' AND id = ?"

    assert (
        adapt_placeholders(sql, "postgres")
        == "SELECT * FROM notes WHERE text = 'it''s ? literal' AND id = %s"
    )


def test_adapt_placeholders_escapes_literal_percent_for_psycopg():
    sql = "SELECT * FROM billing_plans WHERE features_json LIKE '%AI analyses%' AND tier = ?"

    assert (
        adapt_placeholders(sql, "postgres")
        == "SELECT * FROM billing_plans WHERE features_json LIKE '%%AI analyses%%' AND tier = %s"
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
    sql = "INSERT INTO users (username) VALUES (%s) RETURNING id"

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


def test_date_expr_uses_provider_specific_casts():
    assert date_expr("created_at", "sqlite") == "date(created_at)"
    assert date_expr("created_at", "postgres") == "(created_at)::date"


def test_date_part_exprs_use_provider_specific_extraction():
    assert date_month_expr("entry_date", "sqlite") == "substr(entry_date, 6, 2)"
    assert date_month_expr("entry_date", "postgres") == "to_char((entry_date)::date, 'MM')"
    assert date_month_day_expr("entry_date", "sqlite") == "substr(entry_date, 6, 5)"
    assert date_month_day_expr("entry_date", "postgres") == "to_char((entry_date)::date, 'MM-DD')"
    assert date_year_expr("entry_date", "sqlite") == "CAST(substr(entry_date, 1, 4) AS INTEGER)"
    assert date_year_expr("entry_date", "postgres") == "EXTRACT(YEAR FROM (entry_date)::date)::integer"


def test_current_date_expr_uses_provider_specific_current_date():
    assert current_date_expr("sqlite") == "date('now')"
    assert current_date_expr("postgres") == "CURRENT_DATE"
