"""
Tests for app/features/gamification_router.py — gamification endpoints.

Covers:
  - GET  /gamification/profile              — in-memory fallback + mocked DB
  - GET  /gamification/achievements         — in-memory fallback + mocked DB
  - GET  /gamification/achievements/recent  — in-memory fallback + mocked DB
  - GET  /gamification/challenges           — in-memory fallback + mocked DB
  - POST /gamification/xp                   — in-memory fallback + mocked DB + auth
  - GET  /gamification/leaderboard          — in-memory fallback + mocked DB
  - Unit tests for XP/levelling helpers
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

_VALID_SECRET = "test-shared-secret-12345"
USER_ID = "dev-user-local"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conn_ctx():
    """Create a mock async context manager for get_conn()."""
    conn = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return conn, ctx


def _patch_secret():
    return patch("app.auth.API_SHARED_SECRET", _VALID_SECRET)


# ---------------------------------------------------------------------------
# Unit tests for XP / levelling helpers
# ---------------------------------------------------------------------------


class TestXPHelpers:
    """Unit tests for xp_for_level, level_from_xp, and xp_progress."""

    def test_xp_for_level_1(self):
        from app.features.gamification_router import xp_for_level
        assert xp_for_level(1) == 0

    def test_xp_for_level_2(self):
        from app.features.gamification_router import xp_for_level
        assert xp_for_level(2) == 100

    def test_xp_for_level_3(self):
        from app.features.gamification_router import xp_for_level
        assert xp_for_level(3) == 300

    def test_xp_for_level_10(self):
        from app.features.gamification_router import xp_for_level
        assert xp_for_level(10) == 4500

    def test_level_from_xp_zero(self):
        from app.features.gamification_router import level_from_xp
        assert level_from_xp(0) == 1

    def test_level_from_xp_negative(self):
        from app.features.gamification_router import level_from_xp
        assert level_from_xp(-10) == 1

    def test_level_from_xp_99(self):
        from app.features.gamification_router import level_from_xp
        assert level_from_xp(99) == 1

    def test_level_from_xp_100(self):
        from app.features.gamification_router import level_from_xp
        assert level_from_xp(100) == 2

    def test_level_from_xp_300(self):
        from app.features.gamification_router import level_from_xp
        assert level_from_xp(300) == 3

    def test_xp_progress_zero(self):
        from app.features.gamification_router import xp_progress
        p = xp_progress(0)
        assert p["level"] == 1
        assert p["current_xp"] == 0
        assert p["xp_to_next"] == 100
        assert p["total_xp"] == 0

    def test_xp_progress_150(self):
        from app.features.gamification_router import xp_progress
        p = xp_progress(150)
        assert p["level"] == 2
        assert p["current_xp"] == 50  # 150 - 100
        assert p["xp_to_next"] == 200  # 300 - 100
        assert p["total_xp"] == 150


# ---------------------------------------------------------------------------
# GET /gamification/profile — in-memory fallback (DB_ENABLED=false)
# ---------------------------------------------------------------------------


class TestGetProfileInMemory:
    """Tests for GET /gamification/profile when DB is disabled."""

    def test_returns_default_profile(self):
        """When DB is off, returns a zeroed-out default profile."""
        resp = client.get("/gamification/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "profile" in data
        profile = data["profile"]
        assert profile["total_xp"] == 0
        assert profile["level"] == 1
        assert profile["current_xp"] == 0
        assert profile["xp_to_next"] == 100
        assert profile["current_streak"] == 0
        assert profile["longest_streak"] == 0

    def test_profile_schema_fields(self):
        """Verify all expected fields exist in the profile response."""
        resp = client.get("/gamification/profile")
        data = resp.json()["profile"]
        expected_keys = {
            "total_xp", "level", "current_xp", "xp_to_next",
            "current_streak", "longest_streak", "last_activity_date",
            "weekly_xp", "monthly_xp", "achievements_unlocked",
            "achievements_total",
        }
        assert expected_keys.issubset(set(data.keys()))


# ---------------------------------------------------------------------------
# GET /gamification/profile — mocked DB
# ---------------------------------------------------------------------------


class TestGetProfileMockedDB:
    """Tests for GET /gamification/profile with mocked database."""

    def test_happy_path_with_xp(self):
        """When user has XP in DB, profile reflects level and streaks."""
        conn, ctx = _mock_conn_ctx()

        conn.execute = AsyncMock()  # INSERT ON CONFLICT DO NOTHING
        conn.fetchrow = AsyncMock(side_effect=[
            # user_gamification row
            {
                "total_xp": 350,
                "current_streak": 5,
                "longest_streak": 10,
                "last_activity_date": date(2026, 3, 2),
                "weekly_xp": 120,
                "monthly_xp": 350,
            },
            # achievement counts
            {"unlocked": 4, "total": 30},
        ])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/profile")

        assert resp.status_code == 200
        profile = resp.json()["profile"]
        assert profile["total_xp"] == 350
        assert profile["level"] == 3
        assert profile["current_streak"] == 5
        assert profile["longest_streak"] == 10
        assert profile["last_activity_date"] == "2026-03-02"
        assert profile["weekly_xp"] == 120
        assert profile["monthly_xp"] == 350
        assert profile["achievements_unlocked"] == 4
        assert profile["achievements_total"] == 30

    def test_new_user_no_row(self):
        """When fetchrow returns None for user, profile is default with total achievements."""
        conn, ctx = _mock_conn_ctx()

        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[
            None,  # No user_gamification row
            {"unlocked": 0, "total": 30},
        ])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/profile")

        assert resp.status_code == 200
        profile = resp.json()["profile"]
        assert profile["total_xp"] == 0
        assert profile["level"] == 1
        assert profile["achievements_total"] == 30

    def test_db_error_returns_500(self):
        """When DB raises a PostgresError, return 500."""
        import asyncpg
        conn, ctx = _mock_conn_ctx()

        conn.execute = AsyncMock(side_effect=asyncpg.PostgresError("conn failed"))

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/profile")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /gamification/achievements — in-memory fallback
# ---------------------------------------------------------------------------


class TestListAchievementsInMemory:
    """Tests for GET /gamification/achievements when DB is disabled."""

    def test_returns_empty_list(self):
        """When DB is off, returns an empty achievements list."""
        resp = client.get("/gamification/achievements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["achievements"] == []

    def test_with_category_filter_returns_empty(self):
        """Category filter param works but still returns empty in-memory."""
        resp = client.get("/gamification/achievements?category=collection")
        assert resp.status_code == 200
        assert resp.json()["achievements"] == []


# ---------------------------------------------------------------------------
# GET /gamification/achievements — mocked DB
# ---------------------------------------------------------------------------


class TestListAchievementsMockedDB:
    """Tests for GET /gamification/achievements with mocked database."""

    def _make_achievement_row(self, ach_id="first_item", unlocked=False):
        return {
            "id": ach_id,
            "title": "First Item",
            "description": "Add your first item",
            "icon": "trophy",
            "category": "collection",
            "xp_reward": 50,
            "tier": "bronze",
            "threshold": 1,
            "sort_order": 1,
            "unlocked_at": datetime.now(timezone.utc) if unlocked else None,
            "progress": 1 if unlocked else 0,
        }

    def test_happy_path_all_achievements(self):
        """Returns all achievements with unlock status."""
        conn, ctx = _mock_conn_ctx()
        row1 = self._make_achievement_row("first_item", unlocked=True)
        row2 = self._make_achievement_row("collector_10", unlocked=False)
        row2["id"] = "collector_10"
        row2["title"] = "Collector 10"
        row2["sort_order"] = 2
        conn.fetch = AsyncMock(return_value=[row1, row2])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/achievements")

        assert resp.status_code == 200
        achievements = resp.json()["achievements"]
        assert len(achievements) == 2
        assert achievements[0]["id"] == "first_item"
        assert achievements[0]["unlocked"] is True
        assert achievements[1]["id"] == "collector_10"
        assert achievements[1]["unlocked"] is False

    def test_with_category_filter(self):
        """Category filter is passed to the query."""
        conn, ctx = _mock_conn_ctx()
        row = self._make_achievement_row("first_item", unlocked=False)
        conn.fetch = AsyncMock(return_value=[row])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/achievements?category=collection")

        assert resp.status_code == 200
        assert len(resp.json()["achievements"]) == 1
        # Verify the category filter was passed (fetch called with user_id + category)
        call_args = conn.fetch.call_args
        assert call_args[0][1] == USER_ID  # user_id
        assert call_args[0][2] == "collection"  # category

    def test_empty_achievements(self):
        """No achievements in DB returns empty list."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/achievements")

        assert resp.status_code == 200
        assert resp.json()["achievements"] == []

    def test_db_error_returns_500(self):
        """When DB raises a PostgresError, return 500."""
        import asyncpg
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(side_effect=asyncpg.PostgresError("query failed"))

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/achievements")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /gamification/achievements/recent — in-memory fallback
# ---------------------------------------------------------------------------


