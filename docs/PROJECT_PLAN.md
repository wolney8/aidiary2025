Project name: AI Diary (Angular client + Flask API + SQLite + OpenAI)
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
6) Tests: backend pytest; frontend unit + minimal e2e
7) Polish: profile mapping, error states, loading indicators
8) Future feature track: structured CBT diary modules derived from Melanie Fennell’s “Overcoming Low Self-Esteem” worksheets (with scope to add further titles). Initial focus on “Daily activity diary” plus logging templates for predictions vs. outcomes, anxious predictions, self-critical thought spotting/questioning, experimenting with new rules, and bottom-line reviews. Requires dedicated schema additions, UI templates, and content authoring support.

Operating Rhythm
- Each iteration: update CHANGELOG (Unreleased), run tests, commit with version + status, write `docs/tests/test-results-v*.md`.
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
.env usage: OPENAI_API_KEY, DB_PATH, JWT_SECRET, CORS_ORIGINS.
(Optional) Dockerfiles + k3s manifests later; not required to start.

C. Operating rhythm (your working process baked in)
Version/commit convention: vX.Y.Z / working|not-working / see test file.
After each iteration you write test-results-vX.Y.Z.md (place in /docs/tests/) and paste key parts to the chat.
The AI must always consult:
Project Plan (this document) for scope,
test-results-vX.Y.Z.md for current issues,
CHANGELOG.md for history and prior fixes.

D. Non-negotiables
No schema changes. No column renames. Add only additive features that do not break existing DB.
Full file paths and complete code blocks in outputs.
British English in UI, comments, and docs.
Keep styles consistent with wireframes (purple accent, spacing, typography).

E. Existing database schema (must match exactly)

users(id PK, username TEXT NOT NULL, password TEXT NOT NULL,
      first_name TEXT, last_name TEXT, age INTEGER, sex TEXT, goals TEXT,
      dailydiary_api_key TEXT, dreamdiary_api_key TEXT,
      chatgpt_daily_diary_coachname TEXT, chatgpt_dream_diary_coachname TEXT)

configurations(id PK, user_id INTEGER FK→users.id,
               daily_diary_prompt TEXT, dream_diary_prompt TEXT)

dailydiary_entries(id PK, user_id INTEGER FK→users.id,
                   entry_date DATE, entry_number INTEGER,
                   user_message TEXT, ai_response TEXT,
                   daily_people_names TEXT, tags TEXT)

dreamdiary_entries(id PK, user_id INTEGER FK→users.id,
                   entry_date DATE, entry_number INTEGER,
                   title TEXT, cast TEXT, location TEXT, period TEXT, emotion TEXT,
                   plot TEXT, symbols_and_imagery TEXT, insight TEXT, action TEXT,
                   other TEXT, summary TEXT, interpretation TEXT,
                   image_prompt TEXT, image_url TEXT,
                   dream_people_names TEXT, tags TEXT)

Storage notes:
tags, *_people_names may be stored as comma-separated strings for now.
entry_number is a user-visible counter per day; do not repurpose.
