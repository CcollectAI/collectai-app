"""
Tests for app/features/notification_router.py — push token management.

Covers:
  - POST /notifications/register — success (DB disabled mode), invalid token format
  - DELETE /notifications/register — success (DB disabled mode)
  - GET /notifications/tokens — empty list (DB disabled mode)
  - Pydantic validation (min_length, max_length)

Note: With DB_ENABLED=false and DEV_MODE=true (set in conftest.py), the
endpoints take their no-DB code paths and return mock responses.
Existing test_push.py covers the underlying send_push / send_push_to_user
functions, so this file focuses on the HTTP endpoints.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /notifications/register
# ---------------------------------------------------------------------------


class TestRegisterPushToken:
    """Tests for POST /notifications/register."""

    def test_register_valid_token(self):
        resp = client.post("/notifications/register", json={
            "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
            "platform": "ios",
            "device_name": "iPhone 15",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["registered"] is True
        assert "ExponentPushToken" in data["push_token"]

    def test_register_invalid_token_format(self):
        """Tokens must start with 'ExponentPushToken['."""
        resp = client.post("/notifications/register", json={
            "push_token": "some-random-token-value",
            "platform": "android",
        })
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower() or "Invalid" in resp.json()["detail"]

    def test_register_token_too_short(self):
        """push_token min_length is 10."""
        resp = client.post("/notifications/register", json={
            "push_token": "short",
            "platform": "ios",
        })
        assert resp.status_code == 422

    def test_register_missing_token(self):
        resp = client.post("/notifications/register", json={
            "platform": "ios",
        })
        assert resp.status_code == 422

    def test_register_default_platform(self):
        """Platform defaults to 'unknown' if not provided."""
        resp = client.post("/notifications/register", json={
            "push_token": "ExponentPushToken[yyyyyyyyyyyyyyyyyyyyyy]",
        })
        assert resp.status_code == 200
        assert resp.json()["registered"] is True


# ---------------------------------------------------------------------------
# DELETE /notifications/register
# ---------------------------------------------------------------------------


class TestUnregisterPushToken:
    """Tests for DELETE /notifications/register."""

    def test_unregister_valid_token(self):
        resp = client.request("DELETE", "/notifications/register", json={
            "push_token": "ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["unregistered"] is True

    def test_unregister_missing_token(self):
        resp = client.request("DELETE", "/notifications/register", json={})
        assert resp.status_code == 422

    def test_unregister_token_too_short(self):
        resp = client.request("DELETE", "/notifications/register", json={
            "push_token": "short",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /notifications/tokens
# ---------------------------------------------------------------------------


class TestListPushTokens:
    """Tests for GET /notifications/tokens."""

    def test_list_tokens_empty(self):
        """With DB disabled, returns empty list."""
        resp = client.get("/notifications/tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tokens"] == []

    def test_list_tokens_response_shape(self):
        resp = client.get("/notifications/tokens")
        data = resp.json()
        assert "tokens" in data
        assert isinstance(data["tokens"], list)
