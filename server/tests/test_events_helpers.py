"""Tests for app/features/events/events_helpers.py — shared helpers and constants.

Covers:
  - build_event_conditions with no filters
  - build_event_conditions with category_id filter
  - build_event_conditions with include_past=False
  - build_event_conditions with user_id (public/private logic)
  - build_event_conditions with all filters combined
  - EVENT_COLUMNS has all expected column names
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("PER_USER_RATE_LIMIT_ENABLED", "false")

from app.features.events.events_helpers import (  # noqa: E402
    EVENT_COLUMNS,
    build_event_conditions,
)


# ---------------------------------------------------------------------------
# build_event_conditions
# ---------------------------------------------------------------------------

class TestBuildEventConditionsNoFilters:
    """No optional filters — only status='published' and is_public=true."""

    def test_base_conditions(self):
        conditions, params, idx = build_event_conditions(
            category_id=None, include_past=True, user_id=None,
        )
        assert "status = 'published'" in conditions
        assert "is_public = true" in conditions
        assert params == []
        assert idx == 1

    def test_no_date_filter_when_include_past(self):
        conditions, params, _ = build_event_conditions(
            category_id=None, include_past=True,
        )
        # No date condition should be present
        date_conditions = [c for c in conditions if "date" in c]
        assert len(date_conditions) == 0


class TestBuildEventConditionsCategoryFilter:
    """category_id adds a parameterized condition."""

    def test_category_id_adds_condition(self):
        conditions, params, idx = build_event_conditions(
            category_id="watches", include_past=True,
        )
        assert any("category_id" in c for c in conditions)
        assert "watches" in params

    def test_category_id_param_index(self):
        conditions, params, idx = build_event_conditions(
            category_id="lego", include_past=True,
        )
        # category_id is the first param ($1)
        assert "category_id = $1" in conditions
        assert params == ["lego"]
        assert idx == 2


class TestBuildEventConditionsIncludePast:
    """include_past=False adds a date >= $N condition."""

    def test_excludes_past_events(self):
        conditions, params, idx = build_event_conditions(
            category_id=None, include_past=False,
        )
        assert any("date >=" in c for c in conditions)
        # The param should be today's date string
        assert params[0] == date.today().isoformat()

    def test_date_param_index(self):
        conditions, params, idx = build_event_conditions(
            category_id=None, include_past=False,
        )
        assert "date >= $1" in conditions
        assert idx == 2

    def test_date_and_category_param_indices(self):
        """When both include_past=False and category_id are set, indices are sequential."""
        conditions, params, idx = build_event_conditions(
            category_id="funko", include_past=False,
        )
        assert "date >= $1" in conditions
        assert "category_id = $2" in conditions
        assert params == [date.today().isoformat(), "funko"]
        assert idx == 3


class TestBuildEventConditionsUserId:
    """user_id adds public/private visibility logic."""

    def test_user_id_adds_public_or_owner(self):
        conditions, params, idx = build_event_conditions(
            category_id=None, include_past=True, user_id="user-123",
        )
        # Should have (is_public = true OR created_by = $N) instead of just is_public
        public_conditions = [c for c in conditions if "is_public" in c]
        assert len(public_conditions) == 1
        assert "created_by" in public_conditions[0]
        assert "user-123" in params

    def test_no_user_id_adds_strict_public(self):
        conditions, params, _ = build_event_conditions(
            category_id=None, include_past=True, user_id=None,
        )
        assert "is_public = true" in conditions
        # No created_by reference
        assert not any("created_by" in c for c in conditions)

    def test_all_filters_combined(self):
        """include_past=False + category_id + user_id — all conditions present."""
        conditions, params, idx = build_event_conditions(
            category_id="manga", include_past=False, user_id="user-abc",
        )
        assert "status = 'published'" in conditions
        assert "date >= $1" in conditions
        assert "category_id = $2" in conditions
        assert "created_by = $3" in conditions[3]  # inside the OR clause
        assert params == [date.today().isoformat(), "manga", "user-abc"]
        assert idx == 4


# ---------------------------------------------------------------------------
# EVENT_COLUMNS
# ---------------------------------------------------------------------------

class TestEventColumns:
    def test_event_columns_type(self):
        assert isinstance(EVENT_COLUMNS, str)

    def test_event_columns_contains_core_fields(self):
        expected_core = [
            "id", "title", "kind", "category_id", "date", "time",
            "end_date", "location", "description", "format", "status",
        ]
        for col in expected_core:
            assert col in EVENT_COLUMNS, f"Missing core column: {col}"

    def test_event_columns_contains_geo_fields(self):
        for col in ["latitude", "longitude"]:
            assert col in EVENT_COLUMNS, f"Missing geo column: {col}"

    def test_event_columns_contains_meta_fields(self):
        for col in ["created_by", "source", "created_at", "is_public"]:
            assert col in EVENT_COLUMNS, f"Missing meta column: {col}"

    def test_event_columns_contains_count_fields(self):
        for col in ["attendee_count", "going_count", "interested_count", "max_attendees"]:
            assert col in EVENT_COLUMNS, f"Missing count column: {col}"

    def test_event_columns_contains_sponsor_fields(self):
        for col in ["is_sponsored", "sponsor_name", "sponsor_logo_url", "sponsor_expires_at"]:
            assert col in EVENT_COLUMNS, f"Missing sponsor column: {col}"

    def test_event_columns_contains_url_fields(self):
        for col in ["online_url", "image_url"]:
            assert col in EVENT_COLUMNS, f"Missing URL column: {col}"
