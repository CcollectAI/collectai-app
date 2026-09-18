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
    """include_past=False adds `date >= CURRENT_DATE` and binds NOTHING.

    Updated 2026-09-18. These asserted `date >= $1` with `params[0] ==
    date.today()` — a Python date bound from the SERVER BOX, which is
    Europe/Paris, while the database is UTC. Between 00:00 and 02:00 CEST the
    two are different days, and the nearby-events query
    (`events_core.py:491`) has always written `date >= CURRENT_DATE` for this
    same predicate, as does the feed's own RPC. So an event happening today was
    upcoming on one screen and already gone from another, for two hours a night.

    `docs/EVENT_QUALITY_PLAN.md:215` states the canonical gate as
    `(p_include_past OR e.date >= CURRENT_DATE)` and names this helper as one of
    the places that must match it; `docs/ARCHITECTURE.md` gives the rule —
    derive the date in SQL pinned to UTC rather than binding the host's idea of
    today.
    """

    def test_excludes_past_events(self):
        conditions, params, idx = build_event_conditions(
            category_id=None, include_past=False,
        )
        assert any("date >=" in c for c in conditions)

    def test_the_date_gate_binds_no_parameter(self):
        """The property that makes the three query paths agree.

        A bound date can disagree with a `CURRENT_DATE` elsewhere in the same
        statement; `CURRENT_DATE` cannot disagree with itself.
        """
        conditions, params, idx = build_event_conditions(
            category_id=None, include_past=False,
        )
        assert "date >= CURRENT_DATE" in conditions
        assert not any("date >= $" in c for c in conditions)
        assert params == []
        assert idx == 1

    def test_date_and_category_param_indices(self):
        """The category is now $1, because the date no longer takes a slot."""
        conditions, params, idx = build_event_conditions(
            category_id="funko", include_past=False,
        )
        assert "date >= CURRENT_DATE" in conditions
        assert "category_id = $1" in conditions
        assert params == ["funko"]
        assert idx == 2


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
        # The date gate binds nothing, so category and user_id shift down one.
        assert "date >= CURRENT_DATE" in conditions
        assert "category_id = $1" in conditions
        assert "created_by = $2" in conditions[3]  # inside the OR clause
        assert params == ["manga", "user-abc"]
        assert idx == 3


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


class TestDisplayGateIsAlwaysApplied:
    """The feed gate must be present on EVERY conditions build.

    build_event_conditions is the shared chokepoint for fetch_events_basic
    and count_events_basic; if the gate is dropped here, the list and the
    count silently start including quarantined and low-quality rows again.
    Added 2026-07-27 alongside the gate itself.
    """

    def test_gate_present_with_no_filters(self):
        conditions, _params, _idx = build_event_conditions(None, True)
        joined = " AND ".join(conditions)
        assert "quality_score" in joined
        assert "source NOT IN" in joined

    def test_gate_present_with_all_filters(self):
        conditions, _params, _idx = build_event_conditions("manga", False, "user-abc")
        joined = " AND ".join(conditions)
        assert "quality_score IS NULL OR quality_score >= 40" in joined

    def test_gate_adds_no_bind_params(self):
        """It must not renumber the caller's positional placeholders."""
        _c, params_without, idx_without = build_event_conditions(None, True)
        _c2, params_with, idx_with = build_event_conditions("manga", False, "u")
        assert len(params_without) == 0
        # 2, not 3: category + user_id. The date gate stopped binding one when
        # it moved to CURRENT_DATE (2026-09-18).
        assert len(params_with) == 2
        assert idx_with == 3

    def test_gate_sql_refuses_a_non_identifier_source(self):
        """The only values interpolated into SQL are guarded."""
        import app.features.events.events_helpers as helpers
        import app.lib.event_quality as eq

        original = eq.UNRELIABLE_FREE_TEXT_SOURCES
        try:
            eq.UNRELIABLE_FREE_TEXT_SOURCES = frozenset({"x'; DROP TABLE events;--"})
            with pytest.raises(ValueError):
                helpers.display_gate_sql()
        finally:
            eq.UNRELIABLE_FREE_TEXT_SOURCES = original
