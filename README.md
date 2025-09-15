# AI Diary

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

# Frontend
   cd client && npm install
   
# Backend
   cd server
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   
Running the Application
Frontend (Angular):
bashcd client
npm start

# Runs on http://localhost:4200
Backend (Flask):
bashcd server
source venv/bin/activate
flask --app app.py --debug run -p 5001

# Runs on http://localhost:5001
Testing
bash# Backend tests
cd server && pytest

# Frontend tests
cd client && npm test
Architecture

Frontend: Angular 17 with standalone components, Material Design, SCSS
Backend: Flask with JWT authentication, SQLAlchemy, OpenAI integration
Database: SQLite with existing schema (see docs/ARCHITECTURE.md)