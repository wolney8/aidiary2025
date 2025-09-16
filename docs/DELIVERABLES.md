Deliverables

1. Folder & file scaffold (must be created by the AI with code)
client/ Angular app with standalone components & Angular Material.
server/ Flask app with blueprints, JWT, and SQLite integration.
docs/ with:
ARCHITECTURE.md (data flow, key modules)
API.md (routes, request/response bodies mapped to the existing schema)
WIREFRAMES.md (thumbnails + mapping notes when you add PNGs)
tests/ subfolder: keep your test-results-v*.md here
Root: .env.example, CHANGELOG.md, README.md.

2. Back end
Auth: POST /api/register, POST /api/login (JWT), GET/PUT /api/profile.
Daily entries: GET/POST /api/daily, GET/PUT/DELETE /api/daily/:id.
Dream entries: GET/POST /api/dreams, GET/PUT/DELETE /api/dreams/:id.
Analyse: POST /api/analyse → returns fields appropriate to daily or dream mode.
Health: GET /health.

3. Front end
Shell: top bar, side nav, search, pill toggle (All | Daily | Dreams).
List: timeline scroller + responsive card grid with icons/titles/dates.
Detail: two-column (left: user content; right: AI response) + hero image + metadata bar.
Create: with “Leave it to AI” switch.
Profile: map profile fields 1:1 to users table columns you expose.
Auth: login/register screens; route guards.

4. AI integration
Daily: populate ai_response, daily_people_names, tags.
Dreams: populate summary, interpretation, image_prompt, dream_people_names, tags, optionally image_url if your image flow is ready (can be placeholder).

5. Docs & processes
CHANGELOG.md updated every iteration with “Unreleased” → grouped changes.
docs/tests/test-results-vX.Y.Z.md added by you after each run; AI must reference it.
docs/API.md includes exact payloads and column mappings.

6. Tests
Backend: pytest for happy paths + errors (auth, CRUD, analyse with mocked OpenAI).
Frontend: unit tests for services & UI components; Playwright e2e minimal scenario.