# Coding Standards

## General

- Use British English in new documentation, UI copy, and comments unless code conventions require otherwise.
- Prefer small, reviewable changes over broad rewrites.
- Read the affected source and tests before editing.
- Follow the existing project structure unless there is a clear reason to change it.

## Frontend

- Preserve Angular standalone-component patterns already used in `client/src/app/`.
- Keep feature code within its feature folder where practical.
- Reuse `core` services and `shared` components rather than duplicating logic.
- Be careful with route changes because source/runtime drift already exists.
- Treat hardcoded API URLs as a design constraint to review before widening scope.

## Backend

- Match existing Flask blueprint and service patterns.
- Preserve current database schema expectations unless the task explicitly includes schema work.
- Prefer explicit SQL changes with test coverage because the app relies on `sqlite3` and runtime migrations.
- Treat startup behaviour in `server/app.py` as sensitive because it performs schema and NLTK work.

## Testing and validation

- Run only repository-confirmed commands where possible.
- If a configured command appears stale or incomplete, say so instead of pretending it passed.
- Update or add tests near the changed area when behaviour changes.

## Documentation

- Mark uncertainty as `To confirm`.
- Do not copy old assumptions from historical docs without checking current files.
- Keep operational guidance concise and task-focused.
