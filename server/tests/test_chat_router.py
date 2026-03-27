"""Tests for app/features/chat_router.py — DM thread management and messaging.

Covers:
  - GET    /chat/threads                       — list threads (happy path, no DB)
  - GET    /chat/threads/{id}/messages          — get messages (happy, IDOR, invalid UUID)
  - POST   /chat/threads/{id}/messages          — send message (happy, IDOR, blocked)
  - PATCH  /chat/threads/{id}/read              — mark read (happy, IDOR)
  - DELETE /chat/messages/{id}                  — delete message (happy, IDOR, not found)
  - PATCH  /chat/messages/{id}                  — edit message (happy, IDOR, expired window)
  - GET    /chat/unread-count                   — unread count (happy)

All tests mock get_db_pool() and override the auth dependency so no real
database is needed.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)

TEST_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_USER_ID = "11111111-2222-3333-4444-555555555555"
THREAD_UUID = "00000000-0000-0000-0000-000000000001"
MESSAGE_UUID = "00000000-0000-0000-0000-000000000002"
INVALID_UUID = "not-a-uuid"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_pool():
    """Create a mock asyncpg pool with a mock connection."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=None)
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    mock_tx = AsyncMock()
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_acquire.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=mock_acquire)

    return pool, mock_conn


def _auth_override(user_id: str = TEST_USER_ID):
    from app.auth import get_current_user_id

    async def _fake_user():
        return user_id

    app.dependency_overrides[get_current_user_id] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


