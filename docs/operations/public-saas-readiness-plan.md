# Public SaaS Readiness Plan

Updated: 8 August 2026

Scope: standard SaaS path for OpenMynd public hosting, sign-ups, billing, subscription
tiers, production operations, and launch gating.

This document is public-safe. Do not add live API keys, database URLs, payment secrets,
customer data, private diary content, or production incident details.

## Direction

OpenMynd should follow the standard managed SaaS path:

- Hosted Angular frontend behind HTTPS and CDN.
- Hosted Flask API with explicit production configuration.
- Managed PostgreSQL, with Neon already selected for rehearsal/provider-portable
  `DATABASE_URL` support.
- Media/object storage behind storage keys, not local absolute paths.
- Google OAuth plus local email/password accounts with email verification and password
  recovery.
- Stripe Billing for web subscriptions, with Stripe Checkout for payment collection and
  Stripe Customer Portal for self-service billing.
- Internal entitlement model owned by OpenMynd, updated from verified Stripe webhooks.

The first concrete provider decision is captured in
[ADR 0005](../adr/0005-production-saas-hosting-architecture.md): Cloudflare DNS,
Vercel frontend, Render Flask API, Neon Postgres, Cloudflare R2 media storage, SMTP
email, and Stripe Billing later.

Stripe is the recommended first payment provider because it supports subscriptions,
Checkout-hosted payment pages, webhooks, coupons/discounts, and a Customer Portal. Stripe
documentation describes Checkout as a hosted payment page for subscriptions, Billing as
subscription/invoice management, webhooks as real-time event delivery, and Customer Portal
as the self-service surface for payment methods, invoices, subscription changes, and
cancellation.

References:

- https://docs.stripe.com/billing/quickstart
- https://docs.stripe.com/subscriptions
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/customer-management
- https://docs.stripe.com/api/coupons

## Architecture Target

### Frontend

- Static Angular build deployed to a managed frontend host/CDN.
- Environment-specific `apiBaseUrl`.
- Public routes:
  - `/login`
  - `/register`
  - `/forgot-password`
  - `/reset-password`
  - `/verify-email`
  - `/privacy`
  - `/terms`
  - `/cookies`
- Authenticated plan comparison:
  - `/plans`
  - `/admin/plans`
- Authenticated routes remain route-guarded and backend-authorized.

### Backend

- Flask API deployed as a managed service/container.
- `APP_ENV=production`.
- No runtime SQLite migrations in production.
- `DATABASE_PROVIDER=postgres`.
- Shared rate-limit storage, such as Redis.
- Transactional SMTP email configured.
- Object/media storage configured outside the repo source tree.
- Production preflight must pass before deployment.

### Database

- Managed PostgreSQL via `DATABASE_URL`.
- Explicit migration tooling, rehearsal branch, rollback plan, and integrity checks.
- Internal billing and entitlement tables owned by OpenMynd.
- Payment-provider object IDs are references only; app permissions must not depend
  directly on Stripe product names.

### Billing

Use Stripe-hosted surfaces first:

- Checkout Session endpoint for starting subscription purchase.
- Customer Portal Session endpoint for billing management.
- Webhook endpoint for subscription/payment lifecycle changes.
- Local entitlement state updated only from verified, idempotent webhook events.
- Billing UI reads OpenMynd's local entitlement state, not live Stripe calls on every
  page load.

## Entitlement Model

Use internal plan and feature names. Do not bind product logic directly to Stripe
product/price names.

Recommended internal tiers:

| Internal tier | Purpose | Notes |
| --- | --- | --- |
| `free` | Public entry tier | Limited storage, AI, import/export, and advanced analytics. |
| `personal` | Core paid tier | Higher storage and normal AI limits. |
| `plus` | Power-user tier | Higher AI, OCR/transcription, imports, exports, and dashboard depth. |
| `therapeutic` | Future specialist tier | Reserved for richer CBT/coach features; requires clinical/legal review. |
| `lifetime` | Permanent entitlement | Manually or commercially granted; not tied to active recurring subscription. |
| `complimentary` | Family/friends/testers | Time-limited or owner-granted. |
| `administrator` | Owner/support controls | Must not grant casual diary browsing access. |

Pricing, final public names, trial rules, quota values, and feature placement by plan are
product decisions requiring explicit owner approval before implementation or user-facing
copy changes. Provisional internal tier names and test limits are engineering scaffolding,
not commercial approval.

