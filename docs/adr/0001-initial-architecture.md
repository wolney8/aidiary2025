# ADR 0001: Initial Architecture Snapshot

## Status

Accepted as a repository snapshot on 3 June 2026.

## Context

The repository currently implements AI Diary as a split Angular and Flask application backed by SQLite. Existing project documentation contains drift, so future work needs a simple architecture record grounded in the current tree.

## Decision

Treat the following as the working architecture baseline until superseded by a later ADR:

- Angular 17 frontend in `client/`
- Flask backend in `server/`
- SQLite persistence via direct `sqlite3` access
- Flask blueprints for domain routes
- Service modules for OpenAI, import, and runtime migration concerns
- Runtime schema adjustments on backend startup

## Consequences

- Database changes require extra care because schema expectations are shared between live data, tests, and runtime migration helpers.
- Documentation must prefer current source over historical notes.
- Route and command integrity should be checked during routine development because drift already exists.

## To confirm

- Whether runtime migrations are a temporary bridge or the intended long-term migration strategy.
- Whether frontend route gaps reflect missing files, pending work, or stale references.
