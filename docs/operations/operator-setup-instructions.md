# Operator Setup Instructions

Updated: 13 August 2026

Purpose: this is the practical checklist for configuring OpenMynd while development
continues. Do not paste real secrets into this document.

## Local Run Commands

Run these in two separate terminals from the repository root.

Server:

```bash
cd server
source venv/bin/activate
python -m flask --app app.py --debug run -p 5001
```

Client:

```bash
cd client
npm start
```

## SMTP Email Setup

Use SMTP for verification emails, password reset, and admin test email.

Choose a provider first. Suitable options include Postmark, SendGrid, Mailgun, Amazon
SES, Google Workspace SMTP, or another standard SMTP provider.

Add this to `server/.env`:

```bash
EMAIL_PROVIDER=smtp
EMAIL_FROM_ADDRESS="OpenMynd <no-reply@yourdomain.com>"
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_USE_TLS=true
OPENMYND_REQUIRE_REGISTRATION_EMAIL=true
FRONTEND_BASE_URL=http://localhost:4200
```

For production, replace `FRONTEND_BASE_URL` with the real HTTPS frontend URL:

```bash
FRONTEND_BASE_URL=https://your-openmynd-domain.com
```

Smoke test:

1. Restart the server.
2. Log in as an admin.
3. Open avatar menu -> Admin -> Operations.
4. Confirm the Email card is ready or shows a clear missing setting.
5. Use Send test email.
6. Confirm the email arrives.

If Send test fails, check:

- SMTP host and port.
- SMTP username/password.
- Sender address verified with the provider.
- Provider sandbox mode or domain verification.
- Firewall/network blocks from the server environment.

## Shared Rate Limiting

Local development can use:

```bash
RATELIMIT_STORAGE_URI=memory://
```

Public production must use shared storage, normally Redis:

```bash
RATELIMIT_STORAGE_URI=redis://username:password@host:6379/0
```

Why this matters: `memory://` only protects one Python process. Multiple production
workers would each have separate counters.

Smoke test:

1. Set `APP_ENV=production` and leave `RATELIMIT_STORAGE_URI=memory://`.
2. Server startup should fail closed.
3. Set a Redis URL.
4. Admin -> Operations -> Production preflight should no longer report memory limiter
   storage as the blocker.

## Neon/Postgres Setup

Required env for a Postgres rehearsal or cutover:

```bash
DATABASE_PROVIDER=postgres
DATABASE_URL=postgresql://...
DATABASE_USES_POOLER=true
```

For Neon, use the pooled connection string where possible. Keep SQLite as the local
fallback until the cutover issue is deliberately signed off.

Production preflight:

```bash
cd server
source venv/bin/activate
APP_ENV=production PYTHONPATH=. python scripts/validate_production_preflight.py --require-postgres
```

Do not run destructive Postgres reset/import commands against a live database unless
that is the explicit cutover rehearsal being performed.

## Backup And Restore Evidence

Admin -> Operations -> Database maintenance reads backup evidence from these locations
unless overridden by env vars:

- backup summary: `~/OpenMyndBackups`
- SQLite backup manifests: `~/OpenMyndBackups`
- Postgres snapshot manifests: `~/OpenMyndBackups/postgres-snapshots`
- media backup manifests: `~/OpenMyndBackups/media`
- restore report: set with `OPENMYND_RESTORE_REPORT`

Optional env overrides:

```bash
OPENMYND_BACKUP_SUMMARY_DIR=~/OpenMyndBackups
OPENMYND_SQLITE_BACKUP_DIR=~/OpenMyndBackups
OPENMYND_POSTGRES_SNAPSHOT_DIR=~/OpenMyndBackups/postgres-snapshots
OPENMYND_MEDIA_BACKUP_DIR=~/OpenMyndBackups/media
OPENMYND_RESTORE_REPORT=~/OpenMyndBackups/restored-sqlite/latest-restore-report.json
```

Manual validation:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/validate_database_maintenance.py \
  --backup-summary-dir ~/OpenMyndBackups \
  --sqlite-backup-dir ~/OpenMyndBackups \
  --postgres-snapshot-dir ~/OpenMyndBackups/postgres-snapshots \
  --media-backup-dir ~/OpenMyndBackups/media \
  --restore-report ~/OpenMyndBackups/restored-sqlite/latest-restore-report.json \
  --require-postgres-snapshot \
  --require-media-archive \
  --require-restore-rehearsal
```

## Google OAuth Setup

In Google Cloud Console:

1. Create or open the OAuth client.
2. Add local callback:
   `http://localhost:5001/api/oauth/google/callback`
3. Add production callback later:
   `https://your-api-domain.com/api/oauth/google/callback`
4. Add local frontend origin:
   `http://localhost:4200`
5. Add production frontend origin later:
   `https://your-openmynd-domain.com`

Server env:

```bash
OAUTH_GOOGLE_CLIENT_ID=...
OAUTH_GOOGLE_CLIENT_SECRET=...
OAUTH_GOOGLE_REDIRECT_URI=http://localhost:5001/api/oauth/google/callback
FRONTEND_BASE_URL=http://localhost:4200
```

## Stripe Setup

Use Stripe test mode first.

Server env:

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PERSONAL_MONTHLY=price_...
STRIPE_PRICE_PERSONAL_ANNUAL=price_...
STRIPE_PRICE_PLUS_MONTHLY=price_...
STRIPE_PRICE_PLUS_ANNUAL=price_...
```

Expected model:

- Stripe owns payment collection, invoices, subscription lifecycle, and customer portal.
- OpenMynd stores a local entitlement cache.
- Product gates read OpenMynd entitlements, not live Stripe calls.
- Manual admin overrides remain possible from Admin.

Smoke test:

1. Admin -> Operations -> Stripe should show configured.
2. Account/Billing should show current plan and available billing action.
3. Upgrade should open Stripe Checkout in test mode.
4. Stripe webhook should update local entitlements.
5. Customer Portal should open for an existing Stripe customer.

## Admin Operations Smoke Test

After changing any setup:

1. Restart server.
2. Log in as admin.
3. Open Admin -> Operations.
4. Run Production preflight.
5. Toggle Require Postgres and run again.
6. Run Database maintenance.
7. Toggle Require launch evidence and run again.
8. Send a test email.

Expected local result: warnings are acceptable. Crashes, unreadable errors, or missing
cards are not acceptable.

## Issues To Keep Open

Keep these categories open until the listed evidence exists:

- Public readiness/auth hardening: cookie-only cutover still needs explicit owner approval.
- Neon/Postgres cutover: keep open until rehearsal and cutover evidence exists.
- Database backup/maintenance: keep open until scheduled backups and restore rehearsals
  are proven.
- Stripe production billing: keep open until Stripe test/live checkout, webhooks, and
  customer portal are proven.
- Legal/privacy/cookie policy: keep open until final public wording is reviewed.
- UX polish: keep the standing polish issue open for consistency sweeps.

Close completed narrow issues for:

- Admin SMTP test email.
- Admin email readiness visibility.
- Admin production preflight visibility.
- Admin database maintenance visibility.
- Admin security audit visibility/filtering.
- Admin audit trail.
