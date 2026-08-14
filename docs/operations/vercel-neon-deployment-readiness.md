# Vercel And Neon Deployment Readiness

Updated: 14 August 2026

Purpose: prepare OpenMynd for an initial hosted deployment without weakening the
production hardening already added for public readiness.

## Recommended First Deployment Shape

Use Vercel for the Angular frontend first.

Use a separate Python-capable backend host for Flask until the API has been deliberately
adapted for serverless constraints. Suitable backend hosts include Render, Fly.io,
Railway, a small VPS, or another always-on Python service.

Use Neon as the hosted Postgres database.

Do not rely on Vercel local filesystem persistence for OpenMynd media, imports, OCR
assets, backups, or restore evidence. Vercel can run Flask through Python functions, but
that is a stateless/serverless shape and is not the same operational model as the current
Flask app.

## Why Not Full Flask On Vercel First

The current backend expects operational behaviours that are better suited to an
always-on API service:

- authenticated file uploads and generated images
- media reads through `/media/...`
- import jobs and background progress notifications
- OCR/PDF processing
- database backup/restore evidence checks
- rate-limiting storage outside process memory

Before placing the Flask API on Vercel Functions, we would need a dedicated serverless
adaptation pass:

- move all media to object storage, such as S3/R2/Supabase Storage
- replace filesystem backup evidence with external backup evidence
- ensure long-running import/OCR work uses a durable external queue
- confirm Vercel function limits are compatible with image/PDF/OCR workloads

## Frontend On Vercel

Create a Vercel project with:

- Root Directory: `client`
- Framework Preset: Angular or Other
- Build Command: `npm run build:vercel`
- Output Directory: `dist/openmynd`

Set Vercel environment variables:

```bash
OPENMYND_API_BASE_URL=https://your-api-domain.com/api
OPENMYND_API_FALLBACK_BASE_URL=https://your-api-domain.com/api
OPENMYND_COOKIE_ONLY_AUTH=false
OPENMYND_INACTIVITY_TIMEOUT_SECONDS=900
OPENMYND_INACTIVITY_WARNING_SECONDS=60
```

`client/scripts/write-vercel-environment.mjs` writes Angular's hosted environment
(`environment.hosted.ts`) during the Vercel build so the API domain does not need to be
committed into source. Normal local and production builds remain unchanged.

`client/vercel.json` keeps Angular browser routes working on refresh.

If the frontend and backend later share one domain with an API reverse proxy, keep
`OPENMYND_API_BASE_URL=/api`.

## Backend Host Requirements

The backend host must support:

- Python 3 with `server/requirements.txt`
- an always-on Flask/Gunicorn or equivalent process
- HTTPS
- env vars
- outbound HTTPS to OpenAI, Stripe, Google, SMTP, and Neon
- a persistent media directory or object storage integration
- Redis or another shared rate-limit backend for public launch
- scheduled backup/maintenance commands

Minimum backend env shape:

```bash
APP_ENV=production
JWT_SECRET=<strong 32+ char secret>
DATABASE_PROVIDER=postgres
DATABASE_URL=<Neon pooled connection string>
DATABASE_USES_POOLER=true
OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION=false
CORS_ORIGINS=https://your-vercel-frontend.vercel.app,https://your-domain.com
FRONTEND_BASE_URL=https://your-domain.com
MEDIA_ROOT=/var/lib/openmynd/media
MEDIA_BASE_URL=https://your-api-domain.com/media
RATELIMIT_STORAGE_URI=redis://...
OPENMYND_DEFER_SHARED_RATE_LIMITING=false
EMAIL_PROVIDER=smtp
OPENMYND_REQUIRE_REGISTRATION_EMAIL=true
```

Recommended Render start command:

```bash
bash scripts/start_render.sh
```

The wrapper applies pending Postgres migrations when `DATABASE_PROVIDER=postgres`, then
starts Gunicorn. This prevents a fresh Neon database from deploying successfully but
failing login with `UndefinedTable`.

For a private Render + Neon non-media storage rehearsal where email and shared rate
limiting are intentionally deferred, use this temporary block instead:

```bash
RATELIMIT_STORAGE_URI=memory://
OPENMYND_DEFER_SHARED_RATE_LIMITING=true
EMAIL_PROVIDER=console
OPENMYND_DEFER_EMAIL_DELIVERY=true
OPENMYND_REQUIRE_REGISTRATION_EMAIL=false
```

That mode is for proving user accounts and non-media entries can be stored and recalled
from Neon. It is not public-launch ready because verification, password recovery, and
distributed rate limiting are disabled/deferred.

Run before deployment:

```bash
cd server
source venv/bin/activate
APP_ENV=production PYTHONPATH=. python scripts/validate_production_preflight.py --require-postgres
```

## Neon Readiness

Neon is appropriate for the database cutover because OpenMynd already supports standard
Postgres through `DATABASE_PROVIDER=postgres` and `DATABASE_URL`.

Use the Neon pooled connection string for app runtime, with `sslmode=require`.

Keep backup expectations explicit:

- Neon free/entry plans provide limited point-in-time recovery and snapshot capability.
- App-level export/backup still matters because PITR is not the same as a portable user
  export or media backup.
- Media files are not in Neon; they need separate storage and backup.

Before using Neon for real users:

1. Create a clean Neon branch/database.
2. Run a schema/bootstrap migration rehearsal.
3. Import a copy of local test data only.
4. Run backend tests against `DATABASE_PROVIDER=postgres`.
5. Run production preflight with `--require-postgres`.
6. Create and verify a Neon restore point/snapshot.
7. Run an OpenMynd export package and verify it imports into a clean account.

## Deployment Smoke Test

After frontend and backend are deployed:

1. Visit `/login` directly on Vercel.
2. Refresh `/dashboard`, `/entries`, `/settings/account`, and `/onboarding`.
3. Register a test account.
4. Log in with Google.
5. Create Daily, Dream, Thought Record, and Important Day records.
6. Upload an attachment and confirm it survives backend restart.
7. Generate an AI response.
8. Run import preview with a small file.
9. Export all data.
10. Open Admin -> Operations and confirm readiness cards reflect the hosted config.

## Current Decision

Proceed with frontend-on-Vercel readiness now.

Do not deploy the current Flask backend to Vercel Functions as the primary public API
until media storage, durable jobs, and backup evidence have been moved off local
filesystem assumptions.