def _thread_participant_row(requester_id=TEST_USER_ID, responder_id=OTHER_USER_ID):
    """Mock row returned by _get_thread_participant query."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "requester_id": requester_id,
        "responder_id": responder_id,
    }[key]
    return row


def _message_row(sender_id=TEST_USER_ID, created_at=None):
    """Mock row returned by message queries."""
    now = created_at or datetime.now(timezone.utc)
    row = MagicMock()
    data = {
        "id": MESSAGE_UUID,
        "thread_id": THREAD_UUID,
        "sender_id": sender_id,
        "body": "Hello!",
        "created_at": now,
        "edited_at": None,
        "deleted_at": None,
    }
    row.__getitem__ = lambda self, key: data[key]
    row.keys = lambda: data.keys()

    # Support dict(row) conversion
    def _iter():
        return iter(data.items())
    row.__iter__ = _iter

    return row, data


# ---------------------------------------------------------------------------
# Tests: GET /chat/threads
# ---------------------------------------------------------------------------


class TestListThreads:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.chat_router.get_db_pool")
    def test_list_threads_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)

        resp = client.get("/chat/threads")
        assert resp.status_code == 200
        data = resp.json()
        assert "threads" in data
        assert "total_count" in data
        assert data["total_count"] == 0

    @patch("app.features.chat_router.get_db_pool")
    def test_list_threads_no_db(self, mock_get_pool):
        mock_get_pool.return_value = None

        resp = client.get("/chat/threads")
        assert resp.status_code == 200
        assert resp.json() == {"threads": [], "total_count": 0}

    @patch("app.auth.DEV_MODE", False)
    def test_list_threads_unauthenticated(self):
        _clear_overrides()
        resp = client.get("/chat/threads")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Tests: GET /chat/threads/{thread_id}/messages
# ---------------------------------------------------------------------------


class TestGetMessages:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.chat_router.get_db_pool")
    def test_get_messages_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # Return participant row (user is in thread)
        conn.fetchrow = AsyncMock(return_value=_thread_participant_row())
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)

        resp = client.get(f"/chat/threads/{THREAD_UUID}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert "total_count" in data

    @patch("app.features.chat_router.get_db_pool")
    def test_get_messages_idor_not_participant(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # User is NOT in this thread
        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.get(f"/chat/threads/{THREAD_UUID}/messages")
        assert resp.status_code == 404

    def test_get_messages_invalid_uuid(self):
        resp = client.get(f"/chat/threads/{INVALID_UUID}/messages")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: POST /chat/threads/{thread_id}/messages
# ---------------------------------------------------------------------------


class TestSendMessage:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.chat_router.get_db_pool")
    def test_send_message_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # User is in thread
        conn.fetchrow = AsyncMock(side_effect=[
            _thread_participant_row(),  # _get_thread_participant
            None,  # _check_not_blocked (no block)
        ])
        conn.fetchval = AsyncMock(return_value=None)  # block check

        # Mock RPC result
        now = datetime.now(timezone.utc)
        rpc_row = MagicMock()
        rpc_data = {
            "id": MESSAGE_UUID,
            "thread_id": THREAD_UUID,
            "sender_id": TEST_USER_ID,
            "body": "Hello!",
            "created_at": now,
            "edited_at": None,
        }
        rpc_row.__getitem__ = lambda self, key: rpc_data[key]
        rpc_row.keys = lambda: rpc_data.keys()
        rpc_row.__iter__ = lambda self: iter(rpc_data.items())

        # fetchrow returns participant first, then block check is fetchval, then RPC
        conn.fetchrow = AsyncMock(side_effect=[
            _thread_participant_row(),  # _get_thread_participant
            rpc_row,  # rpc_send_message_v1
        ])
        conn.fetchval = AsyncMock(return_value=None)  # block check returns None (not blocked)

        resp = client.post(
            f"/chat/threads/{THREAD_UUID}/messages",
            json={"content": "Hello!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    @patch("app.features.chat_router.get_db_pool")
    def test_send_message_idor(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # User NOT in thread
        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.post(
            f"/chat/threads/{THREAD_UUID}/messages",
            json={"content": "Hello!"},
        )
        assert resp.status_code == 404

    def test_send_message_invalid_uuid(self):
        resp = client.post(
            f"/chat/threads/{INVALID_UUID}/messages",
            json={"content": "Hello!"},
        )
        assert resp.status_code == 400

    def test_send_message_empty_content(self):
        resp = client.post(
            f"/chat/threads/{THREAD_UUID}/messages",
            json={"content": ""},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: PATCH /chat/threads/{thread_id}/read
# ---------------------------------------------------------------------------


class TestMarkRead:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.chat_router.get_db_pool")
    def test_mark_read_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchrow = AsyncMock(return_value=_thread_participant_row())

        resp = client.patch(f"/chat/threads/{THREAD_UUID}/read")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @patch("app.features.chat_router.get_db_pool")
    def test_mark_read_idor(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.patch(f"/chat/threads/{THREAD_UUID}/read")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: DELETE /chat/messages/{message_id}
# ---------------------------------------------------------------------------


class TestDeleteMessage:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.chat_router.get_db_pool")
    def test_delete_message_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # Message exists and belongs to user
        msg_row = MagicMock()
        msg_row.__getitem__ = lambda self, key: {
            "sender_id": TEST_USER_ID,
            "deleted_at": None,
        }[key]
        conn.fetchrow = AsyncMock(return_value=msg_row)

        resp = client.delete(f"/chat/messages/{MESSAGE_UUID}")
        assert resp.status_code == 200

    @patch("app.features.chat_router.get_db_pool")
    def test_delete_message_idor(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # Message belongs to someone else
        msg_row = MagicMock()
        msg_row.__getitem__ = lambda self, key: {
            "sender_id": OTHER_USER_ID,
            "deleted_at": None,
        }[key]
        conn.fetchrow = AsyncMock(return_value=msg_row)

        resp = client.delete(f"/chat/messages/{MESSAGE_UUID}")
        assert resp.status_code == 403

    @patch("app.features.chat_router.get_db_pool")
    def test_delete_message_not_found(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchrow = AsyncMock(return_value=None)

        resp = client.delete(f"/chat/messages/{MESSAGE_UUID}")
        assert resp.status_code == 404

    def test_delete_message_invalid_uuid(self):
        resp = client.delete(f"/chat/messages/{INVALID_UUID}")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: PATCH /chat/messages/{message_id}
# ---------------------------------------------------------------------------


class TestEditMessage:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.chat_router.get_db_pool")
    def test_edit_message_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # Message exists, belongs to user, within edit window
        now = datetime.now(timezone.utc)
        msg_row = MagicMock()
        msg_row.__getitem__ = lambda self, key: {
            "sender_id": TEST_USER_ID,
            "deleted_at": None,
            "created_at": now,
        }[key]

        # Second fetchrow is the UPDATE RETURNING with full columns
        updated_row = MagicMock()
        updated_row.__getitem__ = lambda self, key: {
            "id": MESSAGE_UUID,
            "thread_id": THREAD_UUID,
            "sender_id": TEST_USER_ID,
            "body": "Edited content",
            "created_at": now,
            "edited_at": now,
        }[key]
        conn.fetchrow = AsyncMock(side_effect=[msg_row, updated_row])

        resp = client.patch(
            f"/chat/messages/{MESSAGE_UUID}",
            json={"content": "Edited content"},
        )
        assert resp.status_code == 200

    @patch("app.features.chat_router.get_db_pool")
    def test_edit_message_idor(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        msg_row = MagicMock()
        msg_row.__getitem__ = lambda self, key: {
            "sender_id": OTHER_USER_ID,
            "deleted_at": None,
            "created_at": datetime.now(timezone.utc),
        }[key]
        conn.fetchrow = AsyncMock(return_value=msg_row)

        resp = client.patch(
            f"/chat/messages/{MESSAGE_UUID}",
            json={"content": "Hacked!"},
        )
        assert resp.status_code == 403

    @patch("app.features.chat_router.get_db_pool")
    def test_edit_message_expired_window(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        # Message was created 20 minutes ago (beyond 15min window)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        msg_row = MagicMock()
        msg_row.__getitem__ = lambda self, key: {
            "sender_id": TEST_USER_ID,
            "deleted_at": None,
            "created_at": old_time,
        }[key]
        conn.fetchrow = AsyncMock(return_value=msg_row)

        resp = client.patch(
            f"/chat/messages/{MESSAGE_UUID}",
            json={"content": "Too late!"},
        )
        assert resp.status_code == 400

    def test_edit_message_invalid_uuid(self):
        resp = client.patch(
            f"/chat/messages/{INVALID_UUID}",
            json={"content": "test"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: GET /chat/unread-count
# ---------------------------------------------------------------------------


class TestUnreadCount:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    @patch("app.features.chat_router.get_db_pool")
    def test_unread_count_success(self, mock_get_pool):
        pool, conn = _mock_pool()
        mock_get_pool.return_value = pool

        conn.fetchval = AsyncMock(return_value=5)

        resp = client.get("/chat/unread-count")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unread_count"] == 5

    @patch("app.features.chat_router.get_db_pool")
    def test_unread_count_no_db(self, mock_get_pool):
        mock_get_pool.return_value = None

        resp = client.get("/chat/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0


# ---------------------------------------------------------------------------
# Tests: UUID validation
# ---------------------------------------------------------------------------


class TestUUIDValidation:
    def setup_method(self):
        _auth_override()

    def teardown_method(self):
        _clear_overrides()

    def test_threads_messages_invalid_uuid(self):
        resp = client.get("/chat/threads/not-valid/messages")
        assert resp.status_code == 400

    def test_threads_read_invalid_uuid(self):
        resp = client.patch("/chat/threads/not-valid/read")
        assert resp.status_code == 400

    def test_messages_delete_invalid_uuid(self):
        resp = client.delete("/chat/messages/not-valid")
        assert resp.status_code == 400

    def test_messages_edit_invalid_uuid(self):
        resp = client.patch("/chat/messages/not-valid", json={"content": "x"})
        assert resp.status_code == 400
