"""Tests for app.config.validate_config() — startup environment validation.

Tests the DEV_MODE production guard (R15-1) and required-env-var checks (R15-2).
Since validate_config() reads module-level globals from app.config, we must
reload the module after patching environment variables so the globals pick up
the new values.
"""

from __future__ import annotations

import importlib
import os
import socket
from unittest.mock import patch

import pytest


def _reload_config_and_validate(env_overrides: dict) -> None:
    """Reload app.config with the given env vars and call validate_config().

    This is necessary because app.config reads env vars at module import time
    into module-level constants (DEV_MODE, DB_ENABLED, JWT_SECRET, etc.).
    """
    combined = {**os.environ, **env_overrides}
    with patch.dict(os.environ, combined, clear=True):
        import app.config as cfg
        importlib.reload(cfg)
        cfg.validate_config()


def _reload_config(env_overrides: dict):
    """Reload app.config with the given env vars and return the module."""
    combined = {**os.environ, **env_overrides}
    with patch.dict(os.environ, combined, clear=True):
        import app.config as cfg
        importlib.reload(cfg)
        return cfg


# ---------------------------------------------------------------------------
# DEV_MODE production guard (R15-1)
# ---------------------------------------------------------------------------

class TestDevModeGuard:
    """validate_config() should reject DEV_MODE=true on non-local hostnames."""

    def test_rejects_non_local_hostname(self):
        """DEV_MODE=true on a production-like hostname raises SystemExit."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
            "FORCE_DEV_MODE": "",
        }
        with patch("socket.gethostname", return_value="ip-172-31-10-42.eu-central-1.compute.internal"):
            with pytest.raises(SystemExit):
                _reload_config_and_validate(env)

    def test_rejects_ec2_hostname(self):
        """EC2-style hostname should be rejected."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
            "FORCE_DEV_MODE": "",
        }
        with patch("socket.gethostname", return_value="ec2-3-75-182-41"):
            with pytest.raises(SystemExit):
                _reload_config_and_validate(env)

    def test_allows_localhost_prefix(self):
        """Hostname starting with 'localhost' should be allowed."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
            "FORCE_DEV_MODE": "",
        }
        with patch("socket.gethostname", return_value="localhost"):
            _reload_config_and_validate(env)  # should not raise

    def test_allows_127_prefix(self):
        """Hostname starting with '127.' should be allowed."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
            "FORCE_DEV_MODE": "",
        }
        with patch("socket.gethostname", return_value="127.0.0.1"):
            _reload_config_and_validate(env)  # should not raise

    def test_rejects_macbook_prefix(self):
        """Hostname starting with 'macbook' is no longer whitelisted."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
        }
        with patch("socket.gethostname", return_value="MacBook-Pro"):
            with pytest.raises(SystemExit):
                _reload_config_and_validate(env)

    def test_rejects_mbp_prefix(self):
        """Hostname starting with 'mbp' is no longer whitelisted."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
        }
        with patch("socket.gethostname", return_value="MBP-Merle"):
            with pytest.raises(SystemExit):
                _reload_config_and_validate(env)

    def test_allows_dot_home_suffix(self):
        """Hostname ending with '.home' (macOS home network) should be allowed."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
        }
        with patch("socket.gethostname", return_value="device-47.home"):
            _reload_config_and_validate(env)  # should not raise

    def test_allows_dot_local_suffix(self):
        """Hostname ending with '.local' should be allowed."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
            "FORCE_DEV_MODE": "",
        }
        with patch("socket.gethostname", return_value="my-dev-machine.local"):
            _reload_config_and_validate(env)  # should not raise


# ---------------------------------------------------------------------------
# FORCE_DEV_MODE removed — verify it no longer bypasses
# ---------------------------------------------------------------------------

class TestForceDevModeRemoved:
    """FORCE_DEV_MODE was removed for security. DEV_MODE on non-local hosts is always rejected."""

    def test_force_dev_mode_no_longer_bypasses(self):
        """FORCE_DEV_MODE=true should NOT prevent rejection on production hosts."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
            "FORCE_DEV_MODE": "true",
        }
        with patch("socket.gethostname", return_value="production-server-42"):
            with pytest.raises(SystemExit):
                _reload_config_and_validate(env)

    def test_force_dev_mode_env_ignored(self):
        """FORCE_DEV_MODE=1 env var is now ignored."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "false",
            "FORCE_DEV_MODE": "1",
        }
        with patch("socket.gethostname", return_value="ec2-production"):
            with pytest.raises(SystemExit):
                _reload_config_and_validate(env)


# ---------------------------------------------------------------------------
# Required env vars in production (R15-2)
# ---------------------------------------------------------------------------

