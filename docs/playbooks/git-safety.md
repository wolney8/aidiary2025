# Git Safety

## Before changing files

Run:

```bash
git status --short --branch
```

Check for:

- unrelated local changes
- untracked files that may matter to the task
- generated artefacts that should not be committed

## During work

- Do not silently overwrite user edits or unexpected local changes.
- If a needed file already differs from expectation, inspect it first and explain the conflict.
- Keep changes small and focused so the diff stays reviewable.

## Before finishing

Run:

```bash
git status --short --branch
git diff --stat
git diff
```

Confirm:

- only intended files changed
- no generated/runtime files were accidentally edited
- no secrets or local environment values were introduced

## Generated or runtime files to avoid committing

- `client/node_modules/`
- `client/dist/`
- `client/.angular/`
- `.pytest_cache/`
- `.ruff_cache/`
- `server/.pytest_cache/`
- `server/.ruff_cache/`
- `server/venv/`
- `server/.venv/`
- `server/.runtime-venv`
- `server/db/*.db*`
- `server/db/*.sqlite*`
- `server/app.db*`
- `server/flask.log`
- Python `__pycache__/` and `*.pyc`
- local `.env` files
