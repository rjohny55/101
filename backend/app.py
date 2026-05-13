import sqlite3
import os
from datetime import datetime, timedelta

import jwt
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seed import create_tables, DB_PATH

app = Flask(__name__)
CORS(app)

SECRET_KEY = 'snake-game-secret-key-2024-abcdefgh'
ALGORITHM = 'HS256'
TOKEN_EXPIRATION_HOURS = 24


def get_db():
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def token_required(f):
    """Decorator that validates the JWT token from the Authorization header."""
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401

        token = auth_header.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get('user_id')
            if user_id is None:
                return jsonify({'error': 'Invalid token payload'}), 401
            kwargs['user_id'] = user_id
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user with a username and password."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    password_hash = generate_password_hash(password)

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username already exists'}), 409
    finally:
        conn.close()

    token = jwt.encode(
        {
            'user_id': user_id,
            'username': username,
            'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return jsonify({'token': token, 'user_id': user_id, 'username': username}), 201


@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate a user and return a JWT token."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, password_hash, high_score FROM users WHERE username = ?',
        (username,)
    )
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401

    token = jwt.encode(
        {
            'user_id': user['id'],
            'username': user['username'],
            'exp': datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS)
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return jsonify({
        'token': token,
        'user_id': user['id'],
        'username': user['username'],
        'high_score': user['high_score']
    }), 200


@app.route('/api/profile', methods=['GET'])
@token_required
def profile(user_id):
    """Return the authenticated user's profile with high_score."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, high_score FROM users WHERE id = ?',
        (user_id,)
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'id': user['id'],
        'username': user['username'],
        'high_score': user['high_score']
    }), 200


@app.route('/api/score', methods=['POST'])
@token_required
def update_score(user_id):
    """Update the user's high_score if the new score is higher."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    new_score = data.get('score')
    if new_score is None or not isinstance(new_score, (int, float)) or new_score < 0:
        return jsonify({'error': 'A valid non-negative score is required'}), 400

    new_score = int(new_score)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT high_score FROM users WHERE id = ?',
        (user_id,)
    )
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    if new_score > user['high_score']:
        cursor.execute(
            'UPDATE users SET high_score = ? WHERE id = ?',
            (new_score, user_id)
        )
        conn.commit()
        updated = True
    else:
        updated = False

    cursor.execute(
        'SELECT high_score FROM users WHERE id = ?',
        (user_id,)
    )
    current_high_score = cursor.fetchone()['high_score']
    conn.close()

    return jsonify({
        'high_score': current_high_score,
        'updated': updated
    }), 200


@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    """Return the top 10 users by high_score."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, username, high_score FROM users ORDER BY high_score DESC LIMIT 10'
    )
    rows = cursor.fetchall()
    conn.close()

    leaderboard_list = [
        {'id': row['id'], 'username': row['username'], 'high_score': row['high_score']}
        for row in rows
    ]

    return jsonify(leaderboard_list), 200


def _is_debug_mode():
    """Determine if Flask debug mode should be enabled based on FLASK_DEBUG env var.

    Returns True only if FLASK_DEBUG is set to '1', 'true', or 'yes' (case-insensitive).
    Defaults to False for production safety.
    """
    return os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')


if __name__ == '__main__':
    create_tables()
    app.run(debug=_is_debug_mode())
