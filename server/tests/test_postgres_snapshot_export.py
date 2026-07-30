import json
from contextlib import contextmanager

import pytest

from scripts.export_postgres_snapshot import export_postgres_snapshot


class _FakeConnection:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.executed_sql = []

    def execute(self, sql):
        self.executed_sql.append(sql)
        table_name = sql.split("FROM ", 1)[1].split()[0].strip('"')
        return _FakeResult(self.rows_by_table.get(table_name, []))


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _FakeAdapter:
    provider = "postgres"

    def __init__(self, rows_by_table, columns_by_table):
        self.rows_by_table = rows_by_table
        self.columns_by_table = columns_by_table
        self.connection = _FakeConnection(rows_by_table)

    @contextmanager
    def connect(self, *, timeout=30):
        yield self.connection

    def table_exists(self, _conn, table_name):
        return table_name in self.rows_by_table

    def table_columns(self, _conn, table_name):
        return self.columns_by_table.get(table_name, set())


def test_export_postgres_snapshot_writes_manifest_and_jsonl(tmp_path):
    adapter = _FakeAdapter(
        rows_by_table={
            "users": [{"id": 1, "username": "will"}],
            "cbt_thought_record_data": [
                {"worksheet_id": 7, "situation": "test", "balanced_thought": "ok"}
            ],
        },
        columns_by_table={
            "users": {"id", "username"},
            "cbt_thought_record_data": {"worksheet_id", "situation", "balanced_thought"},
        },
    )

    manifest = export_postgres_snapshot(
        adapter=adapter,
        output_dir=tmp_path,
        label="scheduled backup",
    )

    snapshot_dir = tmp_path / manifest["snapshot_dir"].split("/")[-1]
    assert snapshot_dir.exists()
    assert manifest["provider"] == "postgres"
    assert manifest["label"] == "scheduled backup"
    assert manifest["total_rows"] == 2
    assert [table["table"] for table in manifest["tables"]] == [
        "users",
        "cbt_thought_record_data",
    ]
    assert all(len(table["sha256"]) == 64 for table in manifest["tables"])
    assert (snapshot_dir / "manifest.json").exists()
    assert json.loads((snapshot_dir / "users.jsonl").read_text(encoding="utf-8")) == {
        "id": 1,
        "username": "will",
    }
    assert 'SELECT * FROM "users" ORDER BY "id"' in adapter.connection.executed_sql
    assert (
        'SELECT * FROM "cbt_thought_record_data" ORDER BY "worksheet_id"'
        in adapter.connection.executed_sql
    )


def test_export_postgres_snapshot_requires_postgres_provider(tmp_path):
    adapter = _FakeAdapter(rows_by_table={}, columns_by_table={})
    adapter.provider = "sqlite"

    with pytest.raises(ValueError, match="requires DATABASE_PROVIDER=postgres"):
        export_postgres_snapshot(adapter=adapter, output_dir=tmp_path)
