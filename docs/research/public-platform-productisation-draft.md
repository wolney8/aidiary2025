# AI Diary Public Platform Productisation Draft

Public-safe planning draft for future platform productisation.

Date: 2026-07-29

## 1. Executive Summary

AI Diary is currently a capable private web application with meaningful product depth:
daily entries, dream entries, thought records, important days, on-this-day resurfacing,
attachments, import/export, AI analysis, image generation, reflection summaries,
dark/light themes, and growing WCAG coverage.

It is not yet ready to become a public SaaS or mobile platform. The primary blockers are
not missing features; they are public-platform controls: production authentication,
formal database migrations, secret handling, privacy/security policy, encryption model,
payment entitlements, observability, incident response, and mobile sync architecture.

Recommended direction:

- Continue stabilising the private app and close the remaining local issue queue.
- In parallel, plan the public edition as a separate architecture programme.
- Do not perform a big-bang rewrite.
- Keep the current Flask and Angular product working while carving out production seams:
  auth, storage, database, background jobs, AI consent, audit logging, and entitlements.
- Treat the first public-platform implementation task as a security and privacy audit
  baseline, not a new feature.

## 2. Verified Current-State Audit

Verified from repository source, not inferred from historical docs.

### Frameworks and versions

- Frontend: Angular 17.3.x, Angular Material 17.3.x, RxJS 7.8.x, TypeScript 5.4.x.
- Backend: Flask 3.1.0, Flask-JWT-Extended 4.7.1, Flask-CORS 4.0.1,
  Flask-Limiter 4.1.1, bcrypt 4.2.1.
- AI SDK: OpenAI Python SDK 1.109.0.
- Test tooling: pytest 8.3.4, Playwright 1.60.0, axe-core Playwright 4.10.2.

### Frontend architecture

- Angular standalone components.
- Route guards exist for authentication and pending changes.
- JWT and user payload are stored in browser localStorage.
- Main routes include entries, create/edit/detail, thought records, important days,
  reflections, profile, settings/import/export/customisation/appearance.
- Material 3 style and app tokens are increasingly enforced through
  `.github/skills/enforce-platform-ux/SKILL.md`.

### Backend architecture

- Flask application factory in `server/app.py`.
- Blueprints cover auth, profile, entries, analyse, import, important days, public
  holidays, on-this-day, reflection summaries, chat, and CBT.
- Startup performs NLTK downloads and SQLite-only runtime migrations/backfills.
- OpenAI calls are centralised mostly in `server/services/openai_svc.py`.

### Database technology and schema

- Current default is SQLite at `server/db/app.db`.
- A provider seam exists for SQLite/Postgres via `DATABASE_PROVIDER`,
  `DATABASE_URL`, `DatabaseAdapter`, SQL placeholder adaptation, and a Postgres initial
  schema under `server/migrations/postgres/0001_initial_schema.sql`.
- Runtime migrations are intentionally enabled only for SQLite.
- Cloud cutover tooling exists under `server/scripts/`.
- A real Postgres rehearsal still requires an external `DATABASE_URL`.

### Authentication and session management

- Registration validates username/password/name shape.
- Passwords are stored with bcrypt for new/updated users.
- Legacy plaintext password fallback remains active and migrates on successful login.
- JWT access token lifetime is 24 hours.
- Production requires `JWT_SECRET`; development falls back to a local secret.
- Client stores bearer tokens in localStorage.
- No verified email verification, password reset, passkeys, MFA, refresh-token rotation,
  server-side session revocation, or account recovery flow.
- No user-facing SSO/OAuth sign-up flow is implemented. Current OAuth notes elsewhere in
  this draft are future API/developer-access notes, not end-user authentication.

### Rate limiting and abuse controls

- Flask-Limiter is configured.
- Chat has a route-level rate/budget model and observability events.
- General login/registration distributed rate limiting is still listed as a known issue.
- Default limiter storage is `memory://`, not public-production suitable.

### Encryption

- TLS depends on deployment layer; no production deployment layer is currently verified.
- No application-level field encryption for diary/dream/CBT content is implemented.
- Media files are stored as local files under a server-managed root; no object-storage
  encryption policy is implemented in app code.
- Passwords use bcrypt except legacy fallback accounts.

### AI integrations

- OpenAI API is used for daily/dream analysis, thought-record analysis, reflection
  summaries, chat companion streaming, transcription, OCR cleanup, and image generation.
- Model allow-list includes `gpt-4o-mini`, `gpt-4.1-mini`, and `gpt-4.1`.
- Default analysis model is `gpt-4.1-mini`.
- AI attachment context and history settings exist.
- No full public-release AI safety layer or crisis-support policy is implemented.
- No maintained external source for crisis/hotline data is integrated.

### File and attachment storage

- Images/assets are stored outside DB as local media files with storage keys.
- Browser-facing URLs are resolved at response time.
- Supported attachment types include images, PDF, and audio.
- PDF embedded text extraction and OCR fallback exist.
- Audio transcription support exists via OpenAI service path.
- No cloud object storage backend is implemented yet.

### Logging and monitoring

- Flask logs exist.
- Authorization header logging logs only prefix, not full token.
- Chat observability has a service/table.
- No public-grade monitoring stack, centralised logs, SLO dashboards, error tracking,
  alerting, audit log review, or incident response process is verified.

### Tests

- Backend has a substantial pytest suite covering auth, entries, import, AI service,
  CBT, chat, cloud migration tooling, public holidays, reflection summaries, and
  production preflight.
- Frontend has Playwright smoke, inactivity, and WCAG accessibility suites.
- Current a11y suite has 31 checks after recent hardening.
- No verified payment, mobile, load, formal security, or DR restore test suite.

### Deployment and secrets

- No production deployment configuration was found in the repo root.
- `.env.example` and `server/.env.example` exist with placeholder values.
- `validate_production_preflight.py` blocks missing/weak JWT, unsafe CORS, and Postgres
  cutover misconfiguration.
- Actual `.env` files exist locally and were not read in this audit.
- Runtime artifacts and DB files exist in the working tree, which remains a public-repo
  hygiene risk.

## 3. Risk Register

| Risk | Severity | Current state | Required before public launch |
| --- | --- | --- | --- |
| LocalStorage bearer tokens | High | Verified client stores JWT in localStorage | Decide cookie/session model, CSRF, refresh/revocation |
| Missing email verification/reset | High | Not verified in code | Add verified email, reset, anti-abuse |
| Legacy plaintext fallback | High | Verified fallback remains | Migrate all accounts, remove fallback |
| No field-level diary encryption | High | Not implemented | Decide encryption model and key custody |
| Admin/operator access to content | High | No policy/technical controls verified | Least-access support tooling, audit records, policy |
| Runtime SQLite migrations | High | Verified for local SQLite | Formal migration tool and release process |
| No object storage backend | High | Local media only | S3-compatible or managed object storage abstraction |
| AI privacy/consent gaps | High | Settings exist, policy incomplete | Consent, provider data-flow copy, retention notes |
| Crisis support not production-safe | High | No full safety layer | Contextual classifier, maintained resources, tests |
| No payments/entitlements | Medium | Missing | Internal entitlement model and webhook tests |
| No mobile sync architecture | Medium | Missing | Offline store, conflict resolution, token storage |
| Observability incomplete | Medium | Chat only | Logs, metrics, SLOs, alerting, error tracking |
| Deployment unknown | Medium | No public config | Staging/prod IaC and CI/CD |
| Public repo artifact hygiene | Medium | Runtime artifacts present locally | Clean ignore policy and secret scanning |

## 4. Target Production Architecture

### Recommended primary architecture

Use a managed Postgres-first, container-light architecture:

- Frontend: Cloudflare Pages or Render static site.
- Backend/API: Render Web Service or Google Cloud Run.
- Database: Neon managed Postgres initially, because the repo already targets provider
  portability through `DATABASE_URL` and has Neon-oriented rehearsal notes.
- Object storage: Cloudflare R2 or DigitalOcean Spaces via S3-compatible API.
- Background jobs: provider-native worker/cron first; later a managed queue if volume
  requires it.
- Auth: short-term harden current app auth; medium-term evaluate managed auth or a
  dedicated auth service. Do not keep localStorage bearer tokens for public launch.
- End-user sign-up/auth: support email/password plus selected OAuth identity providers
  such as Google and Apple for public launch. Treat Microsoft as a likely later provider
  if workplace/enterprise use becomes important. Keep provider identity records separate
  from the app user profile so users can link/unlink providers without losing diary data.
- Email: Postmark, Mailgun, Resend, or provider equivalent. Requires DPA review.
- Payments: Stripe Billing plus internal entitlement table. Do not store card data.
- Monitoring: Sentry for errors, provider metrics, uptime checks, structured audit logs.
- Secrets: provider secret manager/environment variables, never repo files.
- CI/CD: GitHub Actions with lint, backend tests, frontend build, Playwright smoke/a11y,
  secret/dependency scan, deploy gates.

Rationale:

- Minimal rewrite.
- Managed Postgres aligns with current cloud migration lane.
- S3-compatible storage avoids AWS account dependency while preserving cloud portability.
- Render/Cloud Run avoid Kubernetes overhead.

### Fallback architecture

DigitalOcean App Platform plus DigitalOcean Managed Postgres and Spaces.

Rationale:

- Simple, predictable pricing.
- S3-compatible storage.
- Less platform sprawl for early public beta.
- Suitable fallback if Render/Cloud Run/Neon operational fit is poor.

## 5. Hosting and Managed Database Comparison

Indicative only. Confirm before purchase.

USD to GBP assumption: 1 USD is about 0.75 GBP, based on current July 2026 market
references consulted during this draft.

| Provider | Fit | Pros | Cons | Current pricing signal |
| --- | --- | --- | --- | --- |
| Neon | Primary DB candidate | Serverless Postgres, branching, good for rehearsal | Separate app hosting/storage required | Free plan; Launch typical spend around 15 USD/month; docs list free allowances |
| Render | Primary app-host candidate | Web services, static sites, Postgres, workers, cron | Postgres costs can rise; less hyperscale than GCP/Azure | Official pricing page covers web, Postgres, workers, cron; cron minimum 1 USD/month |
| Google Cloud Run | Production app fallback | Scale-to-zero, mature IAM/logging, EU/UK regions | More setup; cost predictability requires care | Official docs: pay per resource, 100 ms billing increments |
| Cloudflare Pages/R2/Workers | Frontend/storage candidate | Strong CDN, R2 no egress-style positioning, cheap edge | Flask backend does not naturally run on Workers | Workers Paid minimum 5 USD/month; R2 listed at 0.015 USD/GB-month |
| DigitalOcean | Fallback full-stack | Predictable, simple, Spaces S3-compatible | Less advanced managed platform than GCP/Azure | App Platform web from 5 USD/month; managed DB from 15 USD/month; Spaces from 5 USD/month |
| Railway | Early prototype only | Fast DX, simple deploys | Less mature for sensitive public health-adjacent data | Free/Hobby/Pro tiers; usage-based resources |
| Azure | Enterprise fallback | UK/EU compliance story, managed Postgres, OpenAI option | Higher complexity/cost | Postgres flexible server burstable/general-purpose tiers |
| Supabase | Possible auth/storage/db alternative | Postgres, Auth, Storage in one platform | Significant app architecture decision; RLS model work | Managed platform with free/pro tiers |

## 6. Indicative Monthly Cost Model

Fixed platform costs exclude OpenAI and payment fees. All figures are rough GBP ranges.

| Stage | Fixed platform estimate | Notes |
| --- | ---: | --- |
| Development | 0 to 25 GBP | Free tiers/local plus occasional hosted DB/storage |
| Private personal use | 5 to 35 GBP | Small app host plus managed Postgres/storage |
| Initial public beta | 40 to 120 GBP | Staging/prod, DB, object storage, email, monitoring |
| 100 active users | 80 to 250 GBP | Depends on media, AI usage, background jobs |
| 1,000 active users | 250 to 1,200 GBP | Need monitoring, DB scaling, support processes |
| 10,000 active users | 1,500+ GBP | Architecture and AI usage dominate; needs modelling |

AI variable costs:

- Analysis and chat costs scale by token volume and chosen model.
- Image generation and transcription can dominate per-user cost if unrestricted.
- Public launch needs per-user AI budgets, spend caps, queueing, and visible cost-aware
  UX for expensive actions.

Payment fees:

- Stripe is the likely default for web billing, but exact UK fee mix must be confirmed
  against the active Stripe UK pricing page before launch.

## 7. Subscription and Entitlement Model

Do not bind app permissions directly to Stripe product names.

Internal entitlement model:

- `free`
- `personal`
- `plus`
- `therapeutic`
- `lifetime`
- `complimentary`
- `administrator`

Feature-flag examples:

| Capability | free | personal | plus | therapeutic |
| --- | --- | --- | --- | --- |
| Daily/dream entries | Limited or yes | Yes | Yes | Yes |
| Attachments | Small quota | Larger quota | Larger quota | Larger quota |
| AI analysis | Limited monthly budget | Moderate | Higher | Higher with safety controls |
| Reflection summaries | Limited | Yes | Yes | Yes |
| CBT tools | Basic | Yes | Yes | Yes |
| Export | Yes | Yes | Yes | Yes |
| API access | No | No/limited | Optional | Optional |

Billing requirements:

