# CHANGELOG.md
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

# docs/API.md
# API Documentation

Base URL: `http://localhost:5001/api`

## Authentication

### POST /api/register
Create new user account.

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
  "id": 1,
  "username": "johndoe",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Database Mapping:**
- `username` → `users.username`
- `password` → `users.password` (bcrypt hashed)
- `first_name` → `users.first_name`
- `last_name` → `users.last_name`

### POST /api/login
Authenticate user and receive JWT token.

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
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "johndoe",
    "first_name": "John"
  }
}
```

## Profile

### GET /api/profile
Get current user profile (requires JWT).

**Headers:** `Authorization: Bearer <token>`

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
Update user profile.

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
List all daily entries for authenticated user.

**Response (200):**
```json
[
  {
    "id": 1,
    "entry_date": "2024-01-15",
    "entry_number": 1,
    "user_message": "Today was productive...",
    "ai_response": "Well done on being productive...",
    "daily_people_names": "Sarah,Tom",
    "tags": "work,productivity"
  }
]
```

### POST /api/daily
Create new daily entry.

**Request:**
```json
{
  "entry_date": "2024-01-15",
  "user_message": "Today was productive..."
}
```

**Database Mapping:**
- `entry_date` → `dailydiary_entries.entry_date`
- `user_message` → `dailydiary_entries.user_message`
- Auto-generates `entry_number` for the day

### PUT /api/daily/:id
Update daily entry with AI analysis results.

**Request:**
```json
{
  "ai_response": "Well done on being productive...",
  "daily_people_names": "Sarah,Tom",
  "tags": "work,productivity"
}
```

### DELETE /api/daily/:id
Delete a daily entry.

**Response:** 204 No Content

## Dream Entries

### GET /api/dreams
List all dream entries.

### POST /api/dreams
Create new dream entry.

**Request:**
```json
{
  "entry_date": "2024-01-15",
  "title": "Flying dream",
  "cast": "Me, unknown figure",
  "location": "Mountains",
  "period": "Night",
  "emotion": "Excited",
  "plot": "I was flying over mountains..."
}
```

### PUT /api/dreams/:id
Update dream entry with AI analysis.

**Request:**
```json
{
  "summary": "A dream about freedom...",
  "interpretation": "This suggests...",
  "image_prompt": "Person flying over mountains at night",
  "dream_people_names": "Unknown figure",
  "tags": "flying,freedom,mountains"
}
```

### DELETE /api/dreams/:id
Delete a dream entry.

**Response:** 204 No Content

## AI Analysis

### POST /api/analyse
Analyse text and return structured insights.

**Request:**
```json
{
  "mode": "daily",
  "text": "Today I met Sarah at work..."
}
```

**Response for mode="daily":**
```json
{
  "ai_response": "It sounds like you had a productive meeting...",
  "tags": "work,meeting,collaboration",
  "daily_people_names": "Sarah"
}
```

**Response for mode="dream":**
```json
{
  "summary": "A dream about professional relationships...",
  "interpretation": "Meeting Sarah in your dream may represent...",
  "image_prompt": "Two people in professional setting having a meeting",
  "tags": "work,relationships,communication",
  "dream_people_names": "Sarah"
}
```
