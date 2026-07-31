# Cloud Database Cutover Checklist

## Purpose

Use this checklist before switching OpenMynd from local SQLite to managed Postgres. Do
not cut over until every required gate is complete and the readiness validator returns
`ready_for_cutover: true`.

## Required Environment

- `DATABASE_URL`: Postgres connection string for the target environment.
- `DATABASE_PROVIDER`: explicit runtime provider switch. Keep `sqlite` until the
  Postgres runtime adapter has landed; `DATABASE_URL` alone is rehearsal metadata.
- `DATABASE_USES_POOLER`: set to `true` only after confirming the configured Postgres URL
  uses provider pooling. Pooled hostnames are detected automatically when obvious.
- `DB_PATH`: retained only for SQLite source/fallback during migration.
- `JWT_SECRET`: production secret configured.
- `MEDIA_ROOT` / media backend config: points at the active media store.
- `RATELIMIT_STORAGE_URI`: shared limiter backend such as Redis; `memory://` is local
  development only.
- `OPENAI_API_KEY`: configured only in the backend environment.
- `CORS_ORIGINS`: production frontend origin.
- `OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK`: leave `false` except during an explicitly
  documented emergency rollback window.
- `OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION`: leave `false` except during an
  explicitly documented emergency SQLite fallback window.

## Pre-Cutover Gates

1. Create a timestamped SQLite backup with `scripts/create_sqlite_backup.py` and keep it
   outside the repo.
2. Run SQLite migration audit and confirm:
   - no expected tables are missing
   - no orphan rows are reported
   - no legacy inline image payloads remain
   - no attachment rows have empty storage keys
3. Export JSONL rows from the same SQLite file used for the audit.
4. Dry-run the Postgres load plan and confirm the manifest, total row count, and
   per-table row counts match the audit report.
5. Apply the export to a disposable Postgres rehearsal database or Neon branch.
6. Run production/cloud environment preflight checks.
7. Run cloud schema/export parity checks.
8. Run the runtime SQLite usage audit and confirm product routes/services use the
   database adapter rather than direct SQLite connections.
9. Run backend regression tests against the current local app baseline.
10. Run frontend lint and production build.
11. Run manual smoke against the rehearsal database before production cutover.
12. Generate the cloud parity report and confirm `parity_ready: true`.

## Commands

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_sqlite_backup.py \
  --source-db db/app.db \
  --backup-dir ~/AIDiaryBackups \
  --label pre-cutover \
  --retain 14
```

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/rehearse_cloud_migration.py \
  --source-db db/app.db \
  --export-dir /tmp/aidiary-cloud-export \
  --report-json /tmp/aidiary-cloud-migration-report.json
```

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-cloud-export
```

```bash
cd server
source venv/bin/activate
APP_ENV=production \
JWT_SECRET="replace-with-real-secret" \
DATABASE_PROVIDER=postgres \
DATABASE_URL="postgresql://..." \
DATABASE_USES_POOLER=true \
CORS_ORIGINS="https://your-frontend.example" \
MEDIA_ROOT="/var/lib/openmynd/media" \
RATELIMIT_STORAGE_URI="redis://..." \
OPENAI_API_KEY="sk-..." \
PYTHONPATH=. python scripts/validate_production_preflight.py --require-postgres
```

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/audit_runtime_sqlite_usage.py --repo-root ..
```

```bash
cd server
source venv/bin/activate
PYTHONPATH=. pytest tests/test_cloud_schema_parity.py \
  tests/test_cloud_migration_rehearsal.py \
  tests/test_cloud_cutover_readiness.py
```

```bash
cd server
source venv/bin/activate
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-cloud-export \
  --apply \
  --reset-first
```

```bash
cd server
source venv/bin/activate
PYTHONPATH=. pytest
```

```bash
cd client
npm run lint
npm run build
npm run test:e2e:smoke
npm run test:e2e:a11y
```

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/validate_cloud_cutover_readiness.py \
  --migration-report /tmp/aidiary-cloud-migration-report.json \
  --export-dir /tmp/aidiary-cloud-export \
  --repo-root .. \
  --backend-tests-passed \
  --frontend-lint-passed \
  --frontend-build-passed \
  --postgres-rehearsal-loaded
```

The readiness report must not contain `jsonl_export_manifest`,
`jsonl_export_row_count`, or `jsonl_export_table_counts` blockers before cutover.

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_cloud_parity_report.py \
  --readiness-report /tmp/aidiary-local-cutover-rehearsal/cutover-readiness.json \
  --postgres-target "neon/rehearsal-branch" \
  --backend-tests-passed \
  --frontend-lint-passed \
  --frontend-build-passed \
  --frontend-smoke-passed \
  --frontend-a11y-passed \
  --manual-rehearsal-smoke-passed \
  --output-json /tmp/aidiary-cloud-parity-report.json \
  --output-md /tmp/aidiary-cloud-parity-report.md
```

The parity report must return `parity_ready: true` before moving to the cutover runbook.

## Manual Parity Smoke

- Auth:
  - login succeeds
  - logout clears session
  - protected routes reject unauthenticated requests
- Entries:
  - create, edit, view, and delete Daily entry
  - create, edit, view, and delete Dream entry
  - tags, people, places, dates, and entry times persist
- Calendar and cards:
  - Diary, Dream, Thought Record, Important Day, and On This Day filters work
  - monthly shelves and popouts open/close correctly
  - dark/light mode remains usable
- Media and attachments:
  - entry hero images resolve from storage keys
  - important-day images resolve
  - attachment open/download works
  - PDF derived text remains available
- Import/export:
  - package export succeeds
  - import review does not insert before confirmation
  - import history and background job state are visible
- AI:
  - Daily analysis succeeds
  - Dream analysis succeeds
  - attachment context can be referenced when enabled
  - reflection summaries generate
- Chat:
  - chat sends and streams a response
  - chat history reloads
  - observability report returns lifecycle counts
- Reminders and rhythm:
  - writing reminder settings save
  - rhythm progress panel renders when enabled

## Rollback Triggers

Roll back immediately if any of these happen during cutover validation:

- login or registration fails for valid accounts
- entry counts do not match the rehearsal report
- attachment/media references are missing for existing records
- import history or import jobs are not recoverable
- chat or AI analysis fails due to database errors
- p95 page/API latency is materially worse than the SQLite baseline

## Rollback Procedure

1. Stop writes to the Postgres-backed deployment.
2. Restore the previous backend configuration using `DB_PATH`.
   - if `APP_ENV=production`, set `OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK=true`
     and `OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION=true` only for the rollback
     window
3. Restart backend workers.
4. Verify login, entry list, calendar, and export.
5. Preserve the failed Postgres database for comparison; do not truncate it until the
   failure is understood.

## Sign-Off

Record the final migration report path, export directory, runtime SQLite audit result,
target Postgres branch/database, test command outputs, manual smoke result, cutover
time, and rollback owner before go-live.
