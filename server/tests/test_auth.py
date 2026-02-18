"""Tests for app.auth — JWT validation and auth dependencies."""

from __future__ import annotations

import time
from unittest.mock import patch, MagicMock

import pytest

pyjwt = pytest.importorskip("jwt", reason="PyJWT not installed")

from fastapi import HTTPException
from starlette.requests import Request

from app.auth import get_current_user_id, get_optional_user_id

# Test constants
TEST_SECRET = "test-jwt-secret-key-minimum-32-bytes-long"
TEST_USER_ID = "user-abc-123"
TEST_ISSUER = "https://test-project.supabase.co/auth/v1"


def _make_token(
    sub: str = TEST_USER_ID,
    aud: str = "authenticated",
    iss: str | None = None,
    exp: int | None = None,
    secret: str = TEST_SECRET,
) -> str:
    """Create a JWT token for testing."""
    payload = {"sub": sub, "aud": aud}
    if iss is not None:
        payload["iss"] = iss
    if exp is not None:
        payload["exp"] = exp
    else:
        payload["exp"] = int(time.time()) + 3600
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _make_request(token: str | None = None) -> Request:
    """Create a mock Starlette Request with optional Bearer token."""
    scope = {"type": "http", "headers": []}
    if token:
        scope["headers"].append(
            (b"authorization", f"Bearer {token}".encode())
        )
    return Request(scope)


# ---------------------------------------------------------------------------
# Valid token tests
# ---------------------------------------------------------------------------

class TestValidToken:
    @pytest.mark.asyncio
    async def test_valid_token_returns_user_id(self):
        token = _make_token()
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            user_id = await get_current_user_id(request)
            assert user_id == TEST_USER_ID

    @pytest.mark.asyncio
    async def test_valid_token_with_issuer_check(self):
        token = _make_token(iss=TEST_ISSUER)
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", TEST_ISSUER), \
             patch("app.auth.DEV_MODE", False):
            user_id = await get_current_user_id(request)
            assert user_id == TEST_USER_ID


# ---------------------------------------------------------------------------
# Invalid token tests
# ---------------------------------------------------------------------------

class TestInvalidToken:
    @pytest.mark.asyncio
    async def test_no_auth_header_raises_401(self):
        request = _make_request(None)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_secret_raises_401(self):
        token = _make_token(secret="wrong-secret-that-does-not-match!")
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        token = _make_token(exp=int(time.time()) - 100)
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_issuer_raises_401(self):
        """Token with wrong issuer should be rejected when JWT_ISSUER is set."""
        token = _make_token(iss="https://evil.example.com")
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", TEST_ISSUER), \
             patch("app.auth.DEV_MODE", False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_issuer_rejected_when_required(self):
        """Token without iss claim should be rejected when JWT_ISSUER is configured."""
        token = _make_token(iss=None)
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", TEST_ISSUER), \
             patch("app.auth.DEV_MODE", False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_sub_claim_raises_401(self):
        """Token without sub claim should be rejected (require=["exp", "sub"])."""
        payload = {
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }
        token = pyjwt.encode(payload, TEST_SECRET, algorithm="HS256")
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_audience_raises_401(self):
        token = _make_token(aud="wrong-audience")
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_id(request)
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# DEV_MODE fallback
# ---------------------------------------------------------------------------

class TestDevMode:
    @pytest.mark.asyncio
    async def test_dev_mode_returns_dev_user_without_token(self):
        request = _make_request(None)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", True), \
             patch("app.auth.DEV_USER_ID", "dev-user-42"):
            user_id = await get_current_user_id(request)
            assert user_id == "dev-user-42"

    @pytest.mark.asyncio
    async def test_dev_mode_defaults_to_dev_user_local(self):
        request = _make_request(None)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", True), \
             patch("app.auth.DEV_USER_ID", ""):
            user_id = await get_current_user_id(request)
            assert user_id == "dev-user-local"

    @pytest.mark.asyncio
    async def test_dev_mode_still_validates_good_token(self):
        """Even in DEV_MODE, a valid token should be used (not dev user)."""
        token = _make_token()
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", True):
            user_id = await get_current_user_id(request)
            assert user_id == TEST_USER_ID


# ---------------------------------------------------------------------------
# get_optional_user_id
# ---------------------------------------------------------------------------

class TestOptionalUserId:
    @pytest.mark.asyncio
    async def test_returns_none_without_token(self):
        request = _make_request(None)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            user_id = await get_optional_user_id(request)
            assert user_id is None

    @pytest.mark.asyncio
    async def test_returns_user_id_with_valid_token(self):
        token = _make_token()
        request = _make_request(token)
        with patch("app.auth.JWT_SECRET", TEST_SECRET), \
             patch("app.auth.JWT_ISSUER", ""), \
             patch("app.auth.DEV_MODE", False):
            user_id = await get_optional_user_id(request)
            assert user_id == TEST_USER_ID
