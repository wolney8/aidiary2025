# ADR 0005: Production SaaS Hosting Architecture

## Status

Accepted as the first public SaaS deployment target.

## Context

OpenMynd is moving from local/private use toward public SaaS readiness. The production
architecture needs to support:

- public login, registration, Google OAuth, email verification, and account recovery
- hosted Angular frontend
- hosted Flask API
- managed PostgreSQL
- object/media storage outside the repo and outside the database
- Stripe Billing later, without tying app permissions directly to Stripe product names
- predictable costs and a provider-portable escape path

Current repo constraints:

- Angular production builds currently call `environment.apiBaseUrl = "/api"`, so the
  public frontend must expose a same-origin `/api/*` path through a proxy/rewrite/CDN rule
  or the frontend environment must be changed in a later issue.
- The Flask backend exposes `create_app()` and now has a WSGI entrypoint at
  `server/wsgi.py`.
- Public production must run explicit migrations and preflight checks before startup.
- Neon is already the chosen Postgres rehearsal target in
  [ADR 0004](./0004-cloud-database-architecture.md).

Provider references reviewed on 8 August 2026:

- Vercel supports Angular deployment and custom-domain/static hosting workflows:
  <https://vercel.com/docs/frameworks/angular>
- Render supports Python/Flask web services and production start commands:
  <https://render.com/docs/deploy-flask>
- Neon documents serverless Postgres, branching, and pooled/direct connection options:
  <https://neon.com/docs/introduction>
- Cloudflare R2 is object storage with S3-compatible APIs and no egress fees listed in
  its product positioning:
  <https://developers.cloudflare.com/r2/>
- Stripe Billing/Checkout/Customer Portal remain the planned billing path:
  <https://docs.stripe.com/billing/quickstart>

## Decision

Use this first public SaaS architecture:

| Layer | Decision | Rationale |
| --- | --- | --- |
| DNS/TLS | Cloudflare DNS | Central place for domain, TLS, CDN/proxy rules, R2, and future WAF/rate controls. |
| Frontend | Vercel static Angular deployment | Low-friction Angular hosting, previews, CDN, custom domains. |
| API | Render Python web service | Simple Flask deployment model, persistent service process, environment secrets. |
| Database | Neon Postgres | Already selected for rehearsal, provider-portable through `DATABASE_URL`. |
| Media/object storage | Cloudflare R2 | Keeps images/attachments out of DB and local source tree; S3-compatible shape. |
| Email | SMTP provider configured through env | Keeps current provider-neutral email implementation. |
| Billing | Stripe Billing later | Standard hosted Checkout/Portal/webhook path, separate from app entitlements. |
| Monitoring | Start with platform logs plus Sentry-compatible app error tracking later | Avoid overbuilding before public beta, but leave clear production hook points. |

## Public Domain Shape

Recommended domain layout:

- `https://openmynd.app`: primary marketing/app entry.
- `https://openmynd.app/api/*`: frontend-facing API path, proxied to the Render API.
- `https://api.openmynd.app`: direct API origin for server-side callbacks, OAuth callback
  registration, health checks, and debugging.

If Vercel hosts `openmynd.app`, configure either:

- Vercel rewrites from `/api/*` to `https://api.openmynd.app/api/*`, or
- a Cloudflare rule that routes `/api/*` to the Render API while leaving frontend assets
  on Vercel.

Do not deploy the current Angular production build to a domain where `/api` is not
proxied, because production services use relative `/api` URLs.

## Deployment Shape

### Frontend

Provider: Vercel.

Root directory:

```text
client
```

Build command:

```bash
npm ci
npm run build
```

Output directory:

```text
dist/openmynd
```

Required behavior:

- SPA fallback to `index.html`.
- `/api/*` rewrite/proxy must reach the backend API.
- Legal routes `/privacy`, `/terms`, `/cookies`, and future `/pricing` must be public.

### Backend

Provider: Render web service.

Root directory:

```text
server
```

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn "wsgi:app" --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

Production startup gates:

```bash
APP_ENV=production PYTHONPATH=. python scripts/validate_production_preflight.py --require-postgres
PYTHONPATH=. python scripts/run_postgres_migrations.py --apply
```

Run migrations as an explicit deploy step before the web process starts. Do not rely on
runtime SQLite migration helpers in public production.

## Required Environment Variables

