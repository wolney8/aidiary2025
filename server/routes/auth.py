# Authentication routes with JWT
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token
import bcrypt
import sqlite3
import re

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 12
MAX_USERNAME_LENGTH = 32
MAX_NAME_LENGTH = 12
USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
NAME_PATTERN = re.compile(r"^[A-Za-z]+(?:[ '-][A-Za-z]+)*$")


def _normalise_username(raw: object) -> str:
    return str(raw or '').strip()


def _normalise_optional_name(raw: object) -> str:
    return str(raw or '').strip()


def _validate_registration_payload(
    username: str,
    password: str,
    first_name: str,
    last_name: str,
) -> str | None:
    if not username or not password:
        return 'Username and password required'
    if len(username) < 3:
        return 'Username must be at least 3 characters'
    if len(username) > MAX_USERNAME_LENGTH:
        return 'Username must be 32 characters or fewer'
    if not USERNAME_PATTERN.fullmatch(username):
        return 'Username may only contain letters, numbers, dots, underscores, and hyphens'
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        return 'Password must be between 8 and 12 characters'
    if password.isdigit():
        return 'Password cannot be only numbers'
    if not any(char.isalpha() for char in password):
        return 'Password must include at least one letter'
    if not any(char.isdigit() for char in password):
        return 'Password must include at least one number'
    if len(first_name) > MAX_NAME_LENGTH or len(last_name) > MAX_NAME_LENGTH:
        return 'First and last name must be 12 characters or fewer'
    if first_name and not NAME_PATTERN.fullmatch(first_name):
        return 'First name contains unsupported characters'
    if last_name and not NAME_PATTERN.fullmatch(last_name):
        return 'Last name contains unsupported characters'
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
    first_name = _normalise_optional_name(data.get('first_name'))
    last_name = _normalise_optional_name(data.get('last_name'))

    validation_error = _validate_registration_payload(
        username, password, first_name, last_name
    )
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    # Hash password with bcrypt
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        existing_user = cursor.execute(
            'SELECT id FROM users WHERE username = ?',
            (username,),
        ).fetchone()
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 409

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
