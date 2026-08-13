# Public Launch Security And Privacy Baseline

Updated: 12 August 2026  
Scope: GitHub issue `#113`, public beta / SaaS readiness for OpenMynd.

This is a public-safe audit record. Do not add real database URLs, API keys, user
records, private diary content, OAuth secrets, or production incident details here.

## Current Readiness

OpenMynd is suitable for private/local use and controlled technical rehearsal. It is not
yet ready for open public onboarding until the blockers below are either fixed or
explicitly accepted by the owner for a narrow beta.

Current automated evidence:

- `server/scripts/validate_production_preflight.py` blocks unsafe production runtime
  defaults for JWT, database provider, runtime migrations, CORS, media storage, and
  shared rate limiting.
- The preflight now also checks production frontend URL shape, Google OAuth callback
  safety, public legal/cookie route presence when the frontend tree is available, and
  explicit owner acceptance for known session/password migration risks. It also reports
  whether the production frontend is configured for cookie-only auth or only additive
  cookie compatibility.
- Login, registration, email verification, password reset, OAuth start/callback,
  AI analysis, import/export, import revert, and account deletion routes have
  explicit rate limits, with preflight visibility for production configuration.
- Production startup now fails closed if `RATELIMIT_STORAGE_URI=memory://`, with
  regression coverage proving public production requires shared limiter storage.
- API responses now include conservative security headers for content sniffing,
  clickjacking, referrer leakage, permissions policy, and API CSP; production responses
  also include HSTS.
- Local account email verification and password reset now use provider-neutral
  transactional email. `EMAIL_PROVIDER=console` is development-only; production
  must configure SMTP.
- Database maintenance validation now checks recent backup bundle, SQLite fallback,
  Postgres snapshot, media archive, and restore rehearsal evidence before public
  cutover/launch decisions.
- Registration, login, OAuth callback, and account deletion now write low-sensitivity
  security audit events. Request IP and user-agent values are stored as keyed hashes,
  and event metadata is categorical only.
- Backend auth/profile/chat/import/database tests cover user scoping, account deletion,
  import/revert ownership, chat storage, and database provider compatibility.
- Playwright smoke now covers login, registration, legal/cookie routes, auth recovery
  screens, OAuth onboarding routing, Dashboard loading/interactions, account
  deletion/restricted access, import review/commit/revert, and Chat route
  scope/starter chips.

The standard public SaaS path is tracked separately in
[public-saas-readiness-plan.md](./public-saas-readiness-plan.md). That plan covers
hosting, domain/DNS, Stripe billing, subscription entitlements, pricing/legal pages, and
launch preflight extensions. This baseline remains the security/privacy gate for that
SaaS path.

## Launch Blockers

| Severity | Area | Risk | Current status | Tracking |
| --- | --- | --- | --- | --- |
| Blocking | Sensitive route rate limiting | Login/register/OAuth, AI, import/export, and destructive actions need limiter controls that work across app instances. | Route-level limits and production startup blockers are in place; deployment still needs real shared-limiter configuration evidence such as Redis. | `#113` or new auth-hardening issue |
| Blocking | Session storage | Browser bearer tokens are still stored in localStorage, increasing exposure if XSS occurs. | Additive `HttpOnly` cookie issuance, credentialed API requests, CSRF header forwarding, tracked JWT sessions, logout revocation, and account-deletion revocation now exist. Final cookie-only cutover still needs browser smoke evidence and removal of localStorage bearer persistence. | `#113`; later auth redesign |
| Blocking | Database operations | Public data needs rehearsed backups, restores, capacity alerts, and rollback. | Backup/snapshot/restore tooling exists and maintenance evidence can now be validated; production scheduling and real-provider evidence still need owner sign-off. | `#120`, `#73`, `#72`, `#62`, `#30`, `#28`, `#8` |
| Blocking | Secrets/config | Production must not run with local CORS, weak JWT secret, memory limiter, repo-local media, runtime migrations, or local OAuth callback URLs. | Preflight blocks these conditions. | `#113` |
| Major | HTTP response headers | Public API responses should set baseline browser security headers. | Default security headers and production HSTS are now applied and covered by backend tests; Admin Operations reports the check. | `#113` |
| Major | Legacy password fallback | Plaintext-password fallback still exists for old local databases. | Login upgrades legacy hashes after successful auth, and an operator migration command can now bulk-convert dormant plaintext rows. Public launch should run that command and then disable fallback. | `#113` or auth-hardening issue |
| Major | Account recovery and verification | Email verification and recovery need production SMTP configuration and operational validation. | Local account token flows exist; browser smoke covers verification/reset screens; preflight blocks console email in production; security audit capture is now reviewable in the Admin console. | `#113` or auth-hardening issue |
| Major | AI data processing | AI features process sensitive diary data through configured model providers. | User controls exist for history and attachment context; public disclosure and consent review still required. | legal/privacy issue |
| Major | Export/delete promises | The product must only promise what export/delete actually removes or preserves. | Account deletion and export exist; final public wording needs review against implementation. | legal/privacy issue |
| Major | Billing and entitlements | Public SaaS requires a payment provider, local entitlement model, subscription lifecycle handling, upgrade prompts, and billing disclosures. | Entitlement tables, Stripe Checkout, Customer Portal session creation, verified webhook entitlement sync, the first AI-analysis plan gate, production preflight checks, and authenticated billing disclosures exist. Remaining work is Stripe test-mode/live operational evidence. | `#132` |
| Major | Browser E2E coverage | Critical user journeys need automated browser gates before launch. | Playwright smoke/a11y exists for public auth, legal/cookie, OAuth onboarding, Dashboard, account deletion/restricted access, import review/commit/revert, Account/Customisation settings updates, Chat route scope, Chat context/stat/reply behavior, and light/dark critical-surface accessibility checks. Remaining work is broader regression expansion rather than a single known uncovered route class. | testing issue |

