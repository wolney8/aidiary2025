from scripts.run_postgres_migrations import (
    build_migration_plan,
    discover_migrations,
    ensure_migration_ledger,
    fetch_applied_versions,
)


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, statement, params=None):
        self.executed.append((statement, params))
        return self

    def fetchall(self):
        return self.rows


def test_discover_migrations_returns_ordered_sql_files(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "0002_second.sql").write_text("SELECT 2;", encoding="utf-8")
    (migrations_dir / "0001_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations_dir / "README.md").write_text("ignore", encoding="utf-8")

    migrations = discover_migrations(migrations_dir)

    assert [migration.version for migration in migrations] == [
        "0001_first",
        "0002_second",
    ]


def test_build_migration_plan_marks_pending_versions(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "0001_initial_schema.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations_dir / "0002_next.sql").write_text("SELECT 2;", encoding="utf-8")

    plan = build_migration_plan(
        applied_versions=["0001_initial_schema"],
        migrations_dir=migrations_dir,
    )

    assert plan["all_versions"] == ["0001_initial_schema", "0002_next"]
    assert plan["applied_versions"] == ["0001_initial_schema"]
    assert plan["pending_versions"] == ["0002_next"]


def test_fetch_applied_versions_ensures_ledger_before_selecting():
    cursor = FakeCursor(rows=[("0001_initial_schema",), ("0002_next",)])

    versions = fetch_applied_versions(cursor)

    assert versions == {"0001_initial_schema", "0002_next"}
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in cursor.executed[0][0]
    assert cursor.executed[1] == (
        "SELECT version FROM schema_migrations ORDER BY version",
        None,
    )


def test_ensure_migration_ledger_is_idempotent_statement():
    cursor = FakeCursor()

    ensure_migration_ledger(cursor)

    assert len(cursor.executed) == 1
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in cursor.executed[0][0]