### Frontend

No frontend secrets. Public build/config only.

If a later issue changes Angular to use an absolute API URL, the value must be public and
environment-specific, for example:

```bash
OPENMYND_PUBLIC_API_BASE_URL=https://api.openmynd.app/api
```

### Backend

Core:

```bash
APP_ENV=production
FLASK_PORT=$PORT
JWT_SECRET=<secret-manager-value>
DATABASE_PROVIDER=postgres
DATABASE_URL=<neon-pooled-postgres-url>
DATABASE_USES_POOLER=true
CORS_ORIGINS=https://openmynd.app
FRONTEND_BASE_URL=https://openmynd.app
RATELIMIT_STORAGE_URI=<redis-url>
MEDIA_ROOT=/var/lib/openmynd/media
OPENAI_API_KEY=<secret-manager-value>
```

Auth and OAuth:

```bash
OPENMYND_REQUIRE_REGISTRATION_EMAIL=true
EMAIL_PROVIDER=smtp
EMAIL_FROM_ADDRESS=OpenMynd <no-reply@openmynd.app>
SMTP_HOST=<smtp-host>
SMTP_PORT=587
SMTP_USERNAME=<secret-manager-value>
SMTP_PASSWORD=<secret-manager-value>
SMTP_USE_TLS=true
OAUTH_GOOGLE_CLIENT_ID=<google-client-id>
OAUTH_GOOGLE_CLIENT_SECRET=<secret-manager-value>
OAUTH_GOOGLE_REDIRECT_URI=https://api.openmynd.app/api/oauth/google/callback
```

Rate limits:

```bash
AUTH_LOGIN_RATE_LIMIT=10 per minute
AUTH_REGISTER_RATE_LIMIT=5 per hour
AUTH_PASSWORD_RESET_RATE_LIMIT=5 per hour
AUTH_EMAIL_VERIFICATION_RATE_LIMIT=5 per hour
AUTH_OAUTH_START_RATE_LIMIT=20 per minute
AUTH_OAUTH_CALLBACK_RATE_LIMIT=20 per minute
ANALYSE_RATE_LIMIT=30 per hour
IMPORT_UPLOAD_RATE_LIMIT=20 per hour
IMPORT_COMMIT_RATE_LIMIT=30 per hour
IMPORT_JOB_RATE_LIMIT=30 per hour
IMPORT_REVERT_RATE_LIMIT=10 per hour
EXPORT_RATE_LIMIT=20 per hour
ACCOUNT_DELETE_RATE_LIMIT=5 per hour
SECURITY_AUDIT_RETENTION_DAYS=180
```

Temporary owner decisions, if accepted for public beta:

```bash
OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK=true
OPENMYND_ACCEPT_LEGACY_PASSWORD_FALLBACK=true
```

These are not ideal long-term settings. They document accepted residual risk until the
session/auth redesign and legacy password cleanup are complete.

## Media Storage Direction

Keep the current local media abstraction for local development and private rehearsal.
Before public launch, add an R2/S3-compatible backend to the existing media storage
service so stored keys remain stable and the provider can change later.

Do not store image or attachment bytes in Postgres.

## Monitoring And Backups

Minimum public-beta operations:

- platform request/error logs enabled
- production preflight result captured per deploy
- scheduled database backup bundle
- scheduled Postgres snapshot after cutover
- media archive or object-store replication policy
- restore rehearsal evidence checked with `validate_database_maintenance.py`
- security audit report available to the operator

## Rejected Alternatives

### All-in-one AWS

Rejected for now because account access/support issues are blocking. AWS can be revisited
later without changing the app architecture if it enters through standard Postgres,
object storage, SMTP, and environment-secret contracts.

### SQLite in production

Rejected for public SaaS except as a documented emergency rollback window. It is not
suitable for public multi-user hosted operation.

### Stripe as the permission system

Rejected. Stripe should report billing events. OpenMynd should own entitlements and
feature gates locally.

## Consequences

- The app has a concrete deployable architecture without requiring a full platform
  rewrite.
- The frontend `/api` path must be handled deliberately through proxy/rewrite rules.
- Render/Neon/Cloudflare/Vercel each remain replaceable behind standard contracts.
- Billing implementation can proceed after the entitlement schema exists.
- Public launch remains blocked until legal, auth/session, backups, and E2E gates are
  complete.
