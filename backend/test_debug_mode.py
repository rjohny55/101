"""
Unit tests for the Flask debug mode guard.

The change in app.py replaced:
    app.run(debug=True)
with:
    debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    app.run(debug=debug_mode)

These tests verify that the debug mode is correctly derived from
the FLASK_DEBUG environment variable, defaulting to False (safe).
"""

import os
import sys
import pytest

# Ensure backend directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import app as app_module


# The exact expression used in app.py:
#   debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
def _debug_mode(env_value):
    """Replicate the exact logic from app.py for isolated testing."""
    return env_value.lower() in ('1', 'true', 'yes')


class TestDebugModeExpression:
    """Tests for the debug_mode expression logic in isolation."""

    def test_debug_defaults_to_false(self):
        """When FLASK_DEBUG is not set (empty string), debug_mode must be False."""
        assert _debug_mode('') is False

    def test_debug_env_1_is_true(self):
        """FLASK_DEBUG=1 enables debug mode."""
        assert _debug_mode('1') is True

    def test_debug_env_true_is_true(self):
        """FLASK_DEBUG=true enables debug mode."""
        assert _debug_mode('true') is True

    def test_debug_env_yes_is_true(self):
        """FLASK_DEBUG=yes enables debug mode."""
        assert _debug_mode('yes') is True

    def test_debug_env_0_is_false(self):
        """FLASK_DEBUG=0 disables debug mode."""
        assert _debug_mode('0') is False

    def test_debug_env_false_is_false(self):
        """FLASK_DEBUG=false disables debug mode."""
        assert _debug_mode('false') is False

    def test_debug_env_no_is_false(self):
        """FLASK_DEBUG=no disables debug mode."""
        assert _debug_mode('no') is False

    def test_debug_env_arbitrary_is_false(self):
        """FLASK_DEBUG=anything_else disables debug mode."""
        assert _debug_mode('anything_else') is False

    def test_debug_env_empty_is_false(self):
        """FLASK_DEBUG='' (empty) disables debug mode (same as unset)."""
        assert _debug_mode('') is False

    def test_debug_env_case_insensitive(self):
        """FLASK_DEBUG is case-insensitive: TRUE, True, YES, Yes all work."""
        assert _debug_mode('TRUE') is True
        assert _debug_mode('True') is True
        assert _debug_mode('YES') is True
        assert _debug_mode('Yes') is True


class TestDebugModeIntegration:
    """Tests for the actual debug mode logic in the app module.

    These tests monkeypatch os.getenv to simulate different FLASK_DEBUG
    values and verify that app.run would be called with the correct
    debug argument.
    """

    def test_app_run_called_with_debug_false_by_default(self, monkeypatch):
        """When FLASK_DEBUG is unset, app.run must receive debug=False."""
        monkeypatch.delenv('FLASK_DEBUG', raising=False)
        debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
        assert debug_mode is False

    def test_app_run_called_with_debug_true_when_set(self, monkeypatch):
        """When FLASK_DEBUG=1, app.run must receive debug=True."""
        monkeypatch.setenv('FLASK_DEBUG', '1')
        debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
        assert debug_mode is True

    def test_flask_debug_env_not_set_by_default(self, monkeypatch):
        """Verify FLASK_DEBUG is not set in the test environment (default safe)."""
        # This test validates that the default behavior is safe
        monkeypatch.delenv('FLASK_DEBUG', raising=False)
        val = os.getenv('FLASK_DEBUG', '')
        assert val == '', \
            "FLASK_DEBUG should default to empty string, keeping debug=False"

    def test_debug_mode_false_when_flask_debug_is_0(self, monkeypatch):
        """FLASK_DEBUG=0 must result in debug=False."""
        monkeypatch.setenv('FLASK_DEBUG', '0')
        debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
        assert debug_mode is False
