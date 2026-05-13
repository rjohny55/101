"""Tests for the Flask backend API (app.py)."""

import json
import os
import sys
import tempfile
import pytest

# Adjust path so we can import from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Point DB to a temp file BEFORE importing app
import seed
TEST_DB_FD, TEST_DB_PATH = tempfile.mkstemp(suffix='.db')
seed.DB_PATH = TEST_DB_PATH

# Re-create tables in the test DB
seed.create_tables()

from backend.app import app


@pytest.fixture
def client():
    """Provide a Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_db():
    """Reset the database before each test by clearing the users table."""
    import sqlite3
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.execute('DELETE FROM users')
    conn.commit()
    conn.close()
    yield


def _register(client, username='testuser', password='testpass123'):
    """Helper: register a user and return the response."""
    return client.post(
        '/api/register',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )


def _login(client, username='testuser', password='testpass123'):
    """Helper: login a user and return the response."""
    return client.post(
        '/api/login',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )


def _auth_header(token):
    """Helper: build an Authorization header dict."""
    return {'Authorization': f'Bearer {token}'}


# ---------------------------------------------------------------------------
# POST /api/register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_successful_registration(self, client):
        resp = _register(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'token' in data
        assert data['username'] == 'testuser'
        assert 'user_id' in data

    def test_duplicate_username(self, client):
        _register(client)
        resp = _register(client)
        assert resp.status_code == 409
        assert resp.get_json()['error'] == 'Username already exists'

    def test_missing_username(self, client):
        resp = client.post(
            '/api/register',
            data=json.dumps({'password': 'testpass123'}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_missing_password(self, client):
        resp = client.post(
            '/api/register',
            data=json.dumps({'username': 'testuser'}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_empty_body(self, client):
        resp = client.post(
            '/api/register',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_non_json_body(self, client):
        resp = client.post(
            '/api/register',
            data='not-json',
            content_type='text/plain'
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_whitespace_username(self, client):
        resp = client.post(
            '/api/register',
            data=json.dumps({'username': '   ', 'password': 'testpass123'}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()


# ---------------------------------------------------------------------------
# POST /api/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_successful_login(self, client):
        _register(client)
        resp = _login(client)
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'token' in data
        assert data['username'] == 'testuser'
        assert 'user_id' in data
        assert 'high_score' in data

    def test_invalid_password(self, client):
        _register(client)
        resp = client.post(
            '/api/login',
            data=json.dumps({'username': 'testuser', 'password': 'wrongpass'}),
            content_type='application/json'
        )
        assert resp.status_code == 401
        assert 'error' in resp.get_json()

    def test_nonexistent_user(self, client):
        resp = _login(client)
        assert resp.status_code == 401
        assert 'error' in resp.get_json()

    def test_missing_fields(self, client):
        resp = client.post(
            '/api/login',
            data=json.dumps({'username': 'testuser'}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_non_json_body(self, client):
        resp = client.post(
            '/api/login',
            data='not-json',
            content_type='text/plain'
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()


# ---------------------------------------------------------------------------
# GET /api/profile
# ---------------------------------------------------------------------------

class TestProfile:
    def test_get_profile(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        resp = client.get('/api/profile', headers=_auth_header(token))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['username'] == 'testuser'
        assert 'high_score' in data
        assert 'id' in data

    def test_missing_token(self, client):
        resp = client.get('/api/profile')
        assert resp.status_code == 401
        assert 'error' in resp.get_json()

    def test_invalid_token(self, client):
        resp = client.get('/api/profile', headers=_auth_header('invalidtoken'))
        assert resp.status_code == 401
        assert 'error' in resp.get_json()

    def test_expired_token(self, client):
        import jwt
        import backend.app as backend_app
        expired_token = jwt.encode(
            {'user_id': 999, 'username': 'ghost', 'exp': 0},
            backend_app.SECRET_KEY,
            algorithm=backend_app.ALGORITHM
        )
        resp = client.get('/api/profile', headers=_auth_header(expired_token))
        assert resp.status_code == 401
        assert 'error' in resp.get_json()

    def test_nonexistent_user_in_token(self, client):
        import jwt
        import backend.app as backend_app
        from datetime import datetime, timedelta
        ghost_token = jwt.encode(
            {
                'user_id': 99999,
                'username': 'ghost',
                'exp': datetime.utcnow() + timedelta(hours=1)
            },
            backend_app.SECRET_KEY,
            algorithm=backend_app.ALGORITHM
        )
        resp = client.get('/api/profile', headers=_auth_header(ghost_token))
        assert resp.status_code == 404
        assert 'error' in resp.get_json()


# ---------------------------------------------------------------------------
# POST /api/score
# ---------------------------------------------------------------------------

class TestScore:
    def test_update_score_new_high(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['high_score'] == 100
        assert data['updated'] is True

    def test_update_score_lower(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        # Set high score to 200
        client.post(
            '/api/score',
            data=json.dumps({'score': 200}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        # Try setting lower score
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 50}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['high_score'] == 200
        assert data['updated'] is False

    def test_update_score_same_value(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        client.post(
            '/api/score',
            data=json.dumps({'score': 150}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 150}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['high_score'] == 150
        assert data['updated'] is False

    def test_update_score_no_auth(self, client):
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json'
        )
        assert resp.status_code == 401

    def test_update_score_invalid_score(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': -1}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        assert resp.status_code == 400

    def test_update_score_missing_score(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        resp = client.post(
            '/api/score',
            data=json.dumps({}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        assert resp.status_code == 400

    def test_update_score_non_numeric(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 'abc'}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        assert resp.status_code == 400

    def test_update_score_nonexistent_user(self, client):
        import jwt
        import backend.app as backend_app
        from datetime import datetime, timedelta
        ghost_token = jwt.encode(
            {
                'user_id': 99999,
                'username': 'ghost',
                'exp': datetime.utcnow() + timedelta(hours=1)
            },
            backend_app.SECRET_KEY,
            algorithm=backend_app.ALGORITHM
        )
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json',
            headers=_auth_header(ghost_token)
        )
        assert resp.status_code == 404

    def test_update_score_float_input(self, client):
        reg_resp = _register(client)
        token = reg_resp.get_json()['token']
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 99.7}),
            content_type='application/json',
            headers=_auth_header(token)
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['high_score'] == 99


# ---------------------------------------------------------------------------
# GET /api/leaderboard
# ---------------------------------------------------------------------------

class TestLeaderboard:
    def test_empty_leaderboard(self, client):
        resp = client.get('/api/leaderboard')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_leaderboard_ordering(self, client):
        # Register multiple users and set different scores
        users_scores = [('alice', 300), ('bob', 500), ('carol', 200)]
        for username, score in users_scores:
            reg_resp = _register(client, username=username, password='pass')
            token = reg_resp.get_json()['token']
            client.post(
                '/api/score',
                data=json.dumps({'score': score}),
                content_type='application/json',
                headers=_auth_header(token)
            )

        resp = client.get('/api/leaderboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 3
        # Should be sorted descending by high_score
        assert data[0]['username'] == 'bob'
        assert data[0]['high_score'] == 500
        assert data[1]['username'] == 'alice'
        assert data[1]['high_score'] == 300
        assert data[2]['username'] == 'carol'
        assert data[2]['high_score'] == 200

    def test_leaderboard_limit_10(self, client):
        # Register 15 users
        for i in range(15):
            _register(client, username=f'user{i}', password='pass')

        resp = client.get('/api/leaderboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) <= 10


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session', autouse=True)
def cleanup():
    yield
    os.close(TEST_DB_FD)
    os.unlink(TEST_DB_PATH)
