"""
Unit tests for the Flask debug mode guard.

These tests verify that `app._is_debug_mode()` correctly derives
debug mode from the FLASK_DEBUG environment variable, defaulting
to False (safe) for production.
"""

import os
import sys
from unittest.mock import patch

# Ensure backend directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import app as app_module


class TestIsDebugMode:
    """Tests for the app._is_debug_mode() function directly.

    These tests provide real evidence by calling the actual production
    function with various environment variable configurations, rather
    than replicating the logic in a test helper.
    """

    def test_defaults_to_false(self):
        """When FLASK_DEBUG is not set, _is_debug_mode() must return False."""
        with patch.dict(os.environ, {}, clear=True):
            assert app_module._is_debug_mode() is False

    def test_env_1_is_true(self):
        """FLASK_DEBUG=1 enables debug mode."""
        with patch.dict(os.environ, {'FLASK_DEBUG': '1'}):
            assert app_module._is_debug_mode() is True

    def test_env_true_is_true(self):
        """FLASK_DEBUG=true enables debug mode."""
        with patch.dict(os.environ, {'FLASK_DEBUG': 'true'}):
            assert app_module._is_debug_mode() is True

    def test_env_yes_is_true(self):
        """FLASK_DEBUG=yes enables debug mode."""
        with patch.dict(os.environ, {'FLASK_DEBUG': 'yes'}):
            assert app_module._is_debug_mode() is True

    def test_env_0_is_false(self):
        """FLASK_DEBUG=0 disables debug mode."""
        with patch.dict(os.environ, {'FLASK_DEBUG': '0'}):
            assert app_module._is_debug_mode() is False

    def test_env_false_is_false(self):
        """FLASK_DEBUG=false disables debug mode."""
        with patch.dict(os.environ, {'FLASK_DEBUG': 'false'}):
            assert app_module._is_debug_mode() is False

    def test_env_no_is_false(self):
        """FLASK_DEBUG=no disables debug mode."""
        with patch.dict(os.environ, {'FLASK_DEBUG': 'no'}):
            assert app_module._is_debug_mode() is False

    def test_env_arbitrary_is_false(self):
        """FLASK_DEBUG=anything_else disables debug mode."""
        with patch.dict(os.environ, {'FLASK_DEBUG': 'anything_else'}):
            assert app_module._is_debug_mode() is False

    def test_env_empty_is_false(self):
        """FLASK_DEBUG='' (empty) disables debug mode (same as unset)."""
        with patch.dict(os.environ, {'FLASK_DEBUG': ''}):
            assert app_module._is_debug_mode() is False

    def test_env_case_insensitive(self):
        """FLASK_DEBUG is case-insensitive: TRUE, True, YES, Yes all work."""
        with patch.dict(os.environ, {'FLASK_DEBUG': 'TRUE'}):
            assert app_module._is_debug_mode() is True
        with patch.dict(os.environ, {'FLASK_DEBUG': 'True'}):
            assert app_module._is_debug_mode() is True
        with patch.dict(os.environ, {'FLASK_DEBUG': 'YES'}):
            assert app_module._is_debug_mode() is True
        with patch.dict(os.environ, {'FLASK_DEBUG': 'Yes'}):
            assert app_module._is_debug_mode() is True

    def test_env_unset_is_false(self):
        """When FLASK_DEBUG env var does not exist, _is_debug_mode() is False."""
        if 'FLASK_DEBUG' in os.environ:
            with patch.dict(os.environ, {}, clear=True):
                assert app_module._is_debug_mode() is False
        else:
            assert app_module._is_debug_mode() is False
