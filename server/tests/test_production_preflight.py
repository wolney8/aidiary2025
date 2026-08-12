from scripts.validate_production_preflight import build_production_preflight


def _base_env() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "JWT_SECRET": "x" * 40,
        "DATABASE_PROVIDER": "sqlite",
        "DB_PATH": "db/app.db",
        "CORS_ORIGINS": "https://openmynd.app",
        "FRONTEND_BASE_URL": "https://openmynd.app",
        "OPENAI_API_KEY": "sk-test",
        "MEDIA_ROOT": "/var/lib/openmynd/media",
        "RATELIMIT_STORAGE_URI": "redis://localhost:6379/0",
        "AUTH_LOGIN_RATE_LIMIT": "10 per minute",
        "AUTH_REGISTER_RATE_LIMIT": "5 per hour",
        "AUTH_PASSWORD_RESET_RATE_LIMIT": "5 per hour",
        "AUTH_EMAIL_VERIFICATION_RATE_LIMIT": "5 per hour",
        "AUTH_OAUTH_START_RATE_LIMIT": "20 per minute",
        "AUTH_OAUTH_CALLBACK_RATE_LIMIT": "20 per minute",
        "ANALYSE_RATE_LIMIT": "30 per hour",
        "IMPORT_UPLOAD_RATE_LIMIT": "20 per hour",
        "IMPORT_COMMIT_RATE_LIMIT": "30 per hour",
        "IMPORT_JOB_RATE_LIMIT": "30 per hour",
        "IMPORT_REVERT_RATE_LIMIT": "10 per hour",
        "EXPORT_RATE_LIMIT": "20 per hour",
        "ACCOUNT_DELETE_RATE_LIMIT": "5 per hour",
        "SECURITY_AUDIT_RETENTION_DAYS": "180",
        "OPENMYND_REQUIRE_REGISTRATION_EMAIL": "true",
        "EMAIL_PROVIDER": "smtp",
        "EMAIL_FROM_ADDRESS": "OpenMynd <no-reply@openmynd.app>",
        "SMTP_HOST": "smtp.openmynd.app",
        "STRIPE_SECRET_KEY": "sk_test_public_preflight",
        "STRIPE_WEBHOOK_SECRET": "whsec_public_preflight",
        "STRIPE_PRICE_PERSONAL_MONTHLY": "price_personal_monthly",
        "STRIPE_PRICE_PERSONAL_ANNUAL": "price_personal_annual",
        "STRIPE_PRICE_PLUS_MONTHLY": "price_plus_monthly",
        "STRIPE_PRICE_PLUS_ANNUAL": "price_plus_annual",
    }


def _write_frontend_sources(root, *, include_cookies: bool = True) -> None:
    client_root = root / "client"
    routes = [
        'path: "privacy"',
        'path: "terms"',
    ]
    if include_cookies:
        routes.append('path: "cookies"')
    (client_root / "src/app").mkdir(parents=True)
    (client_root / "src/app/app.routes.ts").write_text("\n".join(routes), encoding="utf-8")
    (client_root / "src/app/legal").mkdir(parents=True)
    (client_root / "src/app/legal/legal-page.component.ts").write_text(
        "export class LegalPageComponent {}",
        encoding="utf-8",
    )
    (client_root / "src/app/shared/components/cookie-consent").mkdir(parents=True)
    (
        client_root
        / "src/app/shared/components/cookie-consent/cookie-consent.component.ts"
    ).write_text("export class CookieConsentComponent {}", encoding="utf-8")


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


def test_preflight_blocks_incomplete_stripe_configuration(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env.pop("STRIPE_WEBHOOK_SECRET")

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "stripe_configuration" in gates
    assert report["summary"]["stripe_webhook_secret_configured"] is False


def test_preflight_blocks_missing_annual_stripe_prices(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env.pop("STRIPE_PRICE_PERSONAL_ANNUAL")
    env.pop("STRIPE_PRICE_PLUS_ANNUAL")

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "stripe_configuration" in gates
    assert report["summary"]["stripe_price_personal_monthly_configured"] is True
    assert report["summary"]["stripe_price_personal_annual_configured"] is False
    assert report["summary"]["stripe_price_plus_annual_configured"] is False


def test_preflight_accepts_legacy_monthly_stripe_prices_with_annual_prices(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env.pop("STRIPE_PRICE_PERSONAL_MONTHLY")
    env.pop("STRIPE_PRICE_PLUS_MONTHLY")
    env["STRIPE_PRICE_PERSONAL"] = "price_personal_legacy"
    env["STRIPE_PRICE_PLUS"] = "price_plus_legacy"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    assert report["ready_for_production"] is True
    assert report["blockers"] == []
    assert report["summary"]["stripe_price_personal_monthly_configured"] is True
    assert report["summary"]["stripe_price_personal_annual_configured"] is True
    assert report["summary"]["stripe_price_plus_monthly_configured"] is True
    assert report["summary"]["stripe_price_plus_annual_configured"] is True


def test_preflight_blocks_malformed_stripe_values(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env["STRIPE_SECRET_KEY"] = "not-a-stripe-secret"
    env["STRIPE_WEBHOOK_SECRET"] = "not-a-webhook-secret"
    env["STRIPE_PRICE_PLUS_MONTHLY"] = "plus-tier"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "stripe_secret_key" in gates
    assert "stripe_webhook_secret" in gates
    assert "stripe_price_plus_monthly" in gates


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
    assert report["summary"]["cookie_auth_mode"] is False
    assert report["summary"]["cookie_auth_csrf_protect"] is False


def test_preflight_warns_when_cookie_auth_lacks_csrf(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env["OPENMYND_AUTH_COOKIE_MODE"] = "true"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "cookie_auth_csrf" in warning_gates
    assert report["summary"]["cookie_auth_mode"] is True
    assert report["summary"]["cookie_auth_csrf_protect"] is False


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


def test_preflight_accepts_disabled_legacy_password_fallback(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env["OPENMYND_DISABLE_LEGACY_PASSWORD_FALLBACK"] = "true"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert "legacy_password_fallback_review" not in warning_gates
    assert report["summary"]["legacy_password_fallback_disabled"] is True


def test_preflight_warns_when_sensitive_rate_limits_are_not_explicit(tmp_path):
    env = _base_env()
    for key in (
        "AUTH_LOGIN_RATE_LIMIT",
        "AUTH_REGISTER_RATE_LIMIT",
        "AUTH_PASSWORD_RESET_RATE_LIMIT",
        "AUTH_EMAIL_VERIFICATION_RATE_LIMIT",
        "AUTH_OAUTH_START_RATE_LIMIT",
        "AUTH_OAUTH_CALLBACK_RATE_LIMIT",
        "ANALYSE_RATE_LIMIT",
        "IMPORT_UPLOAD_RATE_LIMIT",
        "IMPORT_COMMIT_RATE_LIMIT",
        "IMPORT_JOB_RATE_LIMIT",
        "IMPORT_REVERT_RATE_LIMIT",
        "EXPORT_RATE_LIMIT",
        "ACCOUNT_DELETE_RATE_LIMIT",
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
    assert "sensitive_route_rate_limits" in warning_gates
    assert report["summary"]["sensitive_rate_limits_configured"] == {
        "AUTH_LOGIN_RATE_LIMIT": False,
        "AUTH_REGISTER_RATE_LIMIT": False,
        "AUTH_PASSWORD_RESET_RATE_LIMIT": False,
        "AUTH_EMAIL_VERIFICATION_RATE_LIMIT": False,
        "AUTH_OAUTH_START_RATE_LIMIT": False,
        "AUTH_OAUTH_CALLBACK_RATE_LIMIT": False,
        "ANALYSE_RATE_LIMIT": False,
        "IMPORT_UPLOAD_RATE_LIMIT": False,
        "IMPORT_COMMIT_RATE_LIMIT": False,
        "IMPORT_JOB_RATE_LIMIT": False,
        "IMPORT_REVERT_RATE_LIMIT": False,
        "EXPORT_RATE_LIMIT": False,
        "ACCOUNT_DELETE_RATE_LIMIT": False,
    }


def test_preflight_warns_when_security_audit_retention_is_missing(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env.pop("SECURITY_AUDIT_RETENTION_DAYS")

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "security_audit_retention" in warning_gates
    assert report["summary"]["security_audit_retention_days"] is None


def test_preflight_warns_when_security_audit_retention_is_outside_review_range(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env["SECURITY_AUDIT_RETENTION_DAYS"] = "7"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "security_audit_retention" in warning_gates
    assert report["summary"]["security_audit_retention_days"] == 7


def test_preflight_blocks_console_email_in_production(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env["EMAIL_PROVIDER"] = "console"

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "transactional_email_provider" in gates
    assert report["summary"]["email_provider"] == "console"


def test_preflight_blocks_missing_smtp_host_in_production(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env.pop("SMTP_HOST")

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "transactional_email_smtp_host" in gates
    assert report["summary"]["smtp_host_configured"] is False


def test_preflight_warns_when_registration_email_is_not_required(tmp_path):
    env = _base_env()
    env["DATABASE_PROVIDER"] = "postgres"
    env["DATABASE_URL"] = "postgresql://example-pooler/rehearsal?sslmode=require"
    env.pop("OPENMYND_REQUIRE_REGISTRATION_EMAIL")

    report = build_production_preflight(
        root_path=tmp_path,
        environ=env,
        require_postgres=True,
    )

    warning_gates = {warning["gate"] for warning in report["warnings"]}
    assert report["ready_for_production"] is True
    assert "registration_email_required" in warning_gates
    assert report["summary"]["registration_email_required"] is False


def test_preflight_blocks_missing_public_cookie_route_when_frontend_is_available(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    _write_frontend_sources(tmp_path, include_cookies=False)
    env = _base_env()
    env["OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK"] = "true"
    env["OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION"] = "true"

    report = build_production_preflight(
        root_path=server_root,
        environ=env,
    )

    gates = {blocker["gate"] for blocker in report["blockers"]}
    assert report["ready_for_production"] is False
    assert "public_frontend_routes" in gates
    assert report["summary"]["public_frontend_routes_present"] is False


def test_preflight_accepts_public_routes_when_frontend_sources_are_complete(tmp_path):
    server_root = tmp_path / "server"
    server_root.mkdir()
    _write_frontend_sources(tmp_path, include_cookies=True)
    env = _base_env()
    env["OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK"] = "true"
    env["OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION"] = "true"

    report = build_production_preflight(
        root_path=server_root,
        environ=env,
    )

    assert report["ready_for_production"] is True
    assert report["summary"]["public_frontend_routes_present"] is True
