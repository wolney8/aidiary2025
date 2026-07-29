# Cloud Migration Rehearsal

## Purpose

Use this process before any SQLite-to-Postgres cutover. It is designed to be
non-destructive until the explicit Postgres `--apply` step.

## Current `#28` Status

Local dry-run tooling is in place and was rerun successfully on 29 July 2026. The local
bundle produced a SQLite audit, JSONL export, manifest validation, load plan, runtime
SQLite usage audit, readiness report, and operator summary. The dry-run gates showed:

- source/export row counts match
- export manifest is valid
- no Postgres schema column mismatches were reported by the load plan
- no orphan rows were reported by the SQLite audit
- runtime SQLite usage audit passed
- backend tests, frontend lint, and frontend build evidence were recorded in the local
  readiness bundle

The remaining `#28` blocker is not local tooling; it is the first disposable Postgres
rehearsal load against a real `DATABASE_URL`. Run the Postgres steps below against a
throwaway Neon branch or equivalent managed Postgres database before closing `#28`.

## Fast Local Rehearsal Bundle

Run this first when you want a single local artifact set before touching a cloud
database:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/run_local_cutover_rehearsal_bundle.py \
  --source-db db/app.db \
  --work-dir /tmp/aidiary-local-cutover-rehearsal \
  --overwrite
```

This writes:

- migration audit report
- JSONL table export
- export `manifest.json`
- dry-run Postgres load plan
- runtime SQLite usage audit
- cutover readiness report
- `local-cutover-rehearsal-bundle.json`

It does not connect to Postgres. Use the individual steps below when you need to inspect
or rerun one part of the rehearsal.

## 1. Audit The SQLite Source

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/rehearse_cloud_migration.py \
  --source-db db/app.db \
  --report-json /tmp/aidiary-cloud-migration-report.json
```

Review the report for:

- missing expected tables
- orphaned child rows
- legacy inline image payloads
- attachment rows without storage keys

## 2. Export JSONL Rows

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/rehearse_cloud_migration.py \
  --source-db db/app.db \
  --export-dir /tmp/aidiary-cloud-export \
  --report-json /tmp/aidiary-cloud-migration-report.json
```

The export directory contains one `.jsonl` file per migrated table plus `manifest.json`.
The manifest records per-table row counts, byte sizes, and SHA-256 hashes so the loader
can detect missing or tampered files before a Postgres write. These files are temporary
rehearsal artifacts and should not be committed.

## 3. Dry-Run The Postgres Load Plan

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-cloud-export
```

This checks which exported files will be loaded, how many rows are present, and whether
`manifest.json` still matches the exported JSONL files. It does not connect to Postgres.

## 4. Plan Explicit Postgres Migrations

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/run_postgres_migrations.py
```

This lists the ordered Postgres migration files that will be applied. In dry-run mode it
does not connect to Postgres.

## 5. Apply To A Rehearsal Postgres Database

`psycopg[binary]` is pinned in `server/requirements.txt`; install the server
requirements before this step:

```bash
cd server
source venv/bin/activate
pip install -r requirements.txt
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/run_postgres_migrations.py \
  --apply
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-cloud-export \
  --apply \
  --reset-first
```

Use `--reset-first` only on a disposable rehearsal database or branch. Do not use it on a
production database.

## Next Validation

The next cloud issue should run backend parity checks against both SQLite and Postgres,
then turn those checks into the cutover checklist.
