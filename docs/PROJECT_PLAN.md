Project name: AI Diary # AI D10) Excel Import System: Secure bulk import functionality for diary and dream entries via Excel templates. Features down## Database Schemates from Settings>Import, NLTK-based parsing (not AI), upload hygiene validation, and AI response generation on-demand from Edit Entry page. Includes file size limits, security validation against scripts/escape characters, and clear user feedback for entries without AI responses.

## Operating Rhythm
- Each iteration: update CHANGELOG (Unreleased), run tests, commit with version + status, write `docs/tests/test-results-v*.md`.
- Process and relationship between user (human) and Copilot (AI in VSCode): User and/or Copilot suggest changes in clear Phases and tasks. Copilot clarifies with questions the needs or methods necessary to fulfill requests. User confirms. Copilot iterates the design, tests for compile errors, then hands over to user with a summary of changes and tests required. User hands back to Copilot with further iterations necessary. After iterations, Copilot suggests next steps and asks for clarification. User provides further direction, clarification, and asks for a repo commit. Copilot tags, iterates the version, updates the commit, and pushes to the repo. We are then ready for the next phase.

## Architecture

### Backend (Flask)
Structure:
```
server/
  app.py                 # create_app(), CORS, JWT setup
  routes/entries.py      # CRUD for daily + dream entries (separate endpoints or query param)
  routes/auth.py         # /register, /login (JWT)
  routes/profile.py      # get/update user profile
  routes/analyse.py      # POST text -> OpenAI -> returns structured analysis
  db/models.py           # SQLAlchemy models mapping to existing tables
  db/dao.py              # thin data access (if not using ORM per route)
  services/openai_svc.py # call OpenAI; return tags/keywords/people/summary etc.
  tests/                 # pytest for routes + services
```

### Frontend (Angular)
Structure:
```
client/src/app/
  core/           # top-bar, side-nav, auth guard, interceptors
  shared/         # search-bar, view-toggle, tag-input, hero-image
  auth/           # login, register
  profile/        # profile view/edit
  entries/
    list/         # list with search/filter/timeline
    detail/       # two-column view (left user text, right AI)
    create/       # create daily/dream entry, "Leave it to AI" option
  app.routes.ts
styles/           # theme + variables
```

## AI Analysis Pipeline
- **Daily entries**: take user_message → generate ai_response, extract daily_people_names, tags.
- **Dream entries**: map to fields: summary, interpretation, image_prompt, dream_people_names, tags, etc. (Do not overwrite existing user-edited fields unless the user triggers "Regenerate".)

## Testing Strategy
- **Backend**: pytest for auth, entries CRUD, analyse service (mock OpenAI).
- **Frontend**: Angular unit tests for EntriesService & key components; Playwright e2e (create→analyse→list).

## Deployment Configuration
- **.env usage**: OPENAI_API_KEY, DB_PATH, JWT_SECRET, CORS_ORIGINS.
- **(Optional)** Dockerfiles + k3s manifests later; not required to start.

## Development Guidelines
- **Version/commit convention**: vX.Y.Z / working|not-working / see test file.
- After each iteration you write test-results-vX.Y.Z.md (place in /docs/tests/) and paste key parts to the chat.
- The AI must always consult:
  - Project Plan (this document) for scope
  - test-results-vX.Y.Z.md for current issues
  - CHANGELOG.md for history and prior fixes

## Non-negotiables
- No schema changes. No column renames. Add only additive features that do not break existing DB.
- Full file paths and complete code blocks in outputs.
- British English in UI, comments, and docs.
- Keep styles consistent with wireframes (purple accent, spacing, typography).ary Project Plan

**Project name**: AI Diary  
**Architecture**: Angular client + Flask API + SQLite + OpenAI  
**Single-developer flow**: user + AI in VSCode  
**Constraint**: Work with the existing SQLite database (app.db) and its tables exactly as defined below.

## Objectives
- Angular client per wireframes; Flask API; OpenAI analysis; exact `app.db` mapping; basic auth/profile.

## Scope (do-not-break)
- British English; clear comments; full file paths in outputs.
- Use the existing schema created by the original Python script (see Section E). Do not rename columns or tables.
- Front end: Angular (standalone, Angular Material, SCSS).
- Back end: Flask + SQLite (via SQLAlchemy or parameterised sqlite3) + JWT auth.
- AI: OpenAI for analysis/classification; store outputs into the existing columns where applicable (e.g., ai_response, tags, daily_people_names, dream_people_names, image_prompt, etc.).
- Auth: Implement register/login against users table. Passwords are stored in users.password (TEXT). From now on store bcrypt hashes. If any legacy plaintext users exist, document a one-off migration path; do not auto-migrate without an explicit script.

