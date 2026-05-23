# Project Plan

## Overview

**Project name**: AI Diary  
**Architecture**: Angular client + Flask API + SQLite + OpenAI  
**Delivery mode**: Single-developer workflow (user + Copilot in VS Code)

### Goals

- Deliver a stable AI Diary platform with clear daily and dream journalling workflows.
- Keep compatibility with the existing SQLite database and established API contracts.
- Maintain British English across user-facing text, documentation, and comments.
- Ship in milestone waves with practical validation after each wave.

## Architecture

### Frontend

- Angular standalone application with Angular Material and SCSS.
- Core shell includes routing, navigation, authentication views, and entry workflows.
- Feature areas: auth, profile, settings, entries list/detail/create, shared UI components.

### Backend

- Flask API with route modules for auth, profile, entries, and analysis.
- SQLite-backed data access via parameterised sqlite3 and lightweight service helpers.
- OpenAI integration isolated in service code for testability and safer error handling.
- No SQLAlchemy dependency in the active runtime architecture.

### Data and Integration Notes

- Existing SQLite schema remains authoritative unless an explicit migration milestone states otherwise.
- AI outputs populate existing fields such as ai_response, tags, and people-name metadata.
- Authentication remains JWT-based with bcrypt password hashing for stored credentials.

## Milestones

### Milestone 0 — Repository stabilisation and hygiene

- Remove stale or conflicting scaffolding and duplicated documentation blocks.
- Resolve compile blockers in critical frontend surfaces.
- Align dependency baselines for backend and frontend patch lanes.
- Reconfirm test and lint pathways before continuing feature delivery.

### Milestone 1 — Repository and delivery hygiene

- Keep README, CHANGELOG, docs, and environment templates current.
- Standardise version and test-report updates per iteration.

### Milestone 2 — Backend foundation

- Stabilise auth/profile/entries/analyse routes.
- Keep OpenAI service mockable for tests.
- Preserve SQLite compatibility and existing endpoint behaviour.

### Milestone 3 — Frontend shell and routing

- Maintain top bar, side nav, route protection, and core app layout.
- Ensure entry points for authentication and diary features remain stable.

### Milestone 4 — Daily and dream CRUD delivery

- Complete create, read, update, and list workflows for diary entries.
- Preserve two-column detail view and timeline/grid experiences.

### Milestone 5 — AI analysis integration

- Wire analysis responses into daily and dream entry flows.
- Prevent unintended overwrites of user-edited content unless explicitly requested.

### Milestone 6 — Product polish and resilience

- Improve loading, error states, profile mapping, and UX consistency.
- Tighten edge-case handling in API and UI layers.

### Milestone 7 — Edit entry improvements

- Maintain form pre-population and robust update flows.
- Keep optimistic updates and server reconciliation predictable.

### Milestone 8 — Managed database migration track

- Plan migration from local SQLite to a secure hosted database when approved.
- Ensure backward-compatible rollout strategy and rollback documentation.

### Milestone 9 — Structured diary modules

- Add guided, structured diary templates for therapeutic reflection workflows.
- Introduce any required schema additions in controlled migrations.
- Expand UI and analysis prompts to support structured modules.

### Milestone 10 — Excel import system

- Deliver secure bulk import for daily and dream entries from Excel templates.
- Include validation, file-size limits, and clear user feedback.
- Use deterministic parsing and provide post-import analysis triggers where needed.

## Constraints

- Preserve existing SQLite tables and column semantics unless a migration milestone explicitly changes them.
- Avoid breaking API contracts already used by the frontend.
- Keep dependency upgrades within approved major-version lanes during stabilisation.
- Record meaningful test outcomes for each iterative release.

## Operating Rhythm

- Each iteration updates CHANGELOG and relevant handover/test documents.
- Each implementation wave includes targeted validation for touched areas.
- User confirms direction; Copilot implements, validates, and reports deltas.
- Commits and pushes happen only after explicit user approval.
