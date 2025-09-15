### `CHANGELOG.md`
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffold with Angular frontend and Flask backend
- JWT authentication system with bcrypt password hashing
- Database models mapping to existing SQLite schema (users, configurations, dailydiary_entries, dreamdiary_entries)
- Core UI shell: top bar, side navigation, search bar, view toggle
- Entry list view with timeline scroller and responsive card grid
- Entry detail view with two-column layout (user content | AI response)
- Create entry screens for daily and dream diaries with "Leave it to AI" option
- OpenAI integration service for AI analysis
- API endpoints for auth, profile, entries CRUD, and AI analysis
- Profile management with demographics and AI settings
- Backend pytest suite with mocked OpenAI calls
- Comprehensive documentation (API, Architecture, Wireframes)

### Changed
- Password storage migrated from plaintext to bcrypt hashes

### Fixed
- N/A (initial release)