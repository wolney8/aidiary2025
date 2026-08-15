# Vercel And Neon Deployment Readiness

Updated: 14 August 2026

Purpose: prepare OpenMynd for an initial hosted deployment without weakening the
production hardening already added for public readiness.

## Recommended First Deployment Shape

Use Vercel for the Angular frontend first. A single-project Vercel rehearsal is now
available for testing the Flask API through Vercel Python Functions, backed by Neon and
Cloudflare R2.

Keep a separate Python-capable backend host such as Render, Fly.io, Railway, or a small
VPS as the fallback path until the Vercel serverless rehearsal has passed real smoke
tests.

Use Neon as the hosted Postgres database.

Do not rely on Vercel local filesystem persistence for OpenMynd media, imports, OCR
assets, backups, or restore evidence. Vercel can run Flask through Python functions, but
that is a stateless/serverless shape and is not the same operational model as an
always-on Flask process.

## Single-Project Vercel Rehearsal

Root-level Vercel support exists for a controlled rehearsal:

- `api/index.py` imports the existing Flask app factory.
- root `requirements.txt` forwards to `server/requirements.txt`.
- root `vercel.json` builds `client`, serves Angular, and routes `/api`, `/media`, and
  `/health` to the Flask function.

Create the Vercel project from the repository root, not from `client`, when testing this
single-project shape.

Suggested Vercel project settings:

- Framework Preset: Other
- Root Directory: repository root
- Install Command: use `vercel.json`
- Build Command: use `vercel.json`
- Output Directory: use `vercel.json`

Required rehearsal env:

```bash
APP_ENV=production
JWT_SECRET=<strong 32+ char secret>
DATABASE_PROVIDER=postgres
DATABASE_URL=<Neon pooled connection string>
DATABASE_USES_POOLER=true
OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION=false
CORS_ORIGINS=https://your-vercel-project.vercel.app
FRONTEND_BASE_URL=https://your-vercel-project.vercel.app
MEDIA_STORAGE_BACKEND=r2
R2_ENDPOINT_URL=https://<cloudflare-account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<cloudflare-r2-access-key-id>
R2_SECRET_ACCESS_KEY=<cloudflare-r2-secret-access-key>
R2_BUCKET_NAME=openmynd-media
R2_PUBLIC_BASE_URL=
MEDIA_BASE_URL=https://your-vercel-project.vercel.app/media
RATELIMIT_STORAGE_URI=memory://
OPENMYND_DEFER_SHARED_RATE_LIMITING=true
EMAIL_PROVIDER=console
OPENMYND_DEFER_EMAIL_DELIVERY=true
OPENMYND_REQUIRE_REGISTRATION_EMAIL=false
```

Before first deploy, apply the Postgres migrations from a trusted local/admin machine:

```bash
cd server
source venv/bin/activate
DATABASE_URL="<Neon pooled connection string>" \
PYTHONPATH=. python scripts/run_postgres_migrations.py --apply
```

This is a private rehearsal profile, not a public-launch profile. Public launch still
needs shared rate limiting, email delivery, Stripe evidence, and backup/restore evidence.

## Why Vercel API Remains A Rehearsal First

The backend still has operational behaviours that are usually better suited to an
always-on API service or a separate worker:

- authenticated file uploads and generated images
- media reads through `/media/...`
- import jobs and background progress notifications
- OCR/PDF processing
- database backup/restore evidence checks
- rate-limiting storage outside process memory

Before making Vercel Functions the primary production API, prove:

- media works through R2
- explicit migrations run cleanly before deploy
- long-running import/OCR work behaves within serverless limits or moves to a durable
  worker path
- backup evidence comes from Neon/R2/export evidence, not Vercel filesystem state
- rate limiting uses a shared provider before public launch

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
MEDIA_STORAGE_BACKEND=r2
R2_ENDPOINT_URL=https://<cloudflare-account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<cloudflare-r2-access-key-id>
R2_SECRET_ACCESS_KEY=<cloudflare-r2-secret-access-key>
R2_BUCKET_NAME=openmynd-media
R2_PUBLIC_BASE_URL=
MEDIA_ROOT=
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

For the first private Vercel + Render + Neon rehearsal, R2 can proxy through the API by
leaving `R2_PUBLIC_BASE_URL` blank and setting `MEDIA_BASE_URL` to
`https://your-render-service.onrender.com/media`. For public launch, prefer a public or
custom R2 media URL in `R2_PUBLIC_BASE_URL` so media does not stream through the API.

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

Proceed with a single-project Vercel + Neon + R2 private rehearsal.

Do not treat Vercel Functions as the final public API architecture until login, entry
save/load, R2 media, import review, backup evidence, and long-running AI/OCR/import paths
have passed hosted smoke tests.

Keep Render or another always-on Python host as the fallback architecture until that
evidence exists.
