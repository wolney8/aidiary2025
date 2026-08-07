# Known Issues

## Confirmed from current repository

- Existing documentation drift exists:
  - `docs/ARCHITECTURE.md` references files such as `db/models.py` that are not present in the current runtime tree.
  - `.github/copilot-instructions.md` describes a different stack from the actual repository.
- `server/.venv` is not a safe default local runtime path on this machine. `server/venv` is the working local backend environment.
- The frontend dependency tree currently reports npm audit findings. Dependency upgrades
  need a controlled compatibility pass rather than `npm audit fix --force`.

## Architectural risks

- Backend schema handling is partly runtime-driven rather than managed by a formal migration tool.
- The repository currently contains generated and runtime artefacts in the working tree, including local caches and database files.
- Startup side effects include NLTK downloads and database metadata backfill.
- Frontend API configuration is environment-based, but deployment-specific production
  configuration still needs verification before hosting.

## Authentication security review

Immediate hardening completed:

- Protected routes reject missing, malformed, and expired JWTs before rendering.
- Expired sessions are cleared and redirected to login with a safe return path.
- Production startup requires an explicit `JWT_SECRET` when
  `APP_ENV=production`.
- Registration supports long passphrases up to 128 characters instead of imposing
  the previous 12-character ceiling.
- Legacy plaintext passwords are upgraded to bcrypt after a successful login.
- Chat is blocked at the backend when disabled and omits prior-entry context when
  `allow_ai_history` is disabled.
- Login, registration, and OAuth start/callback routes now have explicit configurable
  rate limits.
- Production preflight now checks frontend URL shape, Google OAuth callback safety,
  legal/cookie route source presence, and explicit owner acknowledgement for known
  session/password migration risks. It also reports whether auth rate limits were
  explicitly configured for production.

Remaining risks requiring dedicated delivery work:

- **High:** auth route limits depend on the configured Flask-Limiter backend. Use
  datastore-backed/shared limiter storage before exposing multiple public instances.
- **High:** browser sessions use local-storage bearer tokens. A production auth redesign
  should evaluate secure HttpOnly cookies, CSRF protection, refresh/rotation, and
  server-side revocation.
- **Medium:** legacy plaintext-password fallback remains active. Provide an audited
  migration command and remove the fallback after all deployed databases are migrated.
- **Medium:** account recovery, verification, security-event audit, and consent policy
  are not implemented. Define the account identity model before adding email recovery.
- **Low:** duplicate registration confirms that a username exists. Decide whether that
  usability tradeoff is acceptable alongside rate limiting and monitoring.

Current public-launch audit:

- [Public Launch Security And Privacy Baseline](./operations/public-launch-security-privacy-baseline.md)

## To confirm

- Whether `server/test_enrichment.py` is intended to remain outside `server/tests/`.
- Whether `server/app.db` and `server/db/app.db` are both still needed locally.
