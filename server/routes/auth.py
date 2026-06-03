# Authentication routes with JWT
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token
import bcrypt
import sqlite3

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 10
MAX_USERNAME_LENGTH = 64


def _normalise_username(raw: object) -> str:
    return str(raw or '').strip()


def _validate_registration_payload(username: str, password: str) -> str | None:
    if not username or not password:
        return 'Username and password required'
    if len(username) < 3:
        return 'Username must be at least 3 characters'
    if len(username) > MAX_USERNAME_LENGTH:
        return 'Username must be 64 characters or fewer'
    if len(password) < MIN_PASSWORD_LENGTH:
        return 'Password must be at least 10 characters'
    return None

def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Auth get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user with bcrypt password hashing."""
    data = request.get_json()
    username = _normalise_username(data.get('username'))
    password = str(data.get('password') or '')
    first_name = str(data.get('first_name', '')).strip()
    last_name = str(data.get('last_name', '')).strip()

    validation_error = _validate_registration_payload(username, password)
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    # Hash password with bcrypt
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash.decode('utf-8'), first_name, last_name))
        
        conn.commit()
        user_id = cursor.lastrowid
        
        # Create JWT token
        access_token = create_access_token(identity=str(user_id))
        
        return jsonify({
            'token': access_token,
            'user': {
                'id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            }
        }), 201
        
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409
    finally:
        conn.close()

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token."""
    data = request.get_json()
    username = _normalise_username(data.get('username'))
    password = str(data.get('password') or '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    user = cursor.execute(
        'SELECT id, username, password, first_name FROM users WHERE username = ?',
        (username,)
    ).fetchone()
    
    conn.close()
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check password (handle both bcrypt and legacy plaintext)
    stored_password = user['password']
    if stored_password.startswith('$2b$'):  # bcrypt hash
        if not bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
            return jsonify({'error': 'Invalid credentials'}), 401
    else:  # Legacy plaintext (should be migrated)
        if password != stored_password:
            return jsonify({'error': 'Invalid credentials'}), 401
        # Migrate legacy plaintext password to bcrypt on successful login.
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        conn = get_db()
        conn.execute(
            'UPDATE users SET password = ? WHERE id = ?',
            (password_hash.decode('utf-8'), user['id']),
        )
        conn.commit()
        conn.close()
    
    # Create JWT token
    access_token = create_access_token(identity=str(user['id']))
    
    return jsonify({
        'token': access_token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'first_name': user['first_name']
        }
    }), 200
