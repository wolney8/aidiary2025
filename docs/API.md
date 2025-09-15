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