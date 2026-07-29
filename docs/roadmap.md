# Roadmap

Updated: 29 July 2026. GitHub issues remain the delivery source of truth; this file
records their intended sequence rather than duplicating issue bodies.

## Future State

AI Diary should become a private, portable, clinically careful reflection system rather
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

Near-term work should avoid speculative provider integrations, broad visual redesigns,
or new AI surfaces until the existing accessibility, portability, and cloud-readiness
lanes are stable.

## Immediate Product Lane

1. `#109` On this day and anniversary resurfacing
   - Reuse existing entry, calendar, preview-deck, image, and return-route contracts.
   - Ship neutral resurfacing language plus global and per-entry hide controls.
2. `#110` Weekly and monthly reflection summaries
   - Add explicit, cost-aware AI generation with bounded source references and persisted
     summary provenance.
3. `#111` Gentle writing rhythm and opt-in reminders
   - Build on the in-app notification model with timezone-safe, non-punitive prompts.
   - Keep browser notifications out until permission and service-worker delivery are
     deliberately designed.

## Quality Lane

- Finish the manual matrix in `#52`: keyboard-only journeys, 200% zoom, short viewport
  overlays, light/dark data states, and VoiceOver/NVDA checks.
- Keep `npm run test:e2e:a11y` as a standard frontend gate alongside lint, build, and
  focused smoke tests.
- Complete `#66` chat observability and SLOs after the motivation feature sequence,
  unless production chat reliability becomes urgent sooner.

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
