# README.md

# OpenMynd

Angular + Flask application for daily and dream diary entries with AI analysis.

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- SQLite3
- OpenAI API key

### Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and configure
3. Install dependencies:

   ```bash
   # Frontend
   cd client && npm install

   # Backend
   cd server
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

### Running the Application

**Frontend (Angular):**

```bash
cd client
npm start
# Runs on http://localhost:4200
```

**Backend (Flask):**

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/run_resilient_dev_server.py
# Runs on http://localhost:5001
```

For a one-shot backend process without auto-restart, use:

```bash
cd server
source venv/bin/activate
python -m flask --app app.py --debug run -p 5001
```

### Production API Process

Do not run `python app.py` or the Flask debug server in production. Hosted API
deployments should use the root `Procfile`, which starts the existing WSGI app with
Gunicorn:

```bash
web: cd server && gunicorn "wsgi:app" --bind 0.0.0.0:$PORT --workers ${WEB_CONCURRENCY:-2} --threads ${WEB_THREADS:-4} --timeout ${WEB_TIMEOUT:-120}
```

Before promoting a deploy, run the production preflight and explicit Postgres
migrations described in `docs/adr/0005-production-saas-hosting-architecture.md`.
The runtime health checks are:

```bash
curl -f https://<api-host>/health
curl -f https://<api-host>/api/health/database
```

### Testing

```bash
# Backend tests
cd server && source venv/bin/activate && pytest

# Frontend tests
cd client && npm test
```

## Local Environment Note

- Use `server/venv` for local backend work in this repository.
- The checked-in `server/.venv` path may not be runnable on every machine and should not be treated as the default local environment.

## Architecture

- **Frontend:** Angular 17 with standalone components, Material Design, SCSS
- **Backend:** Flask with JWT authentication, SQLAlchemy, OpenAI integration
- **Database:** SQLite with existing schema (see docs/ARCHITECTURE.md)
