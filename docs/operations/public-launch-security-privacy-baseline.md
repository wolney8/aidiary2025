# Public Launch Security And Privacy Baseline

Updated: 6 August 2026  
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
  explicit owner acceptance for known session/password migration risks.
- Login, registration, and OAuth start/callback routes have explicit rate limits, with
  preflight visibility for production configuration.
- Backend auth/profile/chat/import/database tests cover user scoping, account deletion,
  import/revert ownership, chat storage, and database provider compatibility.

## Launch Blockers

| Severity | Area | Risk | Current status | Tracking |
| --- | --- | --- | --- | --- |
| Blocking | Auth rate limiting | Login/register/OAuth abuse needs limiter controls that work across app instances. | Route-level auth limits are in place; production still requires shared limiter storage such as Redis. | `#113` or new auth-hardening issue |
| Blocking | Session storage | Browser bearer tokens are stored in localStorage, increasing exposure if XSS occurs. | Preflight warns unless the owner explicitly accepts this risk. | `#113`; later auth redesign |
| Blocking | Database operations | Public data needs rehearsed backups, restores, capacity alerts, and rollback. | Cutover tooling exists; production maintenance remains open. | `#120`, `#73`, `#72`, `#62`, `#30`, `#28`, `#8` |
| Blocking | Secrets/config | Production must not run with local CORS, weak JWT secret, memory limiter, repo-local media, runtime migrations, or local OAuth callback URLs. | Preflight blocks these conditions. | `#113` |
| Major | Legacy password fallback | Plaintext-password fallback still exists for old local databases. | Login upgrades legacy hashes after successful auth; removal needs a migration window. | `#113` or auth-hardening issue |
| Major | Account recovery and verification | Email verification, recovery, and security-event audit flows are not complete. | Google OAuth exists; local recovery is not production-grade. | `#113` or auth-hardening issue |
| Major | AI data processing | AI features process sensitive diary data through configured model providers. | User controls exist for history and attachment context; public disclosure and consent review still required. | legal/privacy issue |
| Major | Export/delete promises | The product must only promise what export/delete actually removes or preserves. | Account deletion and export exist; final public wording needs review against implementation. | legal/privacy issue |
| Major | Browser E2E coverage | Critical user journeys need automated browser gates before launch. | Playwright smoke/a11y exists but should be expanded for OAuth, import, chat, account deletion, dashboard, and settings. | testing issue |

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
