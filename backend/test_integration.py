"""
Integration tests for the Flask backend API.

Tests cover all endpoints including authentication, profiles,
score updates, and leaderboard functionality.
"""

import os
import sys
import json
import tempfile
import shutil
import pytest

# Ensure backend directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Import modules
import seed as seed_module

# Import the app module (as a module, not just the Flask instance)
import app as app_module
# The Flask application instance
flask_app = app_module.app

# Since `from seed import DB_PATH` in app.py creates a separate binding,
# we need to patch BOTH seed_module.DB_PATH and app_module.DB_PATH
# Save the original DB_PATH so we can restore it
_ORIGINAL_SEED_DB_PATH = seed_module.DB_PATH
_ORIGINAL_APP_DB_PATH = app_module.DB_PATH


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Create tables in a temp database before each test, remove DB after."""
    # Create a unique temp database for each test
    tmp_dir = tempfile.mkdtemp()
    tmp_db_path = os.path.join(tmp_dir, 'test.db')
    # Patch BOTH places where DB_PATH is referenced
    seed_module.DB_PATH = tmp_db_path
    app_module.DB_PATH = tmp_db_path
    seed_module.create_tables()
    yield
    # Clean up database after test
    shutil.rmtree(tmp_dir, ignore_errors=True)
    # Restore original DB_PATH
    seed_module.DB_PATH = _ORIGINAL_SEED_DB_PATH
    app_module.DB_PATH = _ORIGINAL_APP_DB_PATH


@pytest.fixture
def client():
    """Provide a Flask test client."""
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


def register_user(client, username="testuser", password="password123"):
    """Helper to register a user and return the response."""
    return client.post(
        '/api/register',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )


def login_user(client, username="testuser", password="password123"):
    """Helper to log in and return the response."""
    return client.post(
        '/api/login',
        data=json.dumps({'username': username, 'password': password}),
        content_type='application/json'
    )


def get_auth_header(response):
    """Extract auth token from login/register response."""
    data = json.loads(response.data)
    return {'Authorization': f'Bearer {data["token"]}'}


# ============================================================
# Tests
# ============================================================

class TestRegistration:
    """Tests for POST /api/register"""

    def test_register_success(self, client):
        """Successfully register a new user."""
        resp = register_user(client)
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert 'token' in data
        assert 'user_id' in data
        assert data['username'] == 'testuser'
        assert data['user_id'] > 0

    def test_register_duplicate_username(self, client):
        """Registering with an existing username returns 409."""
        register_user(client)
        resp = register_user(client)
        assert resp.status_code == 409
        data = json.loads(resp.data)
        assert 'error' in data

    def test_register_missing_username(self, client):
        """Register without username returns 400."""
        resp = client.post(
            '/api/register',
            data=json.dumps({'password': 'password123'}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert 'error' in data

    def test_register_missing_password(self, client):
        """Register without password returns 400."""
        resp = client.post(
            '/api/register',
            data=json.dumps({'username': 'testuser'}),
            content_type='application/json'
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert 'error' in data

    def test_register_empty_username(self, client):
        """Register with empty string username returns 400."""
        resp = register_user(client, username="")
        assert resp.status_code == 400

    def test_register_empty_password(self, client):
        """Register with empty string password returns 400."""
        resp = register_user(client, password="")
        assert resp.status_code == 400

    def test_register_non_json_body(self, client):
        """Register with non-JSON body returns 400."""
        resp = client.post(
            '/api/register',
            data='not json',
            content_type='text/plain'
        )
        assert resp.status_code == 400


class TestLogin:
    """Tests for POST /api/login"""

    def test_login_success(self, client):
        """Successfully log in with valid credentials."""
        register_user(client)
        resp = login_user(client)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'token' in data
        assert 'user_id' in data
        assert 'username' in data
        assert 'high_score' in data
        assert data['username'] == 'testuser'
        assert data['high_score'] == 0

    def test_login_invalid_username(self, client):
        """Login with wrong username returns 401."""
        register_user(client)
        resp = login_user(client, username="wronguser")
        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert 'error' in data

    def test_login_wrong_password(self, client):
        """Login with wrong password returns 401."""
        register_user(client)
        resp = login_user(client, password="wrongpassword")
        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert 'error' in data

    def test_login_missing_fields(self, client):
        """Login without fields returns 400."""
        resp = client.post(
            '/api/login',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert resp.status_code == 400

    def test_login_non_json_body(self, client):
        """Login with non-JSON body returns 400."""
        resp = client.post(
            '/api/login',
            data='not json',
            content_type='text/plain'
        )
        assert resp.status_code == 400


class TestProfile:
    """Tests for GET /api/profile"""

    def test_profile_authenticated(self, client):
        """Get profile with a valid token."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)
        resp = client.get('/api/profile', headers=headers)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'id' in data
        assert 'username' in data
        assert 'high_score' in data
        assert data['username'] == 'testuser'

    def test_profile_no_token(self, client):
        """Get profile without auth token returns 401."""
        resp = client.get('/api/profile')
        assert resp.status_code == 401

    def test_profile_invalid_token(self, client):
        """Get profile with an invalid token returns 401."""
        headers = {'Authorization': 'Bearer invalid_token_here'}
        resp = client.get('/api/profile', headers=headers)
        assert resp.status_code == 401

    def test_profile_expired_token(self, client):
        """Get profile with an expired token returns 401."""
        import jwt
        import time
        # Create a token that expired in the past
        expired_token = jwt.encode(
            {'user_id': 1, 'username': 'test', 'exp': int(time.time()) - 3600},
            'snake-game-secret-key-2024-abcdefgh',
            algorithm='HS256'
        )
        headers = {'Authorization': f'Bearer {expired_token}'}
        resp = client.get('/api/profile', headers=headers)
        assert resp.status_code == 401

    def test_profile_bearer_missing(self, client):
        """Get profile with malformed auth header returns 401."""
        headers = {'Authorization': 'Token something'}
        resp = client.get('/api/profile', headers=headers)
        assert resp.status_code == 401


