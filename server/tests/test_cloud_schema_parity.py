import re

from scripts.load_cloud_migration import IDENTITY_ID_TABLES, SCHEMA_PATH
from scripts.rehearse_cloud_migration import TABLE_ORDER


CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE IF NOT EXISTS (?P<table>[A-Za-z_][A-Za-z0-9_]*) \(",
    re.IGNORECASE,
)


def _postgres_schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _postgres_data_tables() -> set[str]:
    tables = {
        match.group("table")
        for match in CREATE_TABLE_RE.finditer(_postgres_schema_sql())
    }
    tables.discard("schema_migrations")
    return tables


def _postgres_identity_tables() -> set[str]:
    sql = _postgres_schema_sql()
    identity_tables = set()
    for table_name in _postgres_data_tables():
        table_match = re.search(
            rf"CREATE TABLE IF NOT EXISTS {table_name} \((?P<body>.*?)\n\);",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if not table_match:
            continue
        if re.search(
            r"\bid\s+BIGINT\s+GENERATED\s+BY\s+DEFAULT\s+AS\s+IDENTITY\b",
            table_match.group("body"),
            re.IGNORECASE,
        ):
            identity_tables.add(table_name)
    return identity_tables


def test_cloud_export_table_order_covers_every_postgres_data_table():
    assert set(TABLE_ORDER) == _postgres_data_tables()


def test_cloud_loader_resets_every_postgres_identity_table():
    assert IDENTITY_ID_TABLES == _postgres_identity_tables()
