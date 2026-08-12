# Roadmap

Updated: 8 August 2026. GitHub issues remain the delivery source of truth; this file
records the intended sequence and the major readiness gaps that should not be lost
between delivery sessions.

## Future State

OpenMynd should become a private, portable, clinically careful reflection system rather
than a generic notes app. The target product shape is:

- A calendar-first personal record that brings together diary entries, dreams, thought
  records, important days, on-this-day memories, attachments, and generated reflections
  without making the interface feel crowded.
- AI that is opt-in, source-aware, and explainable: responses should state when they use
  prior entries, attachments, thought records, or period summaries, while avoiding
  hidden broad surveillance of the user's archive.
- Data that is portable and cloud-ready: exports must preserve enough manifest metadata
  to round-trip entries, images, attachments, prompts, important days, and future media
  references without depending on local filesystem paths.
- A Material 3 and WCAG-led interface where dark mode, compact layouts, dialogs,
  tables, cards, pills, icons, and route returns are consistent enough that new features
  extend the system rather than create one-off screens.
- A production path that moves from local SQLite convenience to hosted PostgreSQL with
  rehearsed migration, rollback, integrity checks, and performance baselines.

Near-term work should now prioritise public-readiness hardening and gap closure over
new broad product surfaces.

## Current Readiness Lanes

1. Security and privacy baseline
   - Finish public-launch security review before any real public onboarding.
   - Harden auth rate limiting, browser session storage, legacy password migration,
     account recovery, audit logging, and consent/privacy evidence.
   - Session migration target is documented in
     [session-auth-hardening-plan.md](./operations/session-auth-hardening-plan.md).
2. Database operations and cloud readiness
   - Keep SQLite as the current local fallback while rehearsing Neon/Postgres cutover.
   - Complete backup, restore, maintenance, rollback, integrity, and performance
     evidence before switching production data stores.
   - Backup, snapshot, media archive, restore fallback, and maintenance validation
     tooling now exists; `#120` should close only after a scheduled run and restore
     rehearsal are captured against the intended provider/data set.
3. Public SaaS hosting, billing, and entitlements
   - Follow the standard managed SaaS path documented in
     [public-saas-readiness-plan.md](./operations/public-saas-readiness-plan.md):
     hosted frontend, hosted Flask API, managed PostgreSQL, object/media storage,
     Google OAuth/local email auth, Stripe Billing/Checkout/Customer Portal, and an
     internal entitlement model.
   - Initial provider architecture is captured in
     [ADR 0005](./adr/0005-production-saas-hosting-architecture.md): Cloudflare DNS,
     Vercel frontend, Render API, Neon Postgres, Cloudflare R2 media storage, SMTP, and
     Stripe Billing later.
   - Do not wire paid plans directly to Stripe product names. Stripe should update
     OpenMynd-owned entitlements through verified webhooks.
4. Chat and AI context validation
   - Chat already has bounded user-scoped Daily/Dream context. It still needs a product
     pass to respect AI-history privacy settings explicitly and to decide whether Chat
     should include Thought Records, Important Days, attachment-derived text, and
     reflection summaries.
   - Entry AI analysis already uses related-entry memory and optional attachment
     context. Keep making source use visible and bounded.
5. Import and portability validation
   - The current import path supports OpenMynd `.xlsx`/`.zip` and Daylio `.csv`/`.daylio`.
   - No ChatGPT import adapter is planned. The remaining personal-data task is to fill
     the OpenMynd import workbook with real diary entries, run the staged review, and
     confirm import, revert, duplicate handling, and media/attachment expectations.
6. Testing and release gates
   - Backend unit/integration coverage is strong. Browser smoke coverage now includes
     login, registration, legal/cookie pages, auth recovery, OAuth onboarding,
     Dashboard, account deletion/restricted access, import review/commit/revert,
     Account/Customisation settings updates, Chat route scope/starter chips, and Chat
     context/stat/reply behavior. The remaining highest-risk browser gap is broader
     dark/light accessibility coverage.
   - Keep `npm run lint`, `npm run build`, `npm run test:e2e:smoke`, and
     `npm run test:e2e:a11y` as release-boundary frontend gates.

## Product Gaps To Keep Visible

- Chat: automated route-scope and starter-chip smoke exists. Remaining coverage should
  assert prior-entry context, privacy settings, source disclosure, rate limits,
  retry/error handling, and disabled-chat behavior.
- Personal import: end-to-end import of the user's real diary data through the OpenMynd
  XLSX template, including staged review before commit and safe revert.
- Dashboard: deeper analytics can later include stronger year-over-year insights,
  important-day comparisons, and clearer mental-health pattern summaries once the data
  set is stable.
- Attachments: audio transcription, attachment-derived metadata, and AI attachment
  context should remain opt-in and source-visible.
- Legal/compliance: privacy policy, terms, cookie consent, data deletion, export, and
  AI data-processing disclosures need production review.
- Payments/entitlements: billing, subscription state, free-tier limits, and AI-cost
  controls are not yet implemented. The initial delivery lane is captured in
  [public-saas-readiness-plan.md](./operations/public-saas-readiness-plan.md).
- Operations: production monitoring, backup alerts, database capacity alerts, and
  incident runbooks remain required.

## Cloud Migration Lane

Cloud work must proceed in dependency order rather than as parallel schema changes:

1. `#27` Select the target architecture/provider and document constraints.
   - Working decision captured in
     [ADR 0004](./adr/0004-cloud-database-architecture.md): managed PostgreSQL,
     Neon first for rehearsal, provider-portable via `DATABASE_URL`.
2. `#28` Build repeatable migration tooling and run a non-production rehearsal.
   - Initial SQLite audit/export and Postgres rehearsal loader tooling now exists under
     `server/scripts/`; a real Neon branch rehearsal still needs provider credentials.
3. `#30` Prove SQLite/cloud behavioral parity and define the cutover checklist.
   - Cutover gates and readiness validation are documented in
     [cloud-cutover-checklist.md](./operations/cloud-cutover-checklist.md).
4. `#73` Complete cutover and rollback rehearsal with owners and timings.
   - Operational sequence is defined in
     [cloud-cutover-runbook.md](./operations/cloud-cutover-runbook.md).
5. `#72` Run post-cutover integrity, performance, and operational verification.
   - Baseline capture and verification steps are documented in
     [post-cutover-verification.md](./operations/post-cutover-verification.md).
6. Close umbrella issues `#8` and `#62` only after the dependent work is complete.

Runtime migrations remain acceptable for local development, but no new cloud cutover
should depend on them as the sole production migration mechanism.