## Milestones
1) Repo hygiene: README, CHANGELOG, docs/, .env.example
2) Backend scaffold: auth/profile/entries/analyse routes; JWT; OpenAI service (mockable)
3) Frontend shell: top bar, search, toggle, routing
4) Daily & Dream CRUD screens + list grid + timeline
5) AI analysis flows wired to DB columns
6) Polish: profile mapping, error states, loading indicators
7) Edit entry functionality: Allow editing existing entries with form pre-population and update API
8) Database migration: Migrate from local SQLite to a free, cloud-based database (e.g., Supabase or PlanetScale) that ensures security, scalability, and seamless integration with Flask and Angular.
9) Structured Diary Modules: Enhanced diary entries with guided prompts and structured templates. Includes dedicated entry types for Daily Activity Tracking, Thought Records, Behavioural Experiments, and Progress Reviews. Features guided prompts, structured templates, enhanced AI analysis, and progress tracking. Requires new database tables (structured_* series), enhanced UI with tabbed entry creation, and specialised AI prompts for guided reflection.
10) Excel Import System: Secure bulk import functionality for diary and dream entries via Excel templates. Features downloadable templates from Settings>Import, NLTK-based parsing (not AI), upload hygiene validation, and AI response generation on-demand from Edit Entry page. Includes file size limits, security validation against scripts/escape characters, and clear user feedback for entries without AI responses.
10) Excel Import System: Secure bulk import functionality for diary and dream entries via Excel templates. Features downloadable templates from Settings>Import, NLTK-based parsing (not AI), upload hygiene validation, and AI response generation on-demand from Edit Entry page. Includes file size limits, security validation against scripts/escape characters, and clear user feedback for entries without AI responses.Database migration: Migrate from local SQLite to a free, cloud-based database (e.g., Supabase or PlanetScale) that ensures security, scalability, and seamless integration with Flask and Angular.
9) CBT Self-Esteem Diary Modules: Structured therapeutic diary entries based on Melanie Fennell's "Overcoming Low Self-Esteem" worksheets. Includes dedicated entry types for Daily Activity Diary, Thought Records, Behavioural Experiments, and Progress Reviews. Features guided prompts, structured templates, therapeutic AI analysis, and progress tracking. Requires new database tables (cbt_* series), enhanced UI with tabbed entry creation, and specialised AI coaching prompts for therapeutic context.ngular client + Flask API + SQLite + OpenAI)
Single-developer flow (user + AI in VSCode).
Constraint: Work with the existing SQLite database (app.db) and its tables exactly as defined below.

Objectives
- Angular client per wireframes; Flask API; OpenAI analysis; exact `app.db` mapping; basic auth/profile.

Scope (do-not-break)
- British English; clear comments; full file paths in outputs.
- Use the existing schema created by the original Python script (see Section E). Do not rename columns or tables.
Front end: Angular (standalone, Angular Material, SCSS).
Back end: Flask + SQLite (via SQLAlchemy or parameterised sqlite3) + JWT auth.
- AI: OpenAI for analysis/classification; store outputs into the existing columns where applicable (e.g., ai_response, tags, daily_people_names, dream_people_names, image_prompt, etc.).
- Auth: Implement register/login against users table. Passwords are stored in users.password (TEXT). From now on store bcrypt hashes. If any legacy plaintext users exist, document a one-off migration path; do not auto-migrate without an explicit script.

Milestones
1) Repo hygiene: README, CHANGELOG, docs/, .env.example
2) Backend scaffold: auth/profile/entries/analyse routes; JWT; OpenAI service (mockable)
3) Frontend shell: top bar, search, toggle, routing
4) Daily & Dream CRUD screens + list grid + timeline
5) AI analysis flows wired to DB columns
6) Polish: profile mapping, error states, loading indicators
7) Edit entry functionality: Allow editing existing entries with form pre-population and update API
8) Database migration: Migrate from local SQLite to a free, cloud-based database (e.g., Supabase or PlanetScale) that ensures security, scalability, and seamless integration with Flask and Angular.
9) Future feature track: structured CBT diary modules derived from Melanie Fennell’s “Overcoming Low Self-Esteem” worksheets (with scope to add further titles). Initial focus on “Daily activity diary” plus logging templates for predictions vs. outcomes, anxious predictions, self-critical thought spotting/questioning, experimenting with new rules, and bottom-line reviews. Requires dedicated schema additions, UI templates, and content authoring support.

Operating Rhythm
- Each iteration: update CHANGELOG (Unreleased), run tests, commit with version + status, write `docs/tests/test-results-v*.md`.
- Process and relationship between user (human) and Copilot (AI in VSCode): User and/or Copilot suggest changes in clear Phases and tasks. Copilot clarifies with questions the needs or methods necessary to fulfill requests. User confirms. Copilot iterates the design, tests for compile errors, then hands over to user with a summary of changes and tests required. User hands back to Copilot with further iterations necessary. After iterations, Copilot suggests next steps and asks for clarification. User provides further direction, clarification, and asks for a repo commit. Copilot tags, iterates the version, updates the commit, and pushes to the repo. We are then ready for the next phase.
markdown


