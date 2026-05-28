# API Documentation

Base URL: `http://localhost:5001/api`

## Authentication

### POST /api/register

Create a new user account.

**Request:**

```json
{
  "username": "johndoe",
  "password": "securePassword123",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response (201):**

```json
{
  "token": "jwt-token",
  "user": {
    "id": 1,
    "username": "johndoe",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Database Mapping:**

- `username` → `users.username`
- `password` (bcrypt) → `users.password`
- `first_name` → `users.first_name`
- `last_name` → `users.last_name`

### POST /api/login

Authenticate an existing user and obtain a JWT.

**Request:**

```json
{
  "username": "johndoe",
  "password": "securePassword123"
}
```

**Response (200):**

```json
{
  "token": "jwt-token",
  "user": {
    "id": 1,
    "username": "johndoe",
    "first_name": "John"
  }
}
```

## Profile

### GET /api/profile

Fetch the authenticated user's profile. Requires `Authorization: Bearer <token>`.

**Response (200):**

```json
{
  "id": 1,
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "age": 30,
  "sex": "male",
  "goals": "Personal growth",
  "dailydiary_api_key": "key123",
  "dreamdiary_api_key": "key456",
  "chatgpt_daily_diary_coachname": "Daily Coach",
  "chatgpt_dream_diary_coachname": "Dream Coach"
}
```

### PUT /api/profile

Update profile fields for the authenticated user.

**Request:**

```json
{
  "first_name": "John",
  "age": 31,
  "goals": "Updated goals"
}
```

## Daily Entries

### GET /api/daily

List all daily entries for the authenticated user (most recent first).

### POST /api/daily

Create a new daily entry.

**Request:**

```json
{
  "entry_date": "2025-09-15",
  "user_message": "Today was productive..."
}
```

**Response (201):**

```json
{
  "id": 14,
  "entry_date": "2025-09-15",
  "entry_number": 1
}
```

### GET /api/daily/:id

Fetch a single daily entry belonging to the current user.

### PUT /api/daily/:id

Update daily entry fields (user content and AI enrichment).

**Request:**

```json
{
  "user_message": "Updated notes",
  "ai_response": "Supportive feedback...",
  "daily_people_names": "Sarah,Tom",
  "tags": "work,productivity"
}
```

### DELETE /api/daily/:id

Delete a daily entry. Returns `204 No Content` on success.

## Dream Entries

### GET /api/dreams

List all dream entries for the authenticated user (most recent first).

### POST /api/dreams

Create a new dream entry.

**Request:**

```json
{
  "entry_date": "2025-09-14",
  "title": "Flying dream",
  "plot": "I was flying over mountains...",
  "emotion": "Excited"
}
```

**Response (201):**

```json
{
  "id": 21,
  "entry_date": "2025-09-14",
  "entry_number": 1
}
```

### GET /api/dreams/:id

Fetch a single dream entry belonging to the current user.

### PUT /api/dreams/:id

Update dream entry narrative and AI enrichment fields.

**Request:**

```json
{
  "plot": "Expanded dream details",
  "summary": "A dream about freedom...",
  "interpretation": "This suggests...",
  "image_prompt": "Person flying over mountains at night",
  "dream_people_names": "Unknown figure",
  "tags": "flying,freedom,mountains"
}
```

### DELETE /api/dreams/:id

Delete a dream entry. Returns `204 No Content` on success.

## AI Analysis

### POST /api/analyse

Analyse a diary entry and return structured AI insights. Requires `Authorization: Bearer <token>`.

**Request:**

```json
{
  "mode": "daily",
  "text": "Today I met Sarah at work..."
}
```

**Response when `mode` = "daily":**

```json
{
  "ai_response": "It sounds like you had a productive meeting...",
  "tags": "work,meeting,collaboration",
  "daily_people_names": "Sarah"
}
```

**Response when `mode` = "dream":**

```json
{
  "summary": "A dream about professional relationships...",
  "interpretation": "Meeting Sarah in your dream may represent...",
  "image_prompt": "Two people in a professional setting having a meeting",
  "tags": "work,relationships,communication",
  "dream_people_names": "Sarah"
}
```

## Excel Import

### 1) POST /api/import/upload schema contract

Accepts a multipart upload with field name `file` containing a `.xlsx` workbook.

Accepted sheet names:

- Daily: `Daily`
- Dreams: `Dreams` or `Dream`

Daily sheet column contract:

- Required: `date`
- Optional: `title`, `content` (alias: `user_message`), `tags`

Dreams sheet column contract:

- Required: `date`
- Optional: `title`, `plot`, `cast`, `location`, `period`, `emotion`, `symbols_and_imagery`, `insight`, `action`, `other`, `tags`

### 2) GET /api/import/history

Returns import history for the authenticated user.

Auth required: JWT Bearer token (`Authorization: Bearer <token>`).

Query params: none.

Response (200):

```json
[
  {
    "id": 123,
    "imported_at": "2026-05-26T09:15:00Z",
    "filename": "journal_import.xlsx",
    "file_size_bytes": 20480,
    "inserted_daily": 10,
    "skipped_daily": 2,
    "inserted_dreams": 4,
    "skipped_dreams": 1,
    "warnings": "[\"Daily sheet row 5: skipped — invalid or missing date (\\\"\\\").\"]",
    "status": "partial"
  }
]
```

### 3) Upload status values

Possible `status` values returned by `POST /api/import/upload` and stored in import history:

- `success` - all rows in the file were inserted
- `partial` - some rows were inserted, some were skipped (for example duplicates)
- `skipped` - all rows were already present (no new entries inserted)
- `empty` - the file contained no data rows at all
- `error` - an unrecoverable parsing or validation error occurred

### 4) Warning behaviour

Warnings are returned in `warnings` as an array of strings.

Column warning patterns:

- Missing columns: `<Sheet> sheet: missing columns <col1>, <col2>. Rows missing required data may be skipped.`
- Unexpected columns: `<Sheet> sheet: ignoring unexpected columns <col1>, <col2>.`

Row skip warning pattern (invalid or missing date):

- `Daily sheet row <N>: skipped — invalid or missing date ("<value>").`
- `Dreams sheet row <N>: skipped — invalid or missing date ("<value>").`

Sheet presence warnings:

- `No 'Daily' sheet found; daily entries not imported.`
- `No 'Dreams' sheet found; dream entries not imported.`

### 5) DB write mapping defaults

Daily import writes:

- `date` -> `dailydiary_entries.entry_date`
- `title` -> `dailydiary_entries.title`
- `content` or `user_message` -> `dailydiary_entries.user_message`
- `tags` -> `dailydiary_entries.tags`

Dream import writes:

- `date` -> `dreamdiary_entries.entry_date`
- `title` -> `dreamdiary_entries.title`
- `plot` -> `dreamdiary_entries.plot`
- `cast` -> `dreamdiary_entries.cast`
- `location` -> `dreamdiary_entries.location`
- `period` -> `dreamdiary_entries.period`
- `emotion` -> `dreamdiary_entries.emotion`
- `symbols_and_imagery` -> `dreamdiary_entries.symbols_and_imagery`
- `insight` -> `dreamdiary_entries.insight`
- `action` -> `dreamdiary_entries.action`
- `other` -> `dreamdiary_entries.other`
- `tags` -> `dreamdiary_entries.tags`

Defaults for non-imported DB fields:

- Daily: non-imported fields such as `ai_response`, `daily_people_names`, and `daily_places` are not set by import and remain database defaults (typically `NULL` until updated later).
- Dreams: non-imported fields such as `summary`, `interpretation`, `image_prompt`, `image_url`, and `dream_people_names` are not set by import and remain database defaults (typically `NULL` until updated later).

`entry_number` assignment logic:

- For each imported row, `entry_number` is set to `MAX(entry_number) + 1` for the same `user_id` and `entry_date` in the target table.
- Duplicate-date rows for the same user are skipped before insert during import, so newly imported rows are normally inserted as the first entry for that date.

## Excel Export

### 1) GET /api/import/export

Downloads an `.xlsx` workbook for the authenticated user.

Auth required: JWT Bearer token (`Authorization: Bearer <token>`).

Query params (all optional):

- `from_date` (format: `YYYY-MM-DD`) - include entries on/after this date
- `to_date` (format: `YYYY-MM-DD`) - include entries on/before this date
- `include_daily` (`true`/`false`, default `true`) - include Daily entries
- `include_dreams` (`true`/`false`, default `true`) - include Dream entries

Validation rules:

- If `from_date` or `to_date` is invalid format -> `400`
- If `from_date > to_date` -> `400`
- If `include_daily=false` and `include_dreams=false` -> `400`

Default behaviour:

- No query params means full export of both Daily and Dreams data.

Response:

- `200` with attachment content type:
  - `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Download filename:
  - default: `aidiary_export_<timestamp>.xlsx`
  - filtered: `aidiary_export_filtered_<timestamp>.xlsx`

Workbook shape:

- Includes only selected sheet types (`Daily` and/or `Dreams`).
- Each included sheet always starts with standard import-template headers.
- Date filtering uses inclusive boundaries for both `from_date` and `to_date`.

Error response (400):

```json
{
  "status": "error",
  "errors": ["from_date cannot be after to_date."]
}
```
