# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.11.4] - 2025-10-03

### Added
- Tag pills on entry cards (maximum 2 displayed) with click-to-search functionality
- Structured display for dream entries in detail view (Plot, Cast, Location, Period, Emotion, Symbols & Imagery, Insight, Action, Other)
- Global search functionality accessible from any route via top-bar
- Enhanced search debugging and error handling

### Fixed
- **CRITICAL**: Search functionality infinite loading issue - search Observable wasn't being subscribed to
- Card boundary overflow issues with tag pills extending beyond card borders
- Search accessibility - now works from any page, not just /entries route
- Tag search functionality in both list and detail views
- Entry detail view now shows structured sections for dream entries instead of single text block

### Changed
- Increased entry card height from 400px to 420px to accommodate tag pills
- Enhanced card CSS with proper overflow controls and text truncation
- Updated PROJECT_PLAN.md with Edit Entry functionality as Milestone 7
- Improved AI response display for dreams (Summary and Interpretation sections)

### Technical
- Added proper Observable subscription to search service calls
- Enhanced search state management with loading/error handling
- Improved tag-based navigation with route parameter handling
- Added debugging infrastructure for search functionality
- Nothing yet.

## [AIDIARY v0.11.3] - 2025-09-29

### 🚀 Major Release: Comprehensive Search System Overhaul

#### 🔍 **Professional Search Experience**
- **Google UX Standard Result Count**: "About X results for 'query'" messaging with proper formatting
- **Complete Pagination System**: Matches ALL ENTRIES exactly with 8/16/32 page sizes, top and bottom controls, default 8 items
- **Smart Search History**: Session-based 6-item history with intelligent filtering and Google-style dropdown behavior
- **Advanced Error Handling**: Context-aware error messages, smart retry logic, and comprehensive HTTP status classification
- **Professional Loading States**: Skeleton cards matching exact result dimensions (303x350px) with shimmer animations

#### 🎯 **Search History Intelligence**
- **Dynamic Filtering**: Shows only history items that match typed characters, hides when no matches found
- **Visual Text Highlighting**: Red highlighting for matching characters in history items (HTML sanitization with DomSanitizer)
- **Individual Item Deletion**: X buttons on each history item for granular control
- **Smart Input Clearing**: Automatically clears search field when navigating away from results while preserving history
- **Material Design Animations**: Smooth dropdown transitions with cubic-bezier easing

#### 🛠 **Technical Architecture Improvements**
- **Enhanced SearchService**: Session storage management, reactive history streams, automatic query tracking
- **Robust State Management**: OnInit/OnDestroy lifecycle hooks with proper subscription cleanup
- **Form Control Excellence**: Proper reactive form implementation with programmatic enable/disable states
- **Memory Leak Prevention**: Comprehensive RxJS subscription management with takeUntil pattern

#### 📱 **User Experience Enhancements**
- **Always-Visible Pagination**: Shows for any number of results (not just 9+) for consistent UX
- **Responsive Design**: Mobile-optimized search history dropdown with proper touch interactions
- **Professional Error States**: Glass-morphism error cards with actionable suggestions and retry functionality
- **Loading Performance**: 8-second timeout with Google UX standards for search operations

#### 🎨 **Material Design Integration**
- **Enhanced Visual Hierarchy**: Proper spacing, typography, and color schemes throughout search interface
- **Interactive Feedback**: Hover states, focus indicators, and smooth transitions for all search components
- **Accessibility Ready**: ARIA labels, screen reader support, and keyboard navigation patterns
- **Professional Polish**: Consistent styling with entry list components for seamless user experience

## [AIDIARY v0.11.2] - 2025-09-25

### 🔍 Major Feature: Advanced Search Results Interface

#### Added
- **Enhanced Search Results Display**: Complete redesign with proper title highlighting instead of body text overflow
- **Red Search Term Highlighting**: Implemented secure HTML sanitization bypass for highlighting search matches in red with bold formatting
- **Material Design Dropdown Structure**: Added structured expanded details with Material icons (bookmark, calendar, tags, edit, psychology)
- **Smart Visual Connectors**: Blue circular chevron indicators showing clear connection between selected cards and expanded details
- **Intelligent Card Positioning**: Dynamic positioning system that prevents expanded cards from going off-screen with grid-aware alignment
- **Uniform Card Sizing**: Consistent 350px height for search cards and 400px for standard entry cards with proper flexbox content distribution
- **Smooth Animation System**: 300ms cubic-bezier animations for card expansion, collapse, and smooth scroll-to-view functionality
- **Click-Away Functionality**: Expanded cards close when clicking outside, providing intuitive interaction patterns

#### Enhanced
- **Search Result Grid Layout**: Improved CSS Grid system with proper spacing and visual hierarchy
- **Entry Cards Centering**: 1-2 cards now center beautifully in standard entry views while 3+ maintain left alignment
- **Visual Selection Feedback**: Selected cards show blue borders and enhanced shadows for clear state indication
- **Grid-Aligned Expanded Cards**: Expanded cards align perfectly within grid boundaries using dynamic CSS custom properties
- **Responsive Positioning**: Smart positioning prevents content overflow on different screen sizes

#### Technical Improvements
- **HTML Security**: Implemented Angular DomSanitizer for safe HTML rendering of highlighted search terms
- **Dynamic CSS Properties**: Custom CSS variables for responsive positioning (--offset-x, --expanded-width)
- **Animation Performance**: Hardware-accelerated transforms with translateZ(0) for smooth 60fps animations
- **Browser Compatibility**: :has() selector with JavaScript fallbacks for older browser support
- **Clean State Management**: Proper cleanup of positioning classes and styles when switching between expanded cards

## [AIDIARY v0.11.1] - 2025-09-23

### 🎉 Major Feature: Advanced Timeline Navigation & Entry Management

#### Added
- **Complete Timeline System**: 5-phase implementation with pagination (2x4 card grid), dynamic timeline generation, entry count badges, view coordination, and scroll limits
- **Smart Navigation Buttons**: First/Today buttons with intelligent date selection and timeline centering
- **Timeline Animation System**: Smooth 300ms animations with ease-out curves for professional visual feedback
- **Date Pre-population**: New entries automatically inherit selected timeline date with UK format support
- **Entry Type Auto-selection**: Create entry form pre-selects Daily/Dream based on current view filter
- **Memory-Safe Animation**: Proper cleanup with ngOnDestroy lifecycle management

#### Enhanced
- **Timeline Scroller**: Dynamic month generation based on actual entry data with future month limits
- **View Toggle Logic**: ALL/DAILY/DREAMS buttons now filter current selection instead of jumping to recent entries
- **Entry Count Badges**: Real-time count display for each month in timeline with proper filtering
- **Navigation UX**: First button jumps to earliest entry month, Today button centers current month
- **Dream Entry Creation**: Fixed critical bug where dream entries were saving as daily entries
- **Pagination Control**: Proper 8-entries-per-page (2 rows × 4 cards) with Material paginator

#### Technical Improvements
- **Timeline State Management**: Preserved selection across view changes with intelligent fallback
- **Animation Framework**: RequestAnimationFrame-based smooth scrolling with performance optimization
- **Query Parameter Handling**: Enhanced routing with date and type parameter support
- **Component Architecture**: Improved separation of concerns between timeline, pagination, and filtering
- **Database Integrity**: Proper dream entry API endpoint verification and testing

#### Fixed
- **Critical Dream Entry Bug**: Dream entries now save correctly to dreamdiary_entries table instead of daily entries
- **View Toggle Behavior**: Buttons no longer jump to recent entries, properly filter current timeline selection
- **Timeline Selection**: Preserved month selection when switching between ALL/DAILY/DREAMS views
- **Entry Type Detection**: New entry form correctly determines type from navigation context
- **Timeline Centering**: First/Today buttons now properly center selected months in timeline scroller

#### User Experience
- **Visual Feedback**: Smooth animations provide clear indication of timeline movements and selections
- **Intuitive Navigation**: First/Today buttons with intelligent month centering and entry filtering
- **Responsive Design**: Maintains 2x4 card grid layout with proper pagination controls
- **Smart Defaults**: Entry creation pre-populates dates and types based on user context

### 🔧 Technical Details
- **Animation System**: 300ms duration with cubic ease-out easing for natural movement
- **Timeline Logic**: Dynamic range calculation from earliest entry to 2 months future limit
- **State Preservation**: Maintains timeline selection across view toggles and navigation actions
- **Memory Management**: Proper cleanup of animation frames and event listeners
- **API Integration**: Verified dream entry endpoints with proper database table routing

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