- Stripe Checkout/Billing for web subscriptions.
- Webhooks must be signature verified, idempotent, auditable, replay-resistant, and
  covered by tests.
- Support trials, coupons, promo codes, complimentary access, family/friend discounts,
  cancellations, grace periods, failed-payment states, upgrades, downgrades, refunds.
- Mobile app billing must account for Apple and Google policy constraints before launch.

## 8. Privacy and AI Data Flow

Text diagram:

```text
User device
  -> Angular client
  -> Flask API
  -> Postgres database: entries, metadata, settings, entitlements
  -> Object storage: images, attachments, exported packages
  -> Optional AI processing only when user invokes or enables it
       -> OpenAI API: selected entry/context/attachment-derived text
       -> Returned AI response stored in app database
  -> Monitoring/logging
       -> Operational metadata only; never diary content
```

Principles:

- Users must be able to create entries without AI processing.
- AI must be opt-in, source-aware, and explainable.
- Logs, analytics, crash reports, support tools, and admin dashboards must not expose
  diary, dream, CBT, attachment-derived, or AI prompt content.
- Privacy copy must not claim absolute privacy unless encryption and operational access
  controls make that true.
- Export/delete/access requests must be first-class product requirements.

## 9. Public API Outline

Public API should come after auth/privacy foundations.

Candidate API:

- `/api/v1/entries`
- `/api/v1/dreams`
- `/api/v1/moods`
- `/api/v1/attachments`
- `/api/v1/imports`
- `/api/v1/webhooks`

Requirements:

- OAuth 2.1 or equivalent delegated authorization.
- User-controlled scopes such as `entries:write`, `entries:read`, `dreams:write`,
  `moods:write`, `profile:read`.
- Idempotency keys for create/import.
- Rate limiting per app/user/scope.
- Developer app registration.
- OpenAPI schema.
- Source/provenance tags.
- Duplicate detection.
- Token revocation and audit history.

This API OAuth work is separate from end-user social sign-in. User sign-in should use
OpenID Connect/OAuth identity-provider login, while third-party API access should use
scoped delegated authorization.

## 10. Mobile Strategy

Recommended approach: start with PWA hardening, then build React Native or Flutter only
after API/auth/sync contracts are stable.

Why:

- The current codebase is Angular web plus Flask API.
- A thin WebView is not acceptable for security/privacy.
- Native Swift/Kotlin would be highest quality but too costly for the current team.
- React Native or Flutter both remain viable after backend contracts stabilise.

Mobile requirements before beta:

- Secure token storage.
- Biometric unlock.
- Offline entry creation.
- Encrypted local storage.
- Sync conflict resolution.
- Push notifications.
- Deep links/universal links.
- App Store privacy declarations and Google Play data-safety declarations.
- Screenshot/app-switcher privacy option.

## 11. Phased Implementation Roadmap

### Phase 0: Repository and security audit

- Objective: establish verified baseline.
- Scope: current-state audit, risk register, secret scan, dependency audit, data-flow map.
- Acceptance: owner-approved public launch blocker list.
- Rollback: documentation-only.
- Complexity: S.

### Phase 1: Architecture foundations

- Objective: formalise production seams.
- Scope: ADRs, environment model, structured config, background-job decision.
- Acceptance: staging/prod architecture approved.
- Complexity: M.

### Phase 2: Production database and authentication

- Objective: hosted Postgres plus public-safe auth.
- Scope: migration rehearsals, formal migrations, secure sessions, email verification,
  reset, rate limiting.
- Acceptance: staging cutover rehearsal and auth threat-model tests pass.
- Complexity: L.

### Phase 3: Privacy and encryption controls

- Objective: protect sensitive diary content.
- Scope: encryption model, access policy, export/delete, audit logs.
- Acceptance: privacy/legal language aligns with actual controls.
- Complexity: L.

### Phase 4: Public web beta

- Objective: controlled public web beta.
- Scope: production hosting, monitoring, alerting, SLOs, incident process.
- Acceptance: beta release gate passes.
- Complexity: M/L.

### Phase 5: Payments and entitlements

- Objective: commercial access control.
- Scope: Stripe, internal entitlements, webhooks, trials/coupons.
- Acceptance: webhook and entitlement tests pass.
- Complexity: M.

### Phase 6: CBT-informed tools

- Objective: guided tools without medical claims.
- Scope: CBT protocols, labels, export for therapist review.
- Acceptance: safety copy and UX reviewed.
- Complexity: M/L.

### Phase 7: AI safety controls

- Objective: safer AI responses and crisis handling.
- Scope: contextual risk classifier, regional support source, test suite.
- Acceptance: false-positive and high-risk evaluation suite approved.
- Complexity: L.

