# docs/ARCHITECTURE.md
# Architecture Overview

## Frontend: Angular (standalone + Material + SCSS)
- `core/`  : TopBar, SideNav, auth guard/interceptor, models
- `shared/`: SearchBar, ViewToggle, TagInput, HeroImage (wireframe components)
- `auth/`  : Login, Register
- `profile/`: Profile view/edit (maps to `users`)
- `entries/`
  - `list/`   : timeline + card grid (All/Daily/Dreams)
  - `detail/` : two-column detail (left: user, right: AI) + hero image + metadata
  - `create/` : "Leave it to AI" option; posts to API then calls `/analyse`

## Backend: Flask + SQLite
- `routes/auth.py`    : register/login (JWT), bcrypt storage
- `routes/profile.py` : read/update user profile
- `routes/entries.py` : CRUD for `dailydiary_entries` and `dreamdiary_entries`
- `routes/analyse.py` : OpenAI analysis service (`services/openai_svc.py`)
- `db/models.py`      : SQLAlchemy models mirroring **existing** schema
- `tests/`            : pytest with temp DB; OpenAI mocked

## Data Flow (Daily)
1. UI create → POST `/api/daily` → row inserted
2. User clicks "Analyse" → POST `/api/analyse` → AI fields returned
3. UI PUT `/api/daily/:id` updating `ai_response`, `tags`, `daily_people_names`

## Data Flow (Dream)
1. UI create → POST `/api/dreams`
2. Analyse → `/api/analyse` → fill `summary`, `interpretation`, `image_prompt`, `dream_people_names`, `tags`
3. UI PUT `/api/dreams/:id` with AI fields

## Security
- JWT in `Authorization: Bearer <token>`
- CORS restricted by `CORS_ORIGINS`
- `.env` for `JWT_SECRET`, `DB_PATH`, `OPENAI_API_KEY`

## Constraints
- **Do not** change table/column names in `app.db`
- Use British English for UI and comments