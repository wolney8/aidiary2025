from scripts.validate_production_preflight import build_production_preflight


def _base_env() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "JWT_SECRET": "x" * 40,
        "DATABASE_PROVIDER": "sqlite",
        "DB_PATH": "db/app.db",
        "CORS_ORIGINS": "https://diary.example.com",
        "OPENAI_API_KEY": "sk-test",
        "MEDIA_ROOT": "/var/lib/aidiary/media",
        "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
    }


def test_preflight_blocks_unsafe_production_defaults(tmp_path):
    report = build_production_preflight(
        root_path=tmp_path,
        environ={
            "DATABASE_PROVIDER": "sqlite",
            "CORS_ORIGINS": "http://localhost:4200",
        },
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "jwt_secret" in gates
    assert "cors_origins" in gates


def test_preflight_blocks_sqlite_for_public_production_by_default(tmp_path):
    report = build_production_preflight(
        root_path=tmp_path,
        environ=_base_env(),
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "production_database_provider" in gates
    assert "production_runtime_migrations" in gates
    assert report["summary"]["database_provider"] == "sqlite"


def test_preflight_allows_explicit_sqlite_emergency_fallback(tmp_path):
    env = _base_env()
    env["OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK"] = "true"
    env["OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION"] = "true"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
    )

    assert report["ready_for_production"] is True
    assert report["blockers"] == []
    assert report["summary"]["sqlite_production_fallback_allowed"] is True
    assert report["summary"]["runtime_migrations_allowed_in_production"] is True


def test_preflight_requires_postgres_for_cloud_cutover(tmp_path):
    report = build_production_preflight(
        root_path=tmp_path,
        environ=_base_env(),
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "postgres_provider" in gates
    assert "database_url" in gates
    assert "runtime_migrations" in gates
    assert "production_database_provider" in gates


def test_preflight_accepts_postgres_cutover_shape(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    assert report["ready_for_production"] is True
    assert report["blockers"] == []
    assert report["summary"]["database_provider"] == "postgres"
    assert report["summary"]["database_url_ssl_disabled"] is False
    assert report["summary"]["database_pooler_configured"] is True


def test_preflight_blocks_postgres_cutover_with_disabled_ssl(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=disable"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "database_url_ssl" in gates
    assert report["summary"]["database_url_ssl_disabled"] is True


def test_preflight_warns_when_postgres_pooling_is_not_explicit(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example.com/rehearsal?sslmode=require"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "database_pooling" in warning_gates
    assert report["summary"]["database_pooler_configured"] is False


def test_preflight_accepts_explicit_pooler_confirmation(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example.com/rehearsal?sslmode=require"
    env["DATABASE_USES_POOLER"] = "true"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "database_pooling" not in warning_gates
    assert report["summary"]["database_pooler_configured"] is True