## Privacy Boundary Review

### Entries, dreams, thought records, and important days

- API routes are authenticated and user-scoped.
- Route guards protect frontend navigation, but backend authorization remains the source
  of truth.
- Future changes must not introduce cross-user search, dashboard, chat, import, or
  reflection leakage.

### Attachments and media

- Entry assets are stored through media references rather than raw DB blobs.
- AI analysis should consume derived text/metadata only when enabled by the user.
- Public launch needs a final statement explaining which attachment content can be used
  by AI and when.

### Chat

- Chat history is user-scoped and bounded.
- Chat is blocked at the API when disabled.
- Prior-entry memory is omitted from Chat context when `allow_ai_history` is disabled.
- Remaining decision: whether Chat should also include Thought Records, Important Days,
  attachment-derived text, and reflection summaries.

### AI analysis

- Daily/Dream analysis uses explicit profile settings, related-entry memory, and optional
  attachment context.
- Responses should stay source-aware where prior entries or attachments are used.
- Public copy must explain that diary content may be sent to the configured AI provider
  when the user chooses AI features.

## Production Preflight

Run before any public deployment or cloud cutover:

```bash
cd server
source venv/bin/activate
APP_ENV=production PYTHONPATH=. python scripts/validate_production_preflight.py
```

For cloud cutover rehearsal:

```bash
cd server
source venv/bin/activate
APP_ENV=production PYTHONPATH=. python scripts/validate_production_preflight.py --require-postgres
```

The preflight must not be used as a substitute for manual security review. It catches
unsafe configuration shape; it does not prove legal compliance, absence of XSS, correct
cookie categorisation, or external-provider contractual readiness.

## Database Maintenance Validation

Run this after scheduled database backups and before any public launch rehearsal:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/validate_database_maintenance.py \
  --backup-summary-dir ~/OpenMyndBackups \
  --sqlite-backup-dir ~/OpenMyndBackups \
  --postgres-snapshot-dir ~/OpenMyndBackups/postgres-snapshots \
  --media-backup-dir ~/OpenMyndBackups/media \
  --restore-report ~/OpenMyndBackups/restored-sqlite/latest-restore-report.json \
  --require-postgres-snapshot \
  --require-media-archive \
  --require-restore-rehearsal \
  --max-age-hours 30
```

The command is read-only. It fails on missing/stale/failed required evidence and can
emit non-blocking capacity warnings when thresholds are supplied.

## Security Audit Review

Security audit capture is available to administrators in the Admin console under
Security. The command-line report remains useful for release evidence and incident
review bundles.

Run a recent audit summary:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/report_security_audit.py --days 30
```

Generate machine-readable evidence:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/report_security_audit.py --days 30 --json
```

Useful focused checks:

```bash
PYTHONPATH=. python scripts/report_security_audit.py --event-type login_failed --days 7
PYTHONPATH=. python scripts/report_security_audit.py --user-id 123 --days 30 --json
```

Audit rows do not contain raw IP addresses, user-agent strings, passwords, tokens,
diary text, prompts, attachment filenames, or OAuth payloads. IP and user-agent values
are stored as keyed hashes so repeated suspicious activity can be correlated without
turning the audit table into a sensitive-content dump.

Production configuration should set:

```bash
SECURITY_AUDIT_RETENTION_DAYS=180
```

The preflight accepts this as an explicit owner decision and warns when the value is
missing or outside the current review range of 30 to 730 days. This setting is an
operational retention policy marker; automatic purging should be added only after the
owner confirms the public-beta retention rule.

## Transactional Email Configuration

Local development can use console delivery:

```bash
EMAIL_PROVIDER=console
```

Production account recovery requires SMTP:

```bash
EMAIL_PROVIDER=smtp
EMAIL_FROM_ADDRESS="OpenMynd <no-reply@example.com>"
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_USE_TLS=true
OPENMYND_REQUIRE_REGISTRATION_EMAIL=true
AUTH_PASSWORD_RESET_RATE_LIMIT="5 per hour"
AUTH_EMAIL_VERIFICATION_RATE_LIMIT="5 per hour"
```

Verification and reset links use `FRONTEND_BASE_URL`. The preflight blocks
console email in production and warns if local registration does not require an
email address. After configuring SMTP, use Admin → Operations → Send test email to
verify provider delivery before relying on account verification or password reset.

## Minimum Public-Beta Exit Criteria

- No blocking preflight gates.
- Owner decision recorded for localStorage JWT risk, or a secure cookie/session redesign
  shipped.
- Distributed rate limiting applied to login, register, OAuth callback, Chat, AI
  analysis, import, export, and account-delete sensitive paths as appropriate, backed
  by shared production limiter storage.
- Backups and restore rehearsal completed against the target database.
- OAuth redirect URIs, CORS origins, frontend base URL, media storage, and OpenAI keys
  configured only through production secrets.
- Legal pages and cookie consent reviewed against actual app behavior.
- Manual smoke passes for registration, Google sign-in, onboarding, account deletion,
  import/revert, export, Chat, AI analysis, and data deletion.
- Browser E2E gates cover the critical public journeys or the owner explicitly accepts
  the residual manual-testing risk.
- Security audit event retention expectations are documented before external users are
  onboarded.
