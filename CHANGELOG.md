# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
- Nothing yet.

## [AIDIARY v0.11.0] - 2025-09-23

### 🎉 Major Feature: Entry Title Support System

#### Added
- **Complete title field support** for daily diary entries
- **Database schema enhancement**: Added `title` column to `dailydiary_entries` table
- **Smart migration system**: Auto-populated all 163 existing entries with date-based titles
- **Frontend title management**: Entry creation, display, and editing with title support
- **Backward compatibility**: Seamless handling of both old and new entry formats
- **Enhanced login error messaging**: User-friendly error messages for authentication failures

#### Enhanced
- **Entry Creation**: Title input field now saves to separate database column
- **Entry Display**: List and detail views prioritize title field with intelligent fallbacks
- **API Endpoints**: All entry endpoints support title field (GET/POST/PUT)
- **Search Integration**: Search functionality works with title fields
- **Data Migration**: Safe, tested migration with comprehensive rollback plan

#### Technical Improvements
- **Database Migration Scripts**: Step-by-step migration with testing and verification
- **API Backward Compatibility**: Handles both old and new entry formats
- **Frontend Resilience**: Graceful handling of entries with/without titles
- **Comprehensive Testing**: Migration verification and frontend testing guides
- **Project Documentation**: Detailed TODO tracking and implementation guides

#### Fixed
- **Logo Navigation**: Fixed logo redirect to navigate to `/entries` instead of `/login`
- **Login UX**: Added loading states, input validation, and comprehensive error handling
- **Entry Structure**: Standardized title/content separation for better organization

#### Developer Experience
- **Migration Safety**: Complete backup and rollback system
- **Testing Framework**: Automated verification scripts and manual testing guides
- **Documentation**: Step-by-step implementation tracking and testing procedures

### 🔧 Technical Details
- **Database**: SQLite schema update with title column addition
- **Backend**: Flask API endpoints enhanced for title field support
- **Frontend**: Angular components updated for title display and management
- **Migration**: 163 entries successfully migrated with zero data loss

## [AIDIARY v0.10.7.1] - 2025-09-23

### Fixed
- Enhanced login form with comprehensive error handling and user feedback
- Added loading states and input validation for better user experience

## [AIDIARY v0.10.7] - 2025-09-22

### Fixed
- TopBar logo navigation now redirects to `/entries` instead of `/login`
- Improved search functionality and component syntax fixes

## [AIDIARY v0.10.6] - 2025-09-19

### Changed
- Refined the top-bar search to match the Google-style pill (white, rounded, centred) and moved the filter indicator into the icon badge.
- Filter panel now stacks options vertically per the wireframes.

## [AIDIARY v0.10.5] - 2025-09-19

### Added
- Angular 17 reactive search form in the top bar with inline filter panel (tags/date/keywords/people) and active filter indicator.

### Changed
- Search bar centred per wireframes; filter trigger now sits within the input and collapses after each search.

### Fixed
- Removed legacy search component usage; top bar now uses the new form-based control exclusively.

## [AIDIARY v0.10.4] - 2025-09-18

### Added
- Navigation guard on the New Entry screen (with window unload protection) and a Cancel/Upload Image flow matching the wireframes.
- Tag chips input with remove/add behaviour plus backend persistence for both diary types.
- User menu in the top bar that exposes Settings and Logout alongside the current user name and release label (`AIDIARY v0.10.4 DEV`).
- Dynamic timeline months and date formatting in UK style (`dd/MM/yyyy`).

### Changed
- Daily entries now capture a title separately (stored in the first paragraph) so lists/detail views present headings consistently.
- New entry buttons adapt to the AI toggle: manual mode shows Upload Image + Save Entry; AI mode only exposes Save & Analyse.
- Search layout centred with adjacent filter action, and the auth service persists the signed-in user across reloads.

### Fixed
- Prevented future dates in the create form and ensured backend inserts propagate supplied tags.
- Daily detail view now separates title/body text correctly when rendering stored entries.

## [AIDIARY v0.10.3] - 2025-09-17

### Added
- Reactive search bar component using Angular Material form controls.
- "New Entry" action on the entries list plus query-string support for Daily/Dream filtering.

### Changed
- Authentication service retains the logged-in user across reloads and redirects to the login screen on logout.
- Route guard and bootstrap logging cleaned up now that the app starts reliably.

### Fixed
- Backend now resolves the SQLite database path relative to the server package, preventing "no such table" errors against `server/db/app.db`.

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
