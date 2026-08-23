# OpenMynd Pause Handoff

Updated: 23 August 2026

## Current working state

OpenMynd is paused after the search/import-export/account-media/calendar polish batch.
The active branch is `feat/search-import-export-polish`; its final merge commit is the
state to resume from. The private hosted route is a root-level Vercel project using the
Flask function in `api/index.py`, Angular client, Neon Postgres, and R2 media storage.

## Completed in the final batch

- Polished search, create, import/export, and account media review flows, including
  stable test hooks and Material dialogs.
- Reused the shared entry image gallery for Important Days and calendar previews.
- Fixed calendar day capacity: diary and dream records retain priority; the front face
  fills before a public holiday or other lower-priority item moves to the back.
- Moved the calendar's hidden-by-filters indicator into the utility area so it does not
  overlap entry actions in narrow layouts.
- Removed an obsolete ignored NLTK scratch script tied to the old `aidiary2025`
  checkout, disposable caches/build output, and the unsafe ignore rule that could hide
  future `server/test_*.py` files.

## Deliberately deferred

No public-SaaS, subscription, payment, mobile, therapist, or wider productisation work
was started. Keep the public-platform roadmap and its unresolved operating controls in
`docs/roadmap.md`, `docs/operations/public-saas-readiness-plan.md`, and ADR 0005.

The hosted Vercel function remains a private-use rehearsal, not an approved public API
platform. Public launch still needs the documented shared rate limiting, email,
cookie/session, backup/restore, long-running-job, media, security, and operational
evidence.

## Deployment and database state

- Root `vercel.json` builds the Angular app and routes `/api`, `/media`, and `/health`
  to `api/index.py`; deploy the repository root, not `client`.
- On 23 August 2026, `https://openmynd.vercel.app/health` and
  `https://openmynd.vercel.app/api/health/database` both returned HTTP 200. Database
  health reported a production Vercel function using Postgres and R2, with a successful
  read check. That deployment reported source SHA `0647ab732362` before this final
  merge; after a new deployment, confirm the reported SHA is the merge commit.
- No Vercel CLI project link or Neon connection string is stored in this checkout.
  Vercel project settings and Neon credentials remain external. Do not add them to Git.
- Explicit Postgres migrations live in `server/migrations/postgres/` through
  `0009_repair_entry_search_schema.sql`. Apply them from a trusted machine before a
  fresh deployment; Vercel startup currently reports no pending migrations.

Required hosted environment-variable names (set values only in the provider secret
manager): `APP_ENV`, `JWT_SECRET`, `DATABASE_PROVIDER`, `DATABASE_URL`,
`DATABASE_USES_POOLER`, `CORS_ORIGINS`, `FRONTEND_BASE_URL`,
`MEDIA_STORAGE_BACKEND`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL`, `MEDIA_BASE_URL`,
`RATELIMIT_STORAGE_URI`, `OPENMYND_DEFER_SHARED_RATE_LIMITING`, `EMAIL_PROVIDER`,
`OPENMYND_DEFER_EMAIL_DELIVERY`, and `OPENMYND_REQUIRE_REGISTRATION_EMAIL`.
Optional features additionally use the names in `.env.example` and `server/.env.example`
(OAuth, OpenAI, Stripe, SMTP, backups, and hardening flags).

## Verification and smoke path

Run locally from the repository root:

```bash
cd server && source venv/bin/activate && PYTHONPATH=. pytest
cd client && npm run lint && npm run build
cd client && npm run test:e2e:smoke && npm run test:e2e:a11y
```

For the deployed private-use smoke path, log in using the existing authentication flow,
create one normal Daily entry and one Dream entry, refresh/search/reopen both, then
confirm they remain after the deployment check. Do not use production credentials in
the repository or automated browser fixtures. Also verify a date with a public holiday
but fewer than five visible metric types stays on the calendar front, and narrow the
calendar until the hidden-by-filters status remains separate from entry controls.

## Known issues and tracking

- `npm run test:e2e:a11y` currently fails on pre-existing broad accessibility and
  fixture-expectation issues (for example unnamed loading spinners, account form labels,
  and stale login/registration/create headings). This pause does not expand into that
  unrelated remediation; inspect the generated Playwright artifacts when resuming.
- The current checkout has no provider credentials, so it cannot independently run the
  Neon migration command or authenticated live entry smoke without external operator
  access.
- GitHub issue `#137` remains the open platform-polish umbrella; the current batch is
  not a reason to close it. Other public-platform and cloud-cutover work remains in the
  roadmap and GitHub issues, intentionally untouched.
- The unrelated linked worktree `../openmynd-dashboard-v1` is preserved and was not
  merged or changed by this pause.

## Safest next priority

Before any major roadmap phase, perform the authenticated Vercel + Neon save/retrieve
and retention smoke against the final deployed SHA, then record its outcome. If it is
green, recover the deferred public-platform roadmap and choose one explicitly approved,
bounded issue rather than starting a broad productisation batch.

## RESUME PROMPT

Read `AGENTS.md`, `docs/PAUSE_HANDOFF.md`, and the relevant current project docs. Inspect
`git status --short --branch` and recent history, then verify the current application
before changing it. Recover the deferred public-platform roadmap and tell me concisely
where the project stands and the single best next task. Wait for my direction before
starting any major new phase.