class TestScore:
    """Tests for POST /api/score"""

    def test_score_update_higher(self, client):
        """Update score with a higher value succeeds."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json',
            headers=headers
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['high_score'] == 100
        assert data['updated'] is True

    def test_score_update_lower(self, client):
        """Update score with a lower value does not update high_score."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        # First set high score to 100
        client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json',
            headers=headers
        )

        # Now try a lower score
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 50}),
            content_type='application/json',
            headers=headers
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['high_score'] == 100  # Should remain 100
        assert data['updated'] is False

    def test_score_update_same(self, client):
        """Update score with the same value does not update."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        # First set high score to 100
        client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json',
            headers=headers
        )

        # Same score should not update
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json',
            headers=headers
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['high_score'] == 100
        assert data['updated'] is False

    def test_score_negative(self, client):
        """Update with a negative score returns 400."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        resp = client.post(
            '/api/score',
            data=json.dumps({'score': -10}),
            content_type='application/json',
            headers=headers
        )
        assert resp.status_code == 400

    def test_score_missing(self, client):
        """Update without a score field returns 400."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        resp = client.post(
            '/api/score',
            data=json.dumps({}),
            content_type='application/json',
            headers=headers
        )
        assert resp.status_code == 400

    def test_score_non_numeric(self, client):
        """Update with non-numeric score returns 400."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 'abc'}),
            content_type='application/json',
            headers=headers
        )
        assert resp.status_code == 400

    def test_score_no_auth(self, client):
        """Update score without auth returns 401."""
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 100}),
            content_type='application/json'
        )
        assert resp.status_code == 401

    def test_score_persists_across_sessions(self, client):
        """Verify high score persists across different logins for the same user."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        # Update score
        client.post(
            '/api/score',
            data=json.dumps({'score': 200}),
            content_type='application/json',
            headers=headers
        )

        # Log in again and check profile
        login_resp2 = login_user(client)
        data = json.loads(login_resp2.data)
        assert data['high_score'] == 200

    def test_score_zero_valid(self, client):
        """Score of 0 is valid (non-negative)."""
        register_user(client)
        login_resp = login_user(client)
        headers = get_auth_header(login_resp)

        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 0}),
            content_type='application/json',
            headers=headers
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['high_score'] == 0
        # Since high_score is already 0, posting 0 does NOT update
        assert data['updated'] is False


class TestLeaderboard:
    """Tests for GET /api/leaderboard"""

    def test_leaderboard_empty(self, client):
        """Leaderboard returns empty list when no users exist."""
        resp = client.get('/api/leaderboard')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data == []

    def test_leaderboard_with_users(self, client):
        """Leaderboard returns users ordered by high_score descending."""
        # Register multiple users and set different scores
        for i in range(5):
            username = f"user{i}"
            password = "pass123"
            register_user(client, username=username, password=password)
            login_resp = login_user(client, username=username, password=password)
            headers = get_auth_header(login_resp)
            score = (i + 1) * 100
            client.post(
                '/api/score',
                data=json.dumps({'score': score}),
                content_type='application/json',
                headers=headers
            )

        resp = client.get('/api/leaderboard')
        assert resp.status_code == 200
        data = json.loads(resp.data)

        # Should have 5 users, ordered by high_score DESC
        assert len(data) == 5
        for i in range(4):
            assert data[i]['high_score'] >= data[i + 1]['high_score']

    def test_leaderboard_top_10(self, client):
        """Leaderboard returns at most 10 entries."""
        # Register 15 users
        for i in range(15):
            username = f"player{i}"
            register_user(client, username=username, password="pass")
            login_resp = login_user(client, username=username, password="pass")
            headers = get_auth_header(login_resp)
            client.post(
                '/api/score',
                data=json.dumps({'score': i * 10}),
                content_type='application/json',
                headers=headers
            )

        resp = client.get('/api/leaderboard')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data) <= 10


class TestEndToEndFlow:
    """End-to-end integration scenarios."""

    def test_full_user_flow(self, client):
        """Complete flow: register → login → view profile → update score → verify."""
        # Register
        resp = register_user(client)
        assert resp.status_code == 201

        # Login
        resp = login_user(client)
        assert resp.status_code == 200
        token = resp.json['token']
        user_id = resp.json['user_id']

        # Profile
        resp = client.get(
            '/api/profile',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp.status_code == 200
        assert resp.json['id'] == user_id
        assert resp.json['high_score'] == 0

        # Update score
        resp = client.post(
            '/api/score',
            data=json.dumps({'score': 500}),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp.status_code == 200
        assert resp.json['high_score'] == 500

        # Verify profile reflects new score
        resp = client.get(
            '/api/profile',
            headers={'Authorization': f'Bearer {token}'}
        )
        assert resp.status_code == 200
        assert resp.json['high_score'] == 500

    def test_multiple_users_independent_scores(self, client):
        """Multiple users can have independent scores."""
        users = ['alice', 'bob', 'charlie']
        tokens = {}

        for username in users:
            register_user(client, username=username, password='pass')
            resp = login_user(client, username=username, password='pass')
            tokens[username] = resp.json['token']

        # Set different scores
        for username, score in [('alice', 300), ('bob', 500), ('charlie', 100)]:
            client.post(
                '/api/score',
                data=json.dumps({'score': score}),
                content_type='application/json',
                headers={'Authorization': f'Bearer {tokens[username]}'}
            )

        # Verify each user's score is independent
        for username, expected_score in [('alice', 300), ('bob', 500), ('charlie', 100)]:
            resp = client.get(
                '/api/profile',
                headers={'Authorization': f'Bearer {tokens[username]}'}
            )
            assert resp.status_code == 200
            assert resp.json['high_score'] == expected_score, \
                f"{username} should have score {expected_score}"