### Phase 8: External API

- Objective: authorised third-party entry creation.
- Scope: OAuth/scopes/OpenAPI/webhooks/rate limits.
- Acceptance: delegated auth and audit tests pass.
- Complexity: L.

### Phase 9: Mobile beta

- Objective: mobile-first secure diary use.
- Scope: offline sync, secure storage, push, app-store privacy.
- Acceptance: beta test track and sync tests pass.
- Complexity: XL.

### Phase 10: Public production launch

- Objective: public production readiness.
- Scope: pen test, DR exercise, legal review, support workflow.
- Acceptance: launch checklist signed.
- Complexity: XL.

## 12. Blocking Owner Decisions

1. Public launch jurisdiction and initial market: UK only, UK/EU, or broader.
2. Hosting preference: Render/Neon/Cloudflare, Google Cloud/Neon/Cloudflare, or
   DigitalOcean full-stack fallback.
3. Auth strategy: harden custom auth or migrate to managed auth.
4. End-user SSO providers for launch: email/password only, Google, Apple, Microsoft, or
   a managed provider bundle.
5. Encryption stance: app-managed field encryption, provider-managed only, or hybrid.
6. AI provider/data retention stance: OpenAI standard retention, qualifying ZDR request,
   Azure OpenAI, or local/private model option.
7. Payment provider and product tier names/prices.
8. Whether the product may be marketed as wellness/self-help only or therapeutic.
9. Minimum age and child-account policy.
10. Whether administrators/support can ever access user content, and under what controls.
11. Mobile strategy: PWA-first, React Native, Flutter, or native apps.

## 13. Recommended Repository Docs and ADRs

Keep public-safe, high-level docs in repo. Keep sensitive commercial/pricing/privacy
working drafts local until approved.

Recommended public docs later:

- `docs/public-platform-readiness.md`
- `docs/security/public-launch-risk-register.md`
- `docs/privacy/ai-data-flow.md`
- `docs/operations/production-runbook.md`
- `docs/operations/incident-response.md`
- `docs/operations/backup-restore.md`

Recommended ADRs:

- Hosting provider.
- Database provider.
- Authentication/session model.
- End-user SSO/OAuth provider strategy.
- File/object storage.
- Encryption model.
- AI provider/data retention.
- Payment provider.
- Background jobs.
- Monitoring/error tracking.
- Mobile framework.
- Public API auth.

## 14. Single Safest Highest-Value First Task

Implement a public-launch security and privacy baseline audit as code-backed, public-safe
documentation and tests.

Scope:

- No product feature changes.
- Verify auth, secrets, CORS, rate limits, logging, AI data flow, media storage, export,
  and database migration gaps.
- Add or improve automated preflight checks only where non-invasive.
- Produce a launch-blocker checklist that maps directly to GitHub issues.

Why this first:

- It reduces risk before architecture changes.
- It can be done incrementally.
- It does not destabilise the current private app.
- It creates the acceptance gate for public productisation.

## Sources Consulted For External Assumptions

- Neon pricing/plans: https://neon.com/pricing and https://neon.com/docs/introduction/plans
- Render pricing/docs: https://render.com/pricing and https://render.com/docs/cronjobs
- Fly.io pricing: https://fly.io/docs/about/pricing/ and https://fly.io/pricing/
- Supabase platform overview: https://supabase.com/
- Google Cloud Run pricing: https://cloud.google.com/run/pricing
- Cloudflare developer platform/R2 pricing: https://www.cloudflare.com/plans/developer-platform/
  and https://www.cloudflare.com/plans/
- DigitalOcean pricing: https://www.digitalocean.com/pricing,
  https://www.digitalocean.com/pricing/app-platform, and
  https://docs.digitalocean.com/products/app-platform/details/pricing/
- Railway pricing: https://railway.com/pricing
- Azure PostgreSQL pricing/concepts: https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/
  and https://learn.microsoft.com/en-us/azure/postgresql/compute-storage/concepts-compute
- Stripe billing/payment docs: https://docs.stripe.com/billing/subscriptions/overview,
  https://docs.stripe.com/billing/subscriptions/coupons, and
  https://docs.stripe.com/billing/subscriptions/trials
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OpenAI API data controls and pricing: https://developers.openai.com/api/docs/guides/your-data
  and https://developers.openai.com/api/docs/pricing
- GBP/USD reference: https://www.gov.uk/government/publications/hmrc-exchange-rates-for-2026-monthly
  and current market references checked on 2026-07-29.
