# Known Issues

## Confirmed from current repository

- `client/package.json` defines `npm run lint`, but `client/angular.json` does not contain a `lint` target.
- `client/package.json` defines a Playwright smoke test, but no visible Playwright config file or `client/tests/e2e/` source is present.
- Existing documentation drift exists:
  - `docs/ARCHITECTURE.md` references files such as `db/models.py` that are not present in the current runtime tree.
  - `.github/copilot-instructions.md` describes a different stack from the actual repository.
- `server/.venv` is not a safe default local runtime path on this machine. `server/venv` is the working local backend environment.

## Architectural risks

- Backend schema handling is partly runtime-driven rather than managed by a formal migration tool.
- The repository currently contains generated and runtime artefacts in the working tree, including local caches and database files.
- Startup side effects include NLTK downloads and database metadata backfill.
- Frontend services use hardcoded `http://localhost:5001/api` endpoints.

## To confirm

- Whether `server/test_enrichment.py` is intended to remain outside `server/tests/`.
- Whether `server/app.db` and `server/db/app.db` are both still needed locally.
