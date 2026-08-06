# Database Outage And Failed-Save Resilience

OpenMynd must never imply that an entry was saved when the database rejected the write.
This applies to SQLite now and hosted Postgres/Neon later.

## Current Behaviour

- `/api/health/database` checks database read reachability.
- `/api/health/database?write=true` also performs a temporary write probe.
- Database connectivity, write-lock, storage, and quota-style failures are returned as
  sanitized API errors with stable `code` values.
- Entry create/edit screens keep the user's input on screen when a save fails.
- The user sees a clear message that the save did not complete.

## Error Codes

- `database_unavailable`: the app could not reach the database.
- `database_write_unavailable`: the database is reachable but not accepting writes.
- `database_storage_exhausted`: storage, quota, disk, or connection capacity appears exhausted.
- `database_write_failed`: a database write failed but does not match a narrower category.

## What This Is Not

This is not offline-first sync. If the hosted database is unavailable, OpenMynd does
not yet queue encrypted local writes and replay them later.

That future feature needs a separate design because it changes:

- IndexedDB storage and encryption expectations
- conflict resolution across devices
- user-visible sync state and retry controls
- account deletion semantics
- export/import and backup guarantees

## Operator Check

Use this before and after cloud cutover, deploys, or suspected provider incidents:

```bash
curl -f http://localhost:5001/api/health/database
curl -f 'http://localhost:5001/api/health/database?write=true'
```

