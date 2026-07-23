# ADR 0004: Cloud Database Architecture And Target Selection

## Status

Accepted as the working cloud database direction for Phase 4.

## Context

AI Diary currently persists application data with direct `sqlite3` calls, runtime schema
compatibility helpers, and local SQLite files selected through `DB_PATH`. This has worked
well for local development, but it is not the right production database model for multiple
devices, hosted deployments, managed backup/restore, or cloud cutover rehearsals.

The current backend has several constraints that must shape the migration:

- SQL is spread across Flask routes and service modules rather than isolated in one DAO.
- Runtime migrations create or alter tables during application startup.
- Tests construct lightweight SQLite schemas directly.
- Existing media work already moved large image payloads toward storage keys, so the
  database should store metadata and references, not binary media payloads.
- Import jobs, chat messages, reflection summaries, important days, thought records, and
  attachment metadata now all need durable relational consistency.

Current provider references reviewed:

- Neon Postgres supports serverless Postgres, branching, autoscaling, scale to zero, and
  instant restore according to its official introduction docs:
  <https://neon.com/docs/introduction>
- Neon supports pooled and direct Postgres connections, with pooled hostnames for apps
  that create many concurrent connections:
  <https://neon.com/docs/get-started/connect-neon>
- Supabase exposes Postgres directly and through Supavisor transaction-mode pooling for
  transient/serverless connections:
  <https://supabase.com/docs/guides/database/connecting-to-postgres>
- Render Postgres documents connection limits and recommends connection pooling when an
  app approaches those limits:
  <https://render.com/docs/postgresql-creating-connecting>

## Decision

Use **managed PostgreSQL** as the cloud database target.

Use **Neon Postgres** as the default first target for migration rehearsal because
branching and restore workflows are a strong fit for safe, repeatable cutover tests.
Keep the implementation provider-portable by treating the connection as standard
Postgres through `DATABASE_URL`.

Supabase Postgres and Render Postgres remain compatible alternatives if deployment,
pricing, region, or platform preference changes. The application must not use
provider-specific features in core data access during the initial cutover.

## Architecture Direction

### Database Access

- Introduce a narrow database connection module before rewriting route logic.
- Support both:
  - `sqlite` for local compatibility while migration is underway
  - `postgres` for cloud rehearsal and production
- Prefer `DATABASE_URL` for Postgres and keep `DB_PATH` only for SQLite/local fallback.
- Return row-like mappings from the connection layer so route code can migrate
  incrementally.
- Avoid hardcoding local absolute paths or provider-specific connection strings.

### SQL Compatibility Rules

The first migration pass must remove or isolate SQLite-specific assumptions:

- `?` placeholders need an adapter strategy for Postgres placeholders.
- `lastrowid` needs a Postgres `RETURNING id` equivalent.
- `PRAGMA table_info` checks need migration-tool replacements.
- `date(...)` and `strftime(...)` usage must be reviewed and made Postgres-safe.
- JSON should remain stored as text initially unless a table is deliberately migrated to
  `jsonb` with tests.

### Migrations

Runtime migrations are acceptable only as a local compatibility bridge. Cloud migration
must introduce explicit, ordered migrations that can be rehearsed and rolled back.

Recommended tooling path:

- Add a migration runner under `server/migrations`.
- Keep migration files idempotent where practical.
- Add a schema-version table.
- Run migrations explicitly during deploy or release, not only during Flask startup.
- Keep startup compatibility checks temporarily until cutover is complete.

### Data Migration

The SQLite-to-Postgres migration should be repeatable and non-destructive:

- export source SQLite rows table-by-table
- validate row counts and foreign-key relationships before write
- insert into a clean Postgres rehearsal database
- verify counts, representative rows, media references, and auth/profile settings
- support dry-run mode before actual writes
- keep rollback as DNS/config flip back to SQLite until cutover is accepted

### Media And Attachments

Do not move image or attachment bytes back into the database. The cloud database stores
storage keys and metadata only. Object/media storage migration should be handled by the
existing media abstraction in a separate storage-backend issue.

### Connection Management

- Use pooled Postgres connections in production.
- Keep transaction scope explicit and short.
- Avoid long-lived global connections in Flask workers.
- Configure SSL/TLS as required by the provider.

## Execution Plan

### Issue `#28`: Data Migration Tooling And Rehearsal

- Add Postgres dependencies and a database connection abstraction.
- Add explicit migration runner and initial Postgres DDL.
- Build a dry-run SQLite-to-Postgres migration script.
- Rehearse into a throwaway Neon branch.
- Produce validation output: table counts, foreign-key checks, sample record checks.

### Issue `#30`: Cloud Parity Tests And Cutover Checklist

- Run backend tests against SQLite and Postgres where practical.
- Add SQL compatibility tests for date filters, imports, chat, attachments, reflections,
  important days, and thought records.
- Write the cutover checklist with required environment variables and rollback triggers.

### Issue `#73`: Cutover Runbook And Rollback Rehearsal

- Rehearse final migration timing.
- Confirm backup, restore, and fallback owners.
- Document exact rollback commands and expected downtime.

### Issue `#72`: Post-Cutover Verification

- Verify auth, entries, imports, exports, images, attachments, AI analysis, chat,
  reminders, and calendar views against production-like data.
- Capture query latency and error baseline.
- Remove or reduce SQLite compatibility code only after confidence is high.

## Consequences

- The repo must stop adding new database features directly into isolated SQLite-only
  assumptions where avoidable.
- Runtime migrations remain useful locally but are not sufficient for production.
- Provider-specific capabilities should wait until after the standard Postgres cutover.
- Tests will need a deliberate split between fast SQLite compatibility and Postgres
  parity coverage.

## Rollback And Fallback Strategy

- Keep SQLite as the source of truth until a rehearsal migration validates successfully.
- Before cutover, take a timestamped SQLite backup and export package.
- Cutover by changing database configuration, not by rewriting application behavior.
- Roll back by restoring the previous `DB_PATH`/deployment config while preserving the
  failed Postgres target for forensic comparison.

## To Confirm

- Final provider account and region.
- Whether production hosting will run Flask long-lived, serverless, or containerized.
- Whether media storage should move to provider object storage, S3-compatible storage, or
  another managed asset backend.
