# Roadmap

Updated: 21 July 2026. GitHub issues remain the delivery source of truth; this file
records their intended sequence rather than duplicating issue bodies.

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
3. `#30` Prove SQLite/cloud behavioral parity and define the cutover checklist.
4. `#73` Complete cutover and rollback rehearsal with owners and timings.
5. `#72` Run post-cutover integrity, performance, and operational verification.
6. Close umbrella issues `#8` and `#62` only after the dependent work is complete.

Runtime migrations remain acceptable for local development, but no new cloud cutover
should depend on them as the sole production migration mechanism.
