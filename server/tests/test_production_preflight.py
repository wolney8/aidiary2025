from scripts.validate_production_preflight import build_production_preflight


def _base_env() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "JWT_SECRET": "x" * 40,
        "DATABASE_PROVIDER": "sqlite",
        "DB_PATH": "db/app.db",
        "CORS_ORIGINS": "https://diary.example.com",
        "FRONTEND_BASE_URL": "https://diary.example.com",
        "OPENAI_API_KEY": "sk-test",
        "MEDIA_ROOT": "/var/lib/openmynd/media",
        "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
        "AUTH_LOGIN_RATE_LIMIT": "10 per minute",
        "AUTH_REGISTER_RATE_LIMIT": "5 per hour",
        "AUTH_OAUTH_START_RATE_LIMIT": "20 per minute",
        "AUTH_OAUTH_CALLBACK_RATE_LIMIT": "20 per minute",
    }


def test_preflight_blocks_unsafe_production_defaults(tmp_path):
    report = build_production_preflight(
        root_path=tmp_path,
        environ={
            "APP_ENV": "production",
            "DATABASE_PROVIDER": "sqlite",
            "CORS_ORIGINS": "http://localhost:4200",
        },
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "jwt_secret" in gates
    assert "cors_origins" in gates
    assert "frontend_base_url" in gates


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


def test_preflight_blocks_local_google_oauth_redirect_in_production(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env["OAUTH_GOOGLE_CLIENT_ID"] = "google-client"
    env["OAUTH_GOOGLE_CLIENT_SECRET"] = "google-secret"
    env["OAUTH_GOOGLE_REDIRECT_URI"] = "http://localhost:5001/api/oauth/google/callback"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "oauth_google_redirect_uri" in gates
    assert report["summary"]["oauth_google_configured"] is True
    assert report["summary"]["oauth_google_redirect_https"] is False


def test_preflight_warns_about_unaccepted_session_and_password_risks(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "jwt_browser_storage_review" in warning_gates
    assert "legacy_password_fallback_review" in warning_gates
    assert report["summary"]["localstorage_jwt_risk_accepted"] is False
    assert report["summary"]["legacy_password_fallback_accepted"] is False


def test_preflight_records_accepted_session_and_password_risks(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env["OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK"] = "true"
    env["OPENMYND_ACCEPT_LEGACY_PASSWORD_FALLBACK"] = "true"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert "jwt_browser_storage_review" not in warning_gates
    assert "legacy_password_fallback_review" not in warning_gates
    assert report["summary"]["localstorage_jwt_risk_accepted"] is True
    assert report["summary"]["legacy_password_fallback_accepted"] is True


def test_preflight_warns_when_auth_rate_limits_are_not_explicit(tmp_path):
    env = _base_env()
    for key in (
        "AUTH_LOGIN_RATE_LIMIT",
        "AUTH_REGISTER_RATE_LIMIT",
        "AUTH_OAUTH_START_RATE_LIMIT",
        "AUTH_OAUTH_CALLBACK_RATE_LIMIT",
    ):
        env.pop(key)
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "auth_rate_limits" in warning_gates
    assert report["summary"]["auth_rate_limits_configured"] == {
        "AUTH_LOGIN_RATE_LIMIT": False,
        "AUTH_REGISTER_RATE_LIMIT": False,
        "AUTH_OAUTH_START_RATE_LIMIT": False,
        "AUTH_OAUTH_CALLBACK_RATE_LIMIT": False,
    }