class TestRequiredEnvVars:
    """When DEV_MODE=false and DB_ENABLED=true, JWT_SECRET and DB_DSN are required."""

    def test_missing_jwt_secret_raises_exit(self):
        env = {
            "DEV_MODE": "false",
            "DB_ENABLED": "true",
            "SUPABASE_JWT_SECRET": "",
            "DB_DSN": "postgresql://user:pass@host/db",
            "SUPABASE_URL": "https://test.supabase.co",
            "OPS_API_KEY": "ops-key-123",
        }
        with pytest.raises(SystemExit):
            _reload_config_and_validate(env)

    def test_missing_db_dsn_raises_exit(self):
        env = {
            "DEV_MODE": "false",
            "DB_ENABLED": "true",
            "SUPABASE_JWT_SECRET": "super-secret-key",
            "DB_DSN": "",
            "SUPABASE_URL": "https://test.supabase.co",
            "OPS_API_KEY": "ops-key-123",
        }
        with pytest.raises(SystemExit):
            _reload_config_and_validate(env)

    def test_missing_both_raises_exit(self):
        env = {
            "DEV_MODE": "false",
            "DB_ENABLED": "true",
            "SUPABASE_JWT_SECRET": "",
            "DB_DSN": "",
            "SUPABASE_URL": "https://test.supabase.co",
            "OPS_API_KEY": "ops-key-123",
        }
        with pytest.raises(SystemExit):
            _reload_config_and_validate(env)

    def test_all_present_does_not_raise(self):
        env = {
            "DEV_MODE": "false",
            "DB_ENABLED": "true",
            "SUPABASE_JWT_SECRET": "super-secret-key-that-is-long",
            "DB_DSN": "postgresql://user:pass@host/db",
            "SUPABASE_URL": "https://test.supabase.co",
            "OPS_API_KEY": "ops-key-123",
            "STRIPE_WEBHOOK_SECRET": "whsec_test_123",
        }
        _reload_config_and_validate(env)  # should not raise

    def test_db_disabled_does_not_require_db_dsn(self):
        """When DB_ENABLED=false, DB_DSN is not required but JWT/SUPABASE_URL/OPS still are."""
        env = {
            "DEV_MODE": "false",
            "DB_ENABLED": "false",
            "SUPABASE_JWT_SECRET": "secret-key",
            "DB_DSN": "",
            "SUPABASE_URL": "https://test.supabase.co",
            "OPS_API_KEY": "ops-key-123",
            "STRIPE_WEBHOOK_SECRET": "whsec_test_123",
        }
        _reload_config_and_validate(env)  # should not raise

    def test_missing_supabase_url_raises_exit(self):
        """SUPABASE_URL is required in production."""
        env = {
            "DEV_MODE": "false",
            "DB_ENABLED": "true",
            "SUPABASE_JWT_SECRET": "secret-key",
            "DB_DSN": "postgresql://user:pass@host/db",
            "SUPABASE_URL": "",
            "OPS_API_KEY": "ops-key-123",
        }
        with pytest.raises(SystemExit):
            _reload_config_and_validate(env)

    def test_missing_ops_key_raises_exit(self):
        """OPS_API_KEY is required in production."""
        env = {
            "DEV_MODE": "false",
            "DB_ENABLED": "true",
            "SUPABASE_JWT_SECRET": "secret-key",
            "DB_DSN": "postgresql://user:pass@host/db",
            "SUPABASE_URL": "https://test.supabase.co",
            "OPS_API_KEY": "",
        }
        with pytest.raises(SystemExit):
            _reload_config_and_validate(env)

    def test_dev_mode_true_does_not_check_required_keys(self):
        """DEV_MODE=true with DB_ENABLED=true should skip the production check."""
        env = {
            "DEV_MODE": "true",
            "DB_ENABLED": "true",
            "SUPABASE_JWT_SECRET": "",
            "DB_DSN": "",
        }
        # Even with empty keys, DEV_MODE should skip the production check
        # (must run on a .local hostname to pass the hostname guard)
        with patch("socket.gethostname", return_value="dev-machine.local"):
            _reload_config_and_validate(env)  # should not raise


# ---------------------------------------------------------------------------
# Module-level config constants
# ---------------------------------------------------------------------------

class TestConfigConstants:
    """Verify that module-level constants are read correctly from env."""

    def test_dev_mode_true(self):
        cfg = _reload_config({"DEV_MODE": "true"})
        assert cfg.DEV_MODE is True

    def test_dev_mode_false(self):
        cfg = _reload_config({"DEV_MODE": "false"})
        assert cfg.DEV_MODE is False

    def test_dev_mode_1(self):
        cfg = _reload_config({"DEV_MODE": "1"})
        assert cfg.DEV_MODE is True

    def test_db_enabled_default_false(self):
        cfg = _reload_config({})
        assert cfg.DB_ENABLED is False

    def test_rate_limit_defaults_to_60(self):
        cfg = _reload_config({})
        assert cfg.RATE_LIMIT_RPM == 60

    def test_usd_to_eur_default(self):
        cfg = _reload_config({})
        assert cfg.USD_TO_EUR == 0.92

    def test_custom_usd_to_eur(self):
        cfg = _reload_config({"USD_TO_EUR": "0.88"})
        assert cfg.USD_TO_EUR == 0.88