Backend (Flask)
2. Structure:
server/
  app.py                 # create_app(), CORS, JWT setup
  routes/entries.py      # CRUD for daily + dream entries (separate endpoints or query param)
  routes/auth.py         # /register, /login (JWT)
  routes/profile.py      # get/update user profile
  routes/analyse.py      # POST text -> OpenAI -> returns structured analysis
  db/models.py           # SQLAlchemy models mapping to existing tables
  db/dao.py              # thin data access (if not using ORM per route)
  services/openai_svc.py # call OpenAI; return tags/keywords/people/summary etc.
  tests/                 # pytest for routes + services


3. Frontend (Angular)
Structure:
client/src/app/
  core/           # top-bar, side-nav, auth guard, interceptors
  shared/         # search-bar, view-toggle, tag-input, hero-image
  auth/           # login, register
  profile/        # profile view/edit
  entries/
    list/         # list with search/filter/timeline
    detail/       # two-column view (left user text, right AI)
    create/       # create daily/dream entry, "Leave it to AI" option
  app.routes.ts
styles/           # theme + variables


4. AI analysis pipeline
Daily entries: take user_message → generate ai_response, extract daily_people_names, tags.
Dream entries: map to fields: summary, interpretation, image_prompt, dream_people_names, tags, etc. (Do not overwrite existing user-edited fields unless the user triggers “Regenerate”.)

5. Testing
Backend: pytest for auth, entries CRUD, analyse service (mock OpenAI).
Frontend: Angular unit tests for EntriesService & key components; Playwright e2e (create→analyse→list).

6. Deployment-ready basics
## Database Schema

### Existing Tables (must match exactly)

**users**
```sql
users(id PK, username TEXT NOT NULL, password TEXT NOT NULL,
      first_name TEXT, last_name TEXT, age INTEGER, sex TEXT, goals TEXT,
      dailydiary_api_key TEXT, dreamdiary_api_key TEXT,
      chatgpt_daily_diary_coachname TEXT, chatgpt_dream_diary_coachname TEXT)
```

**configurations**
```sql
configurations(id PK, user_id INTEGER FK→users.id,
               daily_diary_prompt TEXT, dream_diary_prompt TEXT)
```

**dailydiary_entries**
```sql
dailydiary_entries(id PK, user_id INTEGER FK→users.id,
                   entry_date DATE, entry_number INTEGER,
                   user_message TEXT, ai_response TEXT,
                   daily_people_names TEXT, tags TEXT)
```

**dreamdiary_entries**
```sql
dreamdiary_entries(id PK, user_id INTEGER FK→users.id,
                   entry_date DATE, entry_number INTEGER,
                   title TEXT, cast TEXT, location TEXT, period TEXT, emotion TEXT,
                   plot TEXT, symbols_and_imagery TEXT, insight TEXT, action TEXT,
                   other TEXT, summary TEXT, interpretation TEXT,
                   image_prompt TEXT, image_url TEXT,
                   dream_people_names TEXT, tags TEXT)
```

### Structured Diary Extension Tables (Milestone 9)

**structured_activity_entries**
```sql
structured_activity_entries(id PK, user_id INTEGER FK→users.id,
                    entry_date DATE, entry_number INTEGER,
                    title TEXT, activity_description TEXT,
                    predicted_mood INTEGER, actual_mood INTEGER,
                    predicted_pleasure INTEGER, actual_pleasure INTEGER,
                    predicted_achievement INTEGER, actual_achievement INTEGER,
                    notes TEXT, ai_response TEXT, tags TEXT)
```

**structured_thought_records**
```sql
structured_thought_records(id PK, user_id INTEGER FK→users.id,
                   entry_date DATE, entry_number INTEGER,
                   title TEXT, situation TEXT, emotion TEXT, intensity INTEGER,
                   automatic_thought TEXT, evidence_for TEXT, evidence_against TEXT,
                   balanced_thought TEXT, new_emotion TEXT, new_intensity INTEGER,
                   ai_coaching TEXT, tags TEXT)
```

**structured_behavioural_experiments**
```sql
structured_behavioural_experiments(id PK, user_id INTEGER FK→users.id,
                           entry_date DATE, entry_number INTEGER,
                           title TEXT, belief_to_test TEXT, experiment_plan TEXT,
                           predicted_outcome TEXT, actual_outcome TEXT,
                           learning_points TEXT, ai_guidance TEXT, tags TEXT)
```

**structured_progress_reviews**
```sql
structured_progress_reviews(id PK, user_id INTEGER FK→users.id,
                    entry_date DATE, entry_number INTEGER,
                    title TEXT, goals_review TEXT, achievements TEXT,
                    challenges TEXT, self_compassion_rating INTEGER,
                    next_steps TEXT, ai_encouragement TEXT, tags TEXT)
```

### Storage Notes
- tags, *_people_names may be stored as comma-separated strings for now.
- entry_number is a user-visible counter per day; do not repurpose.
