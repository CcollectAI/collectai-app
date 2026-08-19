"""Tests for app/features/social_router.py — block/unblock user endpoints.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
The social_router endpoints require a DB pool, so these tests verify:
- Input validation (UUID format, self-block)
- Auth dependency (dev mode bypass)
- Offline mode responses when pool is None
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient
from main import app  # noqa: E402

client = TestClient(app)

DEV_USER_ID = os.environ.get("DEV_USER_ID", "dev-user-local")
TARGET_USER_ID = "00000000-0000-0000-0000-000000000099"


# ---------------------------------------------------------------------------
# Block endpoint tests
# ---------------------------------------------------------------------------

class TestBlockUser:
    def test_block_user_offline_mode(self):
        """Block succeeds in offline mode (no DB pool)."""
        resp = client.post(f"/social/block/{TARGET_USER_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "offline" in data["message"].lower() or "blocked" in data["message"].lower()

    def test_block_invalid_uuid(self):
        """Block rejects invalid UUID."""
        resp = client.post("/social/block/not-a-uuid")
        assert resp.status_code == 400

    def test_block_self(self):
        """Block rejects self-block."""
        resp = client.post(f"/social/block/{DEV_USER_ID}")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Unblock endpoint tests
# ---------------------------------------------------------------------------

class TestUnblockUser:
    def test_unblock_user_offline_mode(self):
        """Unblock succeeds in offline mode."""
        resp = client.delete(f"/social/block/{TARGET_USER_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_unblock_invalid_uuid(self):
        """Unblock rejects invalid UUID."""
        resp = client.delete("/social/block/not-a-uuid")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# List blocked endpoint tests
# ---------------------------------------------------------------------------

class TestListBlocked:
    def test_list_blocked_offline_mode(self):
        """List blocked returns empty list in offline mode."""
        resp = client.get("/social/blocked")
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked"] == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_block_same_user_twice_offline(self):
        """Blocking the same user twice should not error (idempotent)."""
        resp1 = client.post(f"/social/block/{TARGET_USER_ID}")
        assert resp1.status_code == 200
        resp2 = client.post(f"/social/block/{TARGET_USER_ID}")
        assert resp2.status_code == 200

    def test_unblock_without_prior_block(self):
        """Unblocking a user not blocked should succeed gracefully."""
        resp = client.delete(f"/social/block/{TARGET_USER_ID}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# User search endpoint tests
# ---------------------------------------------------------------------------

class TestSearchUsers:
    def test_search_users_offline_mode(self):
        """Search returns empty list in offline mode (no DB pool)."""
        resp = client.get("/social/users/search", params={"q": "alice"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["users"] == []

    def test_search_users_missing_query(self):
        """Search requires 'q' query param."""
        resp = client.get("/social/users/search")
        assert resp.status_code == 422  # FastAPI validation error

    def test_search_users_empty_query(self):
        """Search rejects empty query (min_length=1)."""
        resp = client.get("/social/users/search", params={"q": ""})
        assert resp.status_code == 422

    def test_search_users_with_limit(self):
        """Search accepts custom limit parameter."""
        resp = client.get("/social/users/search", params={"q": "test", "limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["users"], list)

    def test_search_users_limit_bounds(self):
        """Search rejects limit out of bounds."""
        resp = client.get("/social/users/search", params={"q": "test", "limit": 0})
        assert resp.status_code == 422
        resp2 = client.get("/social/users/search", params={"q": "test", "limit": 100})
        assert resp2.status_code == 422


class TestLeaderboardOrderDirections:
    """Every ranking column must carry its OWN direction.

    The template used to append `DESC` to whatever the metric contributed, and
    a two-column metric was therefore inverted: `ORDER BY documented_pct,
    documented_count DESC` applies DESC to the LAST column only, so the
    percentage sorted ASCENDING and the LEAST-documented member ranked #1.

    Proven on prod against a synthetic set (90% ranked #3, 10% ranked #1) and
    invisible on the live board, where every member is at 0% and everything
    ties. That is the shape this class exists to stop: a sort direction is not
    something an empty or uniform dataset can test.
    """

    def _source(self) -> str:
        import inspect
        from app.features import social_router

        return inspect.getsource(social_router.get_category_leaderboard)

    def test_the_rank_template_does_not_append_a_direction(self):
        src = self._source()
        assert "RANK() OVER (ORDER BY {order_expr})" in src, (
            "the template appends a direction again — a multi-column metric "
            "will be silently inverted"
        )
        assert "{order_expr} DESC" not in src

    def test_every_metric_states_its_own_direction(self):
        src = self._source()
        for expr in ("total_value DESC", "item_count DESC"):
            assert expr in src, f"{expr} lost its direction"
        # Both columns, both directions — the one that was wrong.
        assert "documented_pct DESC, documented_count DESC" in src

    def test_documented_ranks_on_the_share_not_the_raw_count(self):
        """8 of 10 must beat 20 of 400. Ranking on the count would make a big
        careless collection outrank a small meticulous one, which inverts the
        behaviour this metric exists to reward."""
        src = self._source()
        assert "documented_pct DESC, documented_count DESC" in src
        assert "documented_count DESC, documented_pct" not in src