class TestRecentAchievementsInMemory:
    """Tests for GET /gamification/achievements/recent when DB is disabled."""

    def test_returns_empty_list(self):
        """When DB is off, returns an empty achievements list."""
        resp = client.get("/gamification/achievements/recent")
        assert resp.status_code == 200
        assert resp.json()["achievements"] == []

    def test_limit_param_accepted(self):
        """Limit param is accepted without error."""
        resp = client.get("/gamification/achievements/recent?limit=5")
        assert resp.status_code == 200
        assert resp.json()["achievements"] == []


# ---------------------------------------------------------------------------
# GET /gamification/achievements/recent — mocked DB
# ---------------------------------------------------------------------------


class TestRecentAchievementsMockedDB:
    """Tests for GET /gamification/achievements/recent with mocked database."""

    def test_happy_path(self):
        """Returns recently unlocked achievements."""
        conn, ctx = _mock_conn_ctx()
        now = datetime.now(timezone.utc)
        row = {
            "id": "streak_3",
            "title": "3-Day Streak",
            "description": "Maintain a 3-day streak",
            "icon": "fire",
            "category": "engagement",
            "xp_reward": 25,
            "tier": "bronze",
            "threshold": 3,
            "sort_order": 10,
            "unlocked_at": now,
            "progress": 5,
        }
        conn.fetch = AsyncMock(return_value=[row])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/achievements/recent")

        assert resp.status_code == 200
        achievements = resp.json()["achievements"]
        assert len(achievements) == 1
        assert achievements[0]["id"] == "streak_3"
        assert achievements[0]["unlocked"] is True

    def test_limit_passed_to_query(self):
        """Custom limit param is passed to the DB query."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/achievements/recent?limit=3")

        assert resp.status_code == 200
        call_args = conn.fetch.call_args
        assert call_args[0][2] == 3  # limit param

    def test_limit_validation_min(self):
        """Limit below 1 returns 422."""
        resp = client.get("/gamification/achievements/recent?limit=0")
        assert resp.status_code == 422

    def test_limit_validation_max(self):
        """Limit above 50 returns 422."""
        resp = client.get("/gamification/achievements/recent?limit=51")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /gamification/challenges — in-memory fallback
# ---------------------------------------------------------------------------


class TestListChallengesInMemory:
    """Tests for GET /gamification/challenges when DB is disabled."""

    def test_returns_empty_list(self):
        """When DB is off, returns empty challenges list."""
        resp = client.get("/gamification/challenges")
        assert resp.status_code == 200
        assert resp.json()["challenges"] == []

    def test_with_type_filter(self):
        """Challenge type filter is accepted without error."""
        resp = client.get("/gamification/challenges?challenge_type=weekly")
        assert resp.status_code == 200
        assert resp.json()["challenges"] == []

    def test_invalid_challenge_type_returns_422(self):
        """Invalid challenge_type param returns 422."""
        resp = client.get("/gamification/challenges?challenge_type=invalid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /gamification/challenges — mocked DB
# ---------------------------------------------------------------------------


class TestListChallengesMockedDB:
    """Tests for GET /gamification/challenges with mocked database."""

    def _make_challenge_row(self, completed=False):
        return {
            "id": str(uuid4()),
            "title": "Weekly Scanner",
            "description": "Scan 5 items this week",
            "challenge_type": "weekly",
            "category": None,
            "target_count": 5,
            "xp_reward": 100,
            "start_date": date(2026, 3, 1),
            "end_date": date(2026, 3, 7),
            "current_count": 5 if completed else 2,
            "completed": completed,
            "completed_at": datetime.now(timezone.utc) if completed else None,
        }

    def test_happy_path(self):
        """Returns active challenges with user progress."""
        conn, ctx = _mock_conn_ctx()
        row = self._make_challenge_row(completed=False)
        conn.fetch = AsyncMock(return_value=[row])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/challenges")

        assert resp.status_code == 200
        challenges = resp.json()["challenges"]
        assert len(challenges) == 1
        assert challenges[0]["title"] == "Weekly Scanner"
        assert challenges[0]["current_count"] == 2
        assert challenges[0]["completed"] is False

    def test_completed_challenge(self):
        """Completed challenges show completed=True with completed_at."""
        conn, ctx = _mock_conn_ctx()
        row = self._make_challenge_row(completed=True)
        conn.fetch = AsyncMock(return_value=[row])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/challenges")

        assert resp.status_code == 200
        challenges = resp.json()["challenges"]
        assert challenges[0]["completed"] is True
        assert challenges[0]["completed_at"] is not None

    def test_type_filter_passed_to_query(self):
        """When challenge_type is provided, it's included in the query args."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/challenges?challenge_type=monthly")

        assert resp.status_code == 200
        call_args = conn.fetch.call_args
        assert call_args[0][3] == "monthly"  # challenge_type param

    def test_empty_challenges(self):
        """No active challenges returns empty list."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/challenges")

        assert resp.status_code == 200
        assert resp.json()["challenges"] == []

    def test_db_error_returns_500(self):
        """When DB raises a PostgresError, return 500."""
        import asyncpg
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(side_effect=asyncpg.PostgresError("query failed"))

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/challenges")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /gamification/xp — in-memory fallback
# ---------------------------------------------------------------------------


class TestAwardXPInMemory:
    """Tests for POST /gamification/xp when DB is disabled."""

    def test_award_xp_returns_success(self):
        """When DB is off, returns awarded=True with the requested amount."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": 50, "reason": "test"},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["awarded"] is True
        assert data["amount"] == 50
        assert data["new_total"] == 50

    def test_award_xp_default_reason(self):
        """When reason is omitted, default 'manual_award' is used."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": 100},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /gamification/xp — auth guard
# ---------------------------------------------------------------------------


class TestAwardXPAuth:
    """Tests for POST /gamification/xp auth requirements."""

    def test_missing_api_key_returns_422(self):
        """Missing X-API-Key header returns 422."""
        resp = client.post(
            "/gamification/xp",
            json={"user_id": "user-123", "amount": 50},
        )
        assert resp.status_code == 422

    def test_wrong_api_key_returns_401(self):
        """Invalid X-API-Key returns 401."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": 50},
                headers={"X-API-Key": "wrong-key"},
            )
        assert resp.status_code == 401

    def test_api_key_not_configured_returns_500(self):
        """When API_SHARED_SECRET is empty, return 500."""
        with patch("app.auth.API_SHARED_SECRET", ""):
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": 50},
                headers={"X-API-Key": "anything"},
            )
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /gamification/xp — validation
# ---------------------------------------------------------------------------


