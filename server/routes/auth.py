# Authentication routes with JWT
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
import bcrypt
import sqlite3
import os

auth_bp = Blueprint('auth', __name__)

def get_db():
    """Get database connection."""
    db_path = os.getenv('DB_PATH', './app.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user with bcrypt password hashing."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
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
    username = data.get('username')
    password = data.get('password')
    
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
