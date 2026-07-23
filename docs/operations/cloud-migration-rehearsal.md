# Cloud Migration Rehearsal

## Purpose

Use this process before any SQLite-to-Postgres cutover. It is designed to be
non-destructive until the explicit Postgres `--apply` step.

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

The export directory contains one `.jsonl` file per migrated table. These files are
temporary rehearsal artifacts and should not be committed.

## 3. Dry-Run The Postgres Load Plan

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-cloud-export
```

This checks which exported files will be loaded and how many rows are present. It does not
connect to Postgres.

## 4. Apply To A Rehearsal Postgres Database

Install Psycopg only when a real rehearsal database is ready:

```bash
cd server
source venv/bin/activate
pip install "psycopg[binary]"
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