class TestAwardXPValidation:
    """Tests for POST /gamification/xp input validation."""

    def test_missing_user_id_returns_422(self):
        """Missing user_id in body returns 422."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"amount": 50},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 422

    def test_empty_user_id_returns_422(self):
        """Empty user_id returns 422 (min_length=1)."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "", "amount": 50},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 422

    def test_amount_zero_returns_422(self):
        """Amount of 0 fails validation (ge=1)."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": 0},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 422

    def test_amount_negative_returns_422(self):
        """Negative amount fails validation."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": -10},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 422

    def test_amount_exceeds_max_returns_422(self):
        """Amount above 10000 fails validation (le=10000)."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": 10001},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 422

    def test_reason_too_long_returns_422(self):
        """Reason exceeding 200 chars fails validation."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-123", "amount": 50, "reason": "x" * 201},
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 422

    def test_missing_body_returns_422(self):
        """No JSON body returns 422."""
        with _patch_secret():
            resp = client.post(
                "/gamification/xp",
                headers={"X-API-Key": _VALID_SECRET},
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /gamification/xp — mocked DB
# ---------------------------------------------------------------------------


class TestAwardXPMockedDB:
    """Tests for POST /gamification/xp with mocked database."""

    def test_happy_path_new_user(self):
        """Award XP to a new user — upsert creates row."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value={
            "total_xp": 50,
            "current_streak": 1,
            "longest_streak": 1,
        })
        conn.execute = AsyncMock()

        with _patch_secret(), \
             patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-new", "amount": 50, "reason": "first_scan"},
                headers={"X-API-Key": _VALID_SECRET},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["awarded"] is True
        assert data["amount"] == 50
        assert data["new_total"] == 50
        assert data["level"] == 1
        assert data["reason"] == "first_scan"
        assert data["current_streak"] == 1

    def test_level_up_after_award(self):
        """Awarding XP that crosses level threshold shows new level."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value={
            "total_xp": 150,
            "current_streak": 3,
            "longest_streak": 7,
        })
        conn.execute = AsyncMock()

        with _patch_secret(), \
             patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-lvlup", "amount": 100},
                headers={"X-API-Key": _VALID_SECRET},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["level"] == 2
        assert data["new_total"] == 150

    def test_streak_achievements_checked(self):
        """When streak >= 3, streak_3 achievement is upserted."""
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(return_value={
            "total_xp": 200,
            "current_streak": 7,
            "longest_streak": 7,
        })
        conn.execute = AsyncMock()

        with _patch_secret(), \
             patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-streak", "amount": 10},
                headers={"X-API-Key": _VALID_SECRET},
            )

        assert resp.status_code == 200
        # Verify streak achievement upserts were called
        # streak_3 and streak_7 should be inserted (current_streak=7)
        execute_calls = conn.execute.call_args_list
        # First call: UPDATE level, then streak_3, streak_7
        assert len(execute_calls) >= 3

    def test_db_error_returns_500(self):
        """When DB raises a PostgresError, return 500."""
        import asyncpg
        conn, ctx = _mock_conn_ctx()
        conn.fetchrow = AsyncMock(side_effect=asyncpg.PostgresError("insert failed"))

        with _patch_secret(), \
             patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.post(
                "/gamification/xp",
                json={"user_id": "user-err", "amount": 10},
                headers={"X-API-Key": _VALID_SECRET},
            )

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /gamification/leaderboard — in-memory fallback
# ---------------------------------------------------------------------------


