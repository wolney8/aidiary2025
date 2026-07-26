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


def test_preflight_accepts_explicit_sqlite_production_config(tmp_path):
    report = build_production_preflight(
        root_path=tmp_path,
        environ=_base_env(),
    )

    assert report["ready_for_production"] is True
    assert report["blockers"] == []
    assert report["summary"]["database_provider"] == "sqlite"


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


def test_preflight_accepts_postgres_cutover_shape(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example/rehearsal"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    assert report["ready_for_production"] is True
    assert report["blockers"] == []
    assert report["summary"]["database_provider"] == "postgres"
