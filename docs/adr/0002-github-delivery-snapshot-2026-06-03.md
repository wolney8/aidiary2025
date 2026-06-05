# ADR 0002: GitHub Delivery Snapshot on 3 June 2026

## Status

Accepted as a working backlog snapshot for local reference.

## Context

The active delivery plan now lives partly in GitHub issues and milestones for `wolney8/aidiary2025`. This repository needs a local summary that future Codex sessions can read without re-discovering the current backlog structure from scratch.

Data source used for this snapshot:

- GitHub milestones API: `https://api.github.com/repos/wolney8/aidiary2025/milestones?state=all&per_page=100`
- GitHub issues API: `https://api.github.com/repos/wolney8/aidiary2025/issues?state=all&per_page=100`

Snapshot date:

- 3 June 2026
- Reviewed against live GitHub issue state again on 4 June 2026

## Decision

Treat this file as a local orientation note only. GitHub remains the source of truth for issue state.

## Milestone summary

### Closed milestones

- `M0: Repository Stabilisation`
  - 1 closed, 0 open
- `M8: AI reliability and context quality`
  - 1 closed, 0 open
- `M9: Edit parity and date consistency`
  - 3 closed, 0 open

### Open milestones

- `M1: Complete M10 Excel Import`
  - 5 closed, 3 open
- `M2: Logout Inactivity Timer`
  - 3 closed, 4 open
- `M9: CBT Structured Diary`
  - 0 closed, 4 open
- `M8: Cloud DB Migration`
  - 0 closed, 4 open
- `M11: AI Chat Companion`
  - 0 closed, 8 open
- `M12: UI/UX Enhancements`
  - 0 closed, 8 open
- `M13: Release Governance and Repo Hygiene`
  - 0 closed, 3 open
- `M14: Chat Companion GA and Reliability`
  - 0 closed, 2 open
- `M15: Settings and Personalisation Completion`
  - 0 closed, 2 open
- `M16: Integrations and Data Portability`
  - 0 closed, 3 open
- `M17: Cloud Database Cutover`
  - 0 closed, 2 open

## Notable completed work

- `#1` `[Phase 1] Complete M10 Excel import feature`
- `#5` `[Phase 0] Repository stabilisation and hygiene`
- `#58` `AI context memory: add per-entry metadata header and recent-entry context injection`
- `#59` `Edit entry parity: allow date and mood updates for daily and dream entries`
- `#60` `Date formatting consistency: standardise DD/MM/YYYY across app views`
- `#61` `Runtime DB migration: add mood/ai_style columns to daily and dream tables`

## Active backlog by theme

### Legacy phase-style issues still open

- `#6` `[Phase 2] Inactivity logout timer and warning modal`
- `#7` `[Phase 3] M9 CBT structured diary modules`
- `#8` `[Phase 4] M8 cloud DB migration planning and execution`
- `#10` `[Phase 1][CP2] Search and filter flow stabilisation`
- `#16` `[Phase 1][CP3] Card readability and tag handling`
- `#17` `[Phase 1][CP4] Entry detail formatting and movement`
- `#20` `[Phase 2] Session timeout integration and e2e verification`
- `#21` `[Phase 2] Inactivity service and activity tracking core`
- `#22` `[Phase 2] Warning modal UX and accessibility`
- `#23` `[Phase 3] CBT data model and migration plan`
- `#24` `[Phase 3] CBT insights integration and QA`
- `#26` `[Phase 3] CBT guided UI workflow implementation`
- `#27` `[Phase 4] Cloud migration architecture and target selection`
- `#28` `[Phase 4] Data migration tooling and rehearsal`
- `#30` `[Phase 4] Cloud parity tests and cutover checklist`

These are mostly labelled `status:blocked` in GitHub and appear to represent older structured phase work.

### Chat companion delivery

- `#43` Chat context retrieval service
- `#44` Chat API routes
- `#46` Chat companion UI component
- `#76` Ensure FAB visibility and mounting in app shell
- `#47` OpenAI chat service and SSE streaming
- `#48` DB migration for `chat_messages`
- `#49` Chat Angular service and interfaces
- `#50` Rate limiting and token budget guardrails
- `#66` Chat observability and SLOs
- `#68` Chat reliability hardening

### UI and UX enhancements

- `#51` Auth guard and logged-out menu visibility
- `#52` WCAG 2.2 AA audit
- `#53` Dark/light mode and theme presets
- `#54` User profile settings: pronouns, display name, AI style
- `#55` Photo uploads
- `#64` Finish Settings experience and remove remaining “Coming soon” gaps
- `#84` Entries view filter affordance and calendar return controls
- `#85` Create/Edit entry date fields: use UK format and human-readable date labels
- `#88` Important days: user-configurable personal dates and reminders context
- `#90` Add bottom-page navigation or back-to-top control on long entry screens
- `#91` Dream entries: AI image generation, retry flow, and prompt-hover metadata
- `#79` Diary motivation ideas backlog

