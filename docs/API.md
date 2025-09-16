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