class TestGetLeaderboardInMemory:
    """Tests for GET /gamification/leaderboard when DB is disabled."""

    def test_returns_empty_leaderboard(self):
        """When DB is off, returns empty leaderboard with null rank."""
        resp = client.get("/gamification/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["leaderboard"] == []
        assert data["user_rank"] is None
        assert data["total_count"] == 0

    def test_period_param_accepted(self):
        """Period param is accepted (weekly/monthly/alltime)."""
        for period in ("weekly", "monthly", "alltime"):
            resp = client.get(f"/gamification/leaderboard?period={period}")
            assert resp.status_code == 200

    def test_invalid_period_returns_422(self):
        """Invalid period value returns 422."""
        resp = client.get("/gamification/leaderboard?period=daily")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /gamification/leaderboard — mocked DB
# ---------------------------------------------------------------------------


class TestGetLeaderboardMockedDB:
    """Tests for GET /gamification/leaderboard with mocked database."""

    def _make_leaderboard_row(self, user_id="user-1", xp=500, level=4, streak=3):
        return {
            "user_id": user_id,
            "xp": xp,
            "total_xp": xp,
            "level": level,
            "current_streak": streak,
            "display_name": f"Player {user_id}",
            "avatar_url": None,
            "avatar_color": "#81D8D0",
        }

    def test_happy_path_weekly(self):
        """Returns weekly leaderboard entries with correct ranking."""
        conn, ctx = _mock_conn_ctx()
        row1 = self._make_leaderboard_row("user-a", 500, 4, 5)
        row2 = self._make_leaderboard_row("user-b", 300, 3, 2)
        conn.fetch = AsyncMock(return_value=[row1, row2])
        conn.fetchrow = AsyncMock(side_effect=[
            {"cnt": 2},    # total count
            {"rank": 1},   # user rank
        ])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/leaderboard?period=weekly")

        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "weekly"
        assert len(data["leaderboard"]) == 2
        assert data["leaderboard"][0]["rank"] == 1
        assert data["leaderboard"][0]["user_id"] == "user-a"
        assert data["leaderboard"][0]["total_xp"] == 500
        assert data["leaderboard"][1]["rank"] == 2
        assert data["total_count"] == 2
        assert data["user_rank"] == 1

    def test_alltime_period(self):
        """Alltime period queries total_xp column."""
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchrow = AsyncMock(side_effect=[
            {"cnt": 0},
            {"rank": 1},
        ])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/leaderboard?period=alltime")

        assert resp.status_code == 200
        assert resp.json()["period"] == "alltime"

    def test_pagination_offset(self):
        """Offset parameter adjusts rank numbering."""
        conn, ctx = _mock_conn_ctx()
        row = self._make_leaderboard_row("user-x", 100, 2, 1)
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchrow = AsyncMock(side_effect=[
            {"cnt": 15},
            {"rank": 11},
        ])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/leaderboard?offset=10&limit=5")

        assert resp.status_code == 200
        data = resp.json()
        # rank should be offset + i + 1 = 10 + 0 + 1 = 11
        assert data["leaderboard"][0]["rank"] == 11

    def test_limit_validation_max(self):
        """Limit above 100 returns 422."""
        resp = client.get("/gamification/leaderboard?limit=101")
        assert resp.status_code == 422

    def test_limit_validation_min(self):
        """Limit below 1 returns 422."""
        resp = client.get("/gamification/leaderboard?limit=0")
        assert resp.status_code == 422

    def test_offset_negative_returns_422(self):
        """Negative offset returns 422."""
        resp = client.get("/gamification/leaderboard?offset=-1")
        assert resp.status_code == 422

    def test_db_error_returns_500(self):
        """When DB raises a PostgresError, return 500."""
        import asyncpg
        conn, ctx = _mock_conn_ctx()
        conn.fetch = AsyncMock(side_effect=asyncpg.PostgresError("timeout"))

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/leaderboard")

        assert resp.status_code == 500

    def test_leaderboard_entry_schema(self):
        """Verify the shape of each leaderboard entry."""
        conn, ctx = _mock_conn_ctx()
        row = self._make_leaderboard_row("user-schema", 200, 2, 1)
        conn.fetch = AsyncMock(return_value=[row])
        conn.fetchrow = AsyncMock(side_effect=[
            {"cnt": 1},
            {"rank": 1},
        ])

        with patch("app.features.gamification_router.db_configured", return_value=True), \
             patch("app.features.gamification_router.get_conn", return_value=ctx):
            resp = client.get("/gamification/leaderboard")

        entry = resp.json()["leaderboard"][0]
        expected_keys = {
            "rank", "user_id", "display_name", "avatar_url",
            "avatar_color", "total_xp", "level", "current_streak",
        }
        assert expected_keys == set(entry.keys())
