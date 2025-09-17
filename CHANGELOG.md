# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Nothing yet.

## [AIDIARY v0.10.2] - 2025-09-16

### Added
- Angular profile screen with full coverage of the `users` profile fields and supporting `ProfileService`.

### Changed
- Diary creation flow now supports daily and dream entries, runs AI analysis conditionally, and surfaces validation feedback.
- API documentation restored to `docs/API.md` and updated to describe the current payloads.

### Fixed
- Missing Angular module imports (top bar search, view toggle icons, side-nav divider) and incorrect relative path prevented the app from compiling.
- Daily/dream entry services now avoid sending `Bearer null` when unauthenticated.
- `/api/register` response now returns a `user` object to match the frontend contract and automated tests updated accordingly.

## [AIDIARY v0.1.0] - 2025-09-10

### Added
- Initial project scaffold with Angular frontend and Flask backend.
- JWT authentication system with bcrypt password hashing.
- Database models mapping to existing SQLite schema (users, configurations, dailydiary_entries, dreamdiary_entries).
- Core UI shell: top bar, side navigation, search bar, view toggle.
- Entry list view with timeline scroller and responsive card grid.
- Entry detail view with two-column layout (user content | AI response).
- Create entry screens for daily and dream diaries with "Leave it to AI" option.
- OpenAI integration service for AI analysis.
- API endpoints for auth, profile, entries CRUD, and AI analysis.
- Profile management with demographics and AI settings.
- Backend pytest suite with mocked OpenAI calls.
- Comprehensive documentation (API, Architecture, Wireframes).

### Changed
- Password storage migrated from plaintext to bcrypt hashes.

### Fixed
- N/A (initial release).
