# OpenMynd Pause Handoff

Updated: 23 August 2026

## Current working state

OpenMynd is paused on `main` after the private-use Vercel/Neon import recovery and
the earlier search, create, import/export, account-media, and calendar polish work.
The latest application commit before this handoff is `5d31da3`.

The private hosted app is a root-level Vercel project: Angular is built from `client`,
and Flask is served by `api/index.py` under same-origin `/api`, `/media`, and `/health`
routes. Persistent data is Neon Postgres; hosted media is Cloudflare R2.

## Completed

- Search/create, import/export, account media-review, and calendar polish were
  completed and user smoke-tested.
- Calendar capacity now prioritises diary and dream items on the front of a day card;
  lower-priority public holidays use the back only after the front is occupied.
- The narrow calendar hidden-by-filters control no longer overlaps entry actions.
- Vercel import reliability was repaired for Postgres dictionary rows in both preview
  and commit paths, including `MAX(entry_number)` allocation.
- Reviewed imports run synchronously inside the Vercel request. Browser status polling
  no longer overlaps slow requests, and an orphaned Vercel job stops rather than polling
  indefinitely.
- A 2.1 MB, 1,173-entry hosted import completed successfully after these fixes.

## Deliberately deferred

Do not start public SaaS, payments, subscriptions, mobile, therapist, or broader
productisation work without a new explicit direction. Preserve that roadmap in
`docs/roadmap.md`, `docs/operations/public-saas-readiness-plan.md`, and ADR 0005.

The Vercel function is suitable for current private use, not the approved public API
architecture. Long-running AI/OCR/import work, shared rate limiting, transactional
email, backups/restores, security evidence, and public launch operations remain
deferred.

## Vercel, Neon, and migrations

- On 23 August 2026, `/health` and `/api/health/database` returned HTTP 200. The latter
  reported production Vercel, Postgres, R2, and source SHA `5d31da3881d4` before this
  documentation commit. After any deploy, verify the health SHA again.
- `vercel.json` deliberately uses legacy `builds`; do not add a `functions` property,
  because Vercel rejects that combination.
- Postgres migrations are explicit in `server/migrations/postgres/` through
  `0009_repair_entry_search_schema.sql`. Hosted runtime migrations are disabled; apply
  migrations from a trusted machine with `server/scripts/run_postgres_migrations.py
  --apply` before a fresh database/deployment. The health endpoint's
  `startup_migrations.applied_count: 0` means no migration ran at function startup; it
  is not a migration-ledger audit.
- No Vercel CLI project link, Neon URL, R2 credential, or production secret is stored
  in this checkout.

Required private-hosted environment-variable names (never commit values):
`APP_ENV`, `JWT_SECRET`, `DATABASE_PROVIDER`, `DATABASE_URL`,
`DATABASE_USES_POOLER`, `OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION`,
`CORS_ORIGINS`, `FRONTEND_BASE_URL`, `MEDIA_STORAGE_BACKEND`, `R2_ENDPOINT_URL`,
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL`,
`MEDIA_BASE_URL`, `RATELIMIT_STORAGE_URI`, `OPENMYND_DEFER_SHARED_RATE_LIMITING`,
`EMAIL_PROVIDER`, `OPENMYND_DEFER_EMAIL_DELIVERY`, and
`OPENMYND_REQUIRE_REGISTRATION_EMAIL`. Optional OAuth, OpenAI, Stripe, SMTP, backup,
and hardening variables are documented in `.env.example` and `server/.env.example`.

## Verification

From the repository root:

```bash
cd server && source venv/bin/activate && PYTHONPATH=. pytest
cd client && npm run lint && npm run build
cd client && npm run test:e2e:smoke
```

The release-boundary accessibility command remains `cd client && npm run test:e2e:a11y`.
It has pre-existing broad accessibility/fixture failures; do not treat it as green
without addressing those separately. Use `AGENTS.md` for local server commands.

Hosted checks performed before this handoff: unauthenticated `/health` and database
health returned 200; the operator completed the real large import. The checkout has no
production account credentials, so it cannot independently perform authenticated live
smoke tests.

Manual smoke still worth recording after the final deploy: log in, create one Daily and
one Dream entry, refresh/search/reopen both, and confirm they remain after a subsequent
deployment. Do not put production credentials or diary data in the repository.

## Audit and tracking

- Ignored Playwright output and Python caches are disposable; local `.env` files,
  databases, media, virtual environments, editor settings, and historical handovers
  were preserved. `.gitignore` already covers the generated output and sensitive local
  paths.
- No tracked environment file or obvious private-key marker was found in the text scan.
  The tracked historical `server/db/app.db.backup_20250923_140735` was preserved without
  inspection because it may contain user data; classify/remove it only with owner
  approval.
- GitHub was checked through the public API on 23 August 2026. Relevant open issues:
  `#138` Vercel/Neon rehearsal, `#141` personal database upload/cutover rehearsal,
  `#122` personal XLSX import rehearsal, `#120` backup/restore strategy, `#125` E2E
  release gates, and `#137` platform-polish triage. Public-platform milestones `#15`,
  `#16`, `#18`, and `#21` remain open and intentionally deferred.

## Safest next priority

Before reopening a roadmap phase, record the authenticated Vercel/Neon Daily + Dream
create/retrieve/refresh/retention smoke against the final deployed SHA. Then review the
deferred public-platform roadmap and select one explicitly approved bounded issue.

## RESUME PROMPT

Read `AGENTS.md`, `docs/PAUSE_HANDOFF.md`, and relevant current project documentation.
Inspect `git status --short --branch` and recent history, then verify the current
application before changing it. Recover the deferred public-platform roadmap and tell
me concisely where the project stands and the single best next task. Wait for my
direction before starting a major new phase.