### Settings and personalisation

- `#69` Settings consolidation plan
- `#71` Personalisation schema and API completion

### Integrations and portability

- `#63` Import/sync from Daylio and other diary apps
- `#70` Integration adapters framework
- `#74` Import/export parity and data portability contract
- `#77` Bulk delete all entries with export guard rails and destructive-action warnings
- `#92` Import: allow multiple same-day entries and refine duplicate detection
- `#93` Import: improve duplicate skip reporting with date, title, and reason
- `#94` Import: review skipped entries and allow manual re-add
- `#89` Public holidays and locale-based event calendar integration

### Cloud database and operational readiness

- `#62` Migrate database to external cloud service
- `#72` Post-cutover verification and performance baseline
- `#73` Cloud DB cutover runbook and rollback rehearsal

### Governance and repo hygiene

- `#65` Branch lifecycle policy
- `#67` Milestone closure governance checklist
- `#80` Registration and authentication security review

### AI entry analysis follow-up

- `#83` Save & Analyse does not persist AI response and tags on new entries
- `#86` Improve diary and dream analysis prompt quality, structure, and model reliability
- `#87` Run NLTK enrichment on entry save before AI analysis, then supplement from AI output

## Newly added issues in this cycle

- `#75` addressed a real current UI gap in All Entries month view card centring.
- `#76` makes chat FAB visibility explicit rather than implicit inside chat UI delivery.
- `#77` adds destructive bulk-delete safety aligned with export and portability work.
- `#78` introduced a concrete diary adherence calendar view.
- `#81` extends the calendar view with an in-place preview interaction for day entry icons.
- `#82` tracks date and type preservation when creating entries from calendar-driven contexts.
- `#83` tracks the create-and-analyse persistence bug for AI responses and derived metadata.
- `#84` tracks stronger filter affordance and entries-view control consistency.
- `#85` tracks UK date formatting and human-readable date labels in create and edit flows.
- `#86` tracks prompt, model, and structured-output improvements for diary and dream analysis quality.
- `#87` tracks runtime NLTK enrichment on normal save/analyse flows, with user text taking priority over AI-derived enrichment.
- `#88` adds user-configurable important days such as anniversaries, birthdays, and milestone dates.
- `#89` adds locale-based public holiday integration and caching.
- `#90` adds bottom-page navigation support for long entry screens.
- `#91` adds dream-entry AI image generation, retry flow, and prompt-hover metadata.
- `#92` tracks the import duplicate-rule fix so same-day entries are allowed and only narrower duplicates are skipped by default.
- `#93` tracks clearer import duplicate reporting so users can see exactly what was skipped and why.
- `#94` tracks a follow-up review flow so skipped import rows can be inspected and manually re-added.
- `#79` captures wider retention and motivation ideas without forcing immediate implementation.
- `#80` creates an explicit security review track for registration and authentication.

## Implemented locally, GitHub sync pending

- `#75` is implemented on `main` locally and is now closed on GitHub.
- `#78` is implemented on `main` locally and is now closed on GitHub.
- `#81` is implemented on `main` locally and is now closed on GitHub.
- `#82` is implemented on `main` locally and is now closed on GitHub.

## Interpretation

- The repository has two overlapping planning layers:
  - older phase-numbered work
  - newer milestone-driven product and operations work
- Work on chat reliability, settings completion, portability, and cloud readiness appears to be the current forward-looking roadmap.
- AI analysis work now has a split between:
  - bug-fix and persistence work in `#83`
  - quality/prompt work in `#86`
  - runtime NLTK enrichment in `#87`
- Calendar and date-driven planning work is expanding across:
  - `#78`, `#81`, `#82`, `#84`, `#85`
  - `#88` personal important days
  - `#89` public holidays and locale-aware event context
- Entry presentation and media work now also includes:
  - `#90` bottom-page navigation support
  - `#91` dream-entry AI image generation and image UX
- Some older milestone names reuse numbers for different meanings:
  - `M8` appears both as `Cloud DB Migration` and a separate closed milestone named `AI reliability and context quality`
  - `M9` appears both as `CBT Structured Diary` and a separate closed milestone named `Edit parity and date consistency`

This naming overlap requires care when discussing priorities.

## Operational guidance for future sessions

- Check GitHub again before acting on issue status because this file is only a snapshot.
- Prefer milestone title plus issue number when referring to work, not milestone number alone.
- Treat GitHub as authoritative for open/closed state.
- Note that `#87` is currently assigned to the closed milestone `M8: AI reliability and context quality`, so milestone governance may need tidying if future AI analysis work should remain visibly open in GitHub.

## To confirm

- Which of the older blocked phase issues still represent active delivery commitments.
- Whether milestone-number reuse should be cleaned up in GitHub for clarity.