Approved public launch naming and starting prices:

| Internal tier | Public plan | Monthly | Annual | Notes |
| --- | --- | --- | --- | --- |
| `free` | Free | £0 | £0 | Core app access with limited AI preview. |
| `personal` | Plus | £4.99 | £47.90 | 20% annual discount; normal paid AI/media usage. |
| `plus` | Premier | £11.99 | £115.10 | 20% annual discount; higher AI/media usage. |

Plan names, prices, feature copy, and quota values are stored in OpenMynd's
`billing_plans` catalogue and can be edited by an `administrator` entitlement without a
code deploy. Stripe price IDs still map to internal tier keys.

First-owner setup uses:

```bash
cd server && source venv/bin/activate
PYTHONPATH=. python scripts/grant_admin_entitlement.py --email owner@example.com
```

After promotion, the admin user can open Account -> Plan matrix and update the live
catalogue.

## Billing Data Shape

Recommended tables:

- `billing_customers`
  - `user_id`
  - `stripe_customer_id`
  - `created_at`
  - `updated_at`
- `subscriptions`
  - `user_id`
  - `provider`
  - `provider_subscription_id`
  - `provider_price_id`
  - `status`
  - `current_period_start`
  - `current_period_end`
  - `cancel_at_period_end`
  - `trial_end`
  - `created_at`
  - `updated_at`
- `entitlements`
  - `user_id`
  - `tier`
  - `source`
  - `status`
  - `starts_at`
  - `ends_at`
  - `metadata_json`
- `billing_events`
  - `provider`
  - `provider_event_id`
  - `event_type`
  - `processed_at`
  - `payload_hash`
  - `processing_status`

Webhook requirements:

- Verify Stripe webhook signature.
- Reject replay/duplicate processing using `provider_event_id`.
- Process events idempotently.
- Store only necessary metadata.
- Do not log payment method details or full webhook payloads.
- Cover success, cancellation, failed payment, trial, downgrade, and duplicate-event
  paths with tests.

## Feature Gates

Gate through OpenMynd entitlements, not Stripe objects.

Examples:

- AI analysis monthly quota.
- Chat availability and monthly quota.
- Attachment storage quota.
- OCR/transcription quota.
- Import/export availability.
- Dashboard depth and longer-range analytics.
- Advanced memory/context features.
- Future mobile sync.

When a user is over quota:

- Save ordinary diary data where possible.
- Block only the paid capability.
- Show an app-native explanation and upgrade path.
- Never silently fail a user save because billing state is unavailable.

## Production Hosting Milestone

### Milestone

`M19 Public SaaS Hosting, Billing, and Entitlements`

Goal:

Prepare OpenMynd for public hosted SaaS operation with verified sign-up/recovery,
managed deployment, subscriptions, internal entitlements, and launch gates.

Exit criteria:

- Production frontend/API/domain architecture is selected and documented.
- Staging and production environment variables are documented and preflighted.
- Managed PostgreSQL rehearsal is complete.
- Transactional email works outside console mode.
- Stripe test-mode subscriptions work end-to-end.
- Entitlements gate at least one real feature.
- Customer Portal opens from Account/Billing.
- Webhooks are verified, idempotent, audited, and tested.
- Public launch preflight passes with no blockers.
- Legal/privacy/billing copy is reviewed against actual app behavior.

## GitHub Issue Coverage

### Issue 1

Title:

`[M19] Select production hosting, domain, DNS, and deployment architecture`

Body:

Define the first public SaaS hosting architecture for OpenMynd.

Requirements:

- Choose primary frontend hosting/CDN.
- Choose primary backend/API hosting.
- Confirm managed PostgreSQL strategy and Neon role.
- Define object/media storage provider.
- Define DNS/domain/TLS approach.
- Define staging and production environments.
- Define secret-management approach.
- Define monitoring, logs, error tracking, and alerts.
- Document expected fixed monthly cost and scaling path.
- Keep AWS out of scope unless account access issues are resolved later.

Acceptance criteria:

- Architecture decision is documented.
- Required env vars are listed for staging and production.
- Deployment path is reproducible from a clean checkout.
- Production preflight can run in CI/deployment before release.

Status note:

- Initial decision is documented in
  [ADR 0005](../adr/0005-production-saas-hosting-architecture.md). Keep this issue open
  only until the owner confirms the providers/domain and a staging deployment has been
  rehearsed.

### Issue 2

Title:

`[M19] Add Billing and subscription entitlement data model`

Body:

Add OpenMynd-owned billing and entitlement tables without coupling feature access directly
to Stripe product names.

Requirements:

- Add `billing_customers`.
- Add `subscriptions`.
- Add `entitlements`.
- Add `billing_events`.
- Add explicit migration/runtime compatibility for local and Postgres.
- Add service helpers to resolve a user's current entitlement.
- Add tests for free/default users, active paid users, expired/cancelled users, and
  complimentary/lifetime overrides.

Acceptance criteria:

- Existing accounts default to `free`.
- Entitlement lookup is user-scoped.
- Billing tables are included in cloud migration tooling.
- Account deletion removes or anonymises billing references according to the documented
  retention rule.

Status note:

- Initial local billing tables, entitlement helper service, migration/export parity, and
  account-deletion cleanup are implemented. Keep this issue open only until the owner
  confirms the internal tier names and this baseline is validated in the intended staging
  environment.

### Issue 3

Title:

`[M19] Stripe Checkout and Customer Portal integration`

Body:

Integrate Stripe-hosted Checkout and Customer Portal for web subscriptions.

Requirements:

- Add backend endpoint to create a Stripe Checkout Session.
- Add backend endpoint to create a Stripe Customer Portal Session.
- Add Account/Billing UI showing current tier/status and billing actions.
- Use Stripe test mode first.
- Keep Stripe price/product IDs in environment/config, not hardcoded in feature logic.
- Do not collect card data directly in OpenMynd.

Acceptance criteria:

- User can start upgrade from OpenMynd and reach Stripe Checkout.
- User can open Customer Portal from Account/Billing.
- Cancel/upgrade/downgrade actions are handled through Stripe-hosted UI.
- Feature access still comes from local entitlement state.

Implementation note:

- `feat/128-stripe-checkout-portal` adds `/api/billing/status`,
  `/api/billing/checkout-session`, and `/api/billing/customer-portal-session`.
- Account now shows the current OpenMynd entitlement and Stripe-hosted billing actions.
- Required environment variables:
  - `STRIPE_SECRET_KEY`
  - `STRIPE_PRICE_PERSONAL`
  - `STRIPE_PRICE_PLUS`
  - `STRIPE_WEBHOOK_SECRET` for the follow-on webhook endpoint
  - optional `STRIPE_CHECKOUT_SUCCESS_URL`
  - optional `STRIPE_CHECKOUT_CANCEL_URL`
  - optional `STRIPE_CUSTOMER_PORTAL_RETURN_URL`
- Entitlement changes still require the separate webhook issue. Checkout success alone
  must not be treated as the source of truth for paid access.

### Issue 4

Title:

`[M19] Stripe webhook processing and entitlement synchronisation`

Body:

Process Stripe webhooks securely and update local subscription/entitlement state.

Requirements:

- Add `/api/billing/stripe/webhook`.
- Verify Stripe webhook signatures.
- Store processed event IDs for idempotency.
- Handle at least:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_failed`
  - `invoice.payment_succeeded`
  - invoice/payment failure or success events needed for access state
- Audit billing state changes without logging sensitive payment data.
- Add tests for duplicate events, out-of-order events where practical, invalid
  signatures, cancellation, renewal, failed payment, and reactivation.

Acceptance criteria:

- Duplicate webhook delivery does not duplicate or corrupt entitlements.
- Invalid signatures are rejected.
- Subscription status changes update local entitlement status.
- Billing event logs contain no card/payment method details.

Implementation note:

- `feat/129-stripe-webhook-entitlements` adds `/api/billing/stripe/webhook`.
- Webhook delivery verifies the raw `Stripe-Signature` HMAC using
  `STRIPE_WEBHOOK_SECRET`.
- Supported events in the first pass:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
- Events are recorded idempotently in `billing_events`; duplicate deliveries return
  success without reprocessing.
- Subscription and entitlement rows are updated from verified Stripe events only.

### Issue 5

Title:

`[M19] Plan-gated feature limits and upgrade prompts`

Body:

Introduce first practical SaaS feature gates using OpenMynd entitlements.

Requirements:

- Define limits for `free`, `personal`, and `plus`.
- Gate at least one high-cost feature, such as AI calls, OCR/transcription, or storage.
- Add app-native upgrade prompt when a user hits a limit.
- Make quota/usage visible on Account/Billing.
- Ensure ordinary diary saving is not blocked by billing failures unless storage quota is
  explicitly exceeded.

Acceptance criteria:

- Free user receives clear limit feedback.
- Paid entitlement bypasses or raises the limit.
- UI uses Material 3/WCAG patterns.
- Backend enforces the same limit as the frontend.

Implementation note:

- `feat/130-plan-gated-limits` adds `usage_events`, plan-aware usage helpers, Account
  usage visibility, and server-enforced AI analysis limits.
- `feat/133-admin-plan-catalogue` moves plan names, prices, feature copy, and quotas into
  the `billing_plans` catalogue. Current seeded monthly AI analysis limits are:
  - `free`: 10
  - `personal` / public `Plus`: 250
  - `plus` / public `Premier`: 1000
  - `therapeutic`, `lifetime`, and `complimentary`: 1000
  - `administrator`: unlimited
- Daily, Dream, and Thought Record AI analysis are gated server-side.
- Ordinary entry saves still complete if the user has reached the AI analysis limit;
  only the AI response is skipped with an upgrade-required warning.

### Issue 6

Title:

`[M19] Authenticated plan selection, legal, and billing disclosure pages`

Body:

Add authenticated SaaS plan surfaces and copy aligned with actual OpenMynd behavior.

Requirements:

- Add authenticated `/plans`; do not expose a public pricing route for v1.
- Add onboarding plan selection at the end of first-run setup.
- Add admin-only `/admin/plans` for editing the plan matrix.
- Review and update Terms, Privacy, and Cookie pages for paid SaaS behavior.
- Explain AI data processing, exports, account deletion, refunds/cancellation, and
  subscription management.
- Keep copy concise and consistent with actual implementation.
- Do not promise data behavior that export/delete/billing does not implement.

Acceptance criteria:

- Authenticated plan page exists.
- Admin plan matrix can edit public names, prices, features, and quotas.
- Legal pages reflect real auth, AI, billing, export, and deletion behavior.
- Public legal links are reachable from footer/login/register/account.
- Plan links are reachable from onboarding/account/gated upgrade prompts only.
- Copy passes product-owner review before public launch.

Implementation note:

- `feat/132-pricing-legal-disclosures` originally added `/pricing`; owner direction later
  moved plan visibility behind authentication.
- `feat/133-admin-plan-catalogue` replaces the public pricing route with authenticated
  `/plans`, onboarding plan selection, and admin catalogue editing.
- Footer, Login, and Register link to legal pages only. Account/Billing links to Plans.
- Terms, Privacy, and Cookie copy now mention AI provider use, supported exports,
  account deletion boundaries, Stripe-hosted billing, subscription limits, and cookie
  consent behavior.

### Issue 7

Title:

`[M19] Public launch preflight and deployment gate`

Body:

Extend production preflight and release checks for hosted SaaS launch.

Requirements:

- Add checks for Stripe secret/public/webhook configuration.
- Add checks for SMTP production mode.
- Add checks for production frontend/API URLs.
- Add checks for public legal and cookie routes.
- Add checks for shared rate limit storage.
- Add checks for Postgres provider and migration mode.
- Add checklist output suitable for launch evidence.

Acceptance criteria:

- Preflight blocks missing Stripe webhook secret in production.
- Preflight blocks console email in production.
- Preflight blocks memory rate limiter in production.
- Preflight reports billing/legal readiness status.
- Launch cannot be marked ready while blockers remain.

Implementation note:

- `feat/131-public-launch-preflight` extends production preflight with Stripe
  configuration checks for `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  `STRIPE_PRICE_PERSONAL`, and `STRIPE_PRICE_PLUS`.
- The preflight now reports Stripe readiness in the summary and blocks partial or
  malformed Stripe configuration.
- Frontend source checks now include public route presence for `/privacy`, `/terms`, and
  `/cookies`. `/plans` is authenticated and intentionally not public.

## Sequencing

Recommended order after the current account-recovery branch:

1. Finish and merge account recovery/email verification.
2. Complete database/cloud maintenance tracking already planned under `#120`.
3. Start `M19` with hosting architecture first.
4. Add billing/entitlement model.
5. Add Stripe Checkout and Portal.
6. Add Stripe webhook sync.
7. Add feature gates and pricing/legal pages.
8. Expand E2E tests for sign-up, billing, import/export, account deletion, and AI-cost
   controls.

Do not start Stripe integration before the internal entitlement model exists. Payment
providers should update entitlements; they should not become the app's permission system.
