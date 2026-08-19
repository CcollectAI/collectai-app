"""
Tests for app/agents/dossier_agent.py — Dossier Factory.

Covers:
  - Helper functions: _parse_json_field, _ts, _compute_authenticity_signals, _compute_completeness
  - generate_dossier() with fully mocked DB connection
  - ItemDossier to_dict() serialization
  - HTML export format (via dossier_router._render_html)
  - Error handling: item not found
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestParseJsonField:
    """Tests for _parse_json_field()."""

    def test_none(self):
        from app.agents.dossier_agent import _parse_json_field

        assert _parse_json_field(None) is None

    def test_valid_json_string(self):
        from app.agents.dossier_agent import _parse_json_field

        assert _parse_json_field('{"key": "value"}') == {"key": "value"}

    def test_invalid_json_string(self):
        from app.agents.dossier_agent import _parse_json_field

        assert _parse_json_field("not json") == "not json"

    def test_dict_passthrough(self):
        from app.agents.dossier_agent import _parse_json_field

        d = {"a": 1}
        assert _parse_json_field(d) is d

    def test_list_passthrough(self):
        from app.agents.dossier_agent import _parse_json_field

        lst = [1, 2, 3]
        assert _parse_json_field(lst) is lst


class TestTs:
    """Tests for _ts() helper."""

    def test_none(self):
        from app.agents.dossier_agent import _ts

        assert _ts(None) == ""

    def test_datetime_object(self):
        from app.agents.dossier_agent import _ts

        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _ts(dt)
        assert "2026-01-15" in result

    def test_string_passthrough(self):
        from app.agents.dossier_agent import _ts

        assert _ts("2026-01-15") == "2026-01-15"


class TestComputeAuthenticitySignals:
    """Tests for _compute_authenticity_signals()."""

    def test_empty_events(self):
        from app.agents.dossier_agent import _compute_authenticity_signals

        assert _compute_authenticity_signals([]) == []

    def test_verified_event(self):
        from app.agents.dossier_agent import _compute_authenticity_signals

        events = [{"event_type": "verified", "source": "manual"}]
        signals = _compute_authenticity_signals(events)
        assert "owner_verified" in signals

    def test_graded_event(self):
        from app.agents.dossier_agent import _compute_authenticity_signals

        events = [{"event_type": "graded", "source": "PSA"}]
        signals = _compute_authenticity_signals(events)
        assert "professionally_graded" in signals

    def test_receipt_source(self):
        from app.agents.dossier_agent import _compute_authenticity_signals

        events = [{"event_type": "purchase", "source": "receipt"}]
        signals = _compute_authenticity_signals(events)
        assert "receipt_on_file" in signals
        assert "purchase_recorded" in signals

    def test_multiple_signals(self):
        from app.agents.dossier_agent import _compute_authenticity_signals

        events = [
            {"event_type": "verified", "source": "owner"},
            {"event_type": "graded", "source": "PSA"},
            {"event_type": "purchase", "source": "receipt"},
        ]
        signals = _compute_authenticity_signals(events)
        assert len(signals) == 4  # verified + graded + receipt + purchase


class TestComputeCompleteness:
    """Tests for _compute_completeness()."""

    def test_all_present(self):
        from app.agents.dossier_agent import _compute_completeness

        score = _compute_completeness(
            has_photo=True,
            has_provenance=True,
            has_prediction=True,
            has_attributes=True,
            has_comps=True,
        )
        assert score == 1.0

    def test_none_present(self):
        from app.agents.dossier_agent import _compute_completeness

        score = _compute_completeness(
            has_photo=False,
            has_provenance=False,
            has_prediction=False,
            has_attributes=False,
            has_comps=False,
        )
        assert score == 0.0

    def test_partial(self):
        from app.agents.dossier_agent import _compute_completeness

        score = _compute_completeness(
            has_photo=True,
            has_provenance=False,
            has_prediction=True,
            has_attributes=False,
            has_comps=True,
        )
        assert score == 0.6


# ---------------------------------------------------------------------------
# ItemDossier tests
# ---------------------------------------------------------------------------


class TestItemDossier:
    """Tests for ItemDossier dataclass."""

    def test_to_dict(self):
        from app.agents.dossier_agent import ItemDossier

        dossier = ItemDossier(
            item_id="test-id",
            generated_at="2026-01-15T12:00:00",
            identity={"name": "Test Item"},
            valuation={"q50": 100.0},
            completeness_score=0.6,
        )
        d = dossier.to_dict()
        assert d["item_id"] == "test-id"
        assert d["identity"]["name"] == "Test Item"
        assert d["completeness_score"] == 0.6
        assert d["version"] == "1.0"


# ---------------------------------------------------------------------------
# generate_dossier with mocked DB
# ---------------------------------------------------------------------------


def _make_mock_conn(
    item_row=None,
    pred_row=None,
    prov_rows=None,
    ph_rows=None,
    mh_rows=None,
    pointer_rows=None,
):
    """Create a mocked asyncpg connection with configurable return values."""
    conn = AsyncMock()
    calls: list[tuple[str, tuple]] = []

    async def mock_fetchrow(sql, *args):
        calls.append((sql, args))
        sql_lower = sql.lower()
        if "public.items" in sql_lower:
            return item_row
        if "price_predictions" in sql_lower:
            return pred_row
        return None

    async def mock_fetch(sql, *args):
        calls.append((sql, args))
        sql_lower = sql.lower()
        if "item_provenance_events" in sql_lower:
            return prov_rows or []
        if "price_history" in sql_lower:
            return ph_rows or []
        if "market_hits" in sql_lower:
            return mh_rows or []
        if "object_pointers" in sql_lower:
            return pointer_rows or []
        return []

    conn.fetchrow = mock_fetchrow
    conn.fetch = mock_fetch
    # The helper routes on SQL TEXT, so it answers `price_predictions`
    # identically no matter which key was bound — which is why binding the
    # bare `canonical_key` against the namespaced `item_ref` was invisible
    # here for months. Recording every (sql, args) lets a test assert the
    # VALUE, which is the only thing that separates the two vocabularies
    # (learning_validate_values_not_just_structure).
    conn.recorded_calls = calls
    return conn


class TestGenerateDossier:
    """Tests for generate_dossier() with mocked DB."""

    @pytest.mark.asyncio
    async def test_item_not_found_raises(self):
        from app.agents.dossier_agent import generate_dossier

        conn = _make_mock_conn(item_row=None)
        with pytest.raises(ValueError, match="Item not found"):
            await generate_dossier("item-id", "user-id", conn)

    @pytest.mark.asyncio
    async def test_price_lookups_bind_the_namespaced_ref(self):
        """The identifier-format rule, enforced where it is actually broken.

        `items.canonical_key` is BARE (`base1-base1-4`);
        `price_predictions.item_ref` and `price_prediction_daily.item_ref` are
        ALWAYS namespaced (`pokemon:base1-base1-4` — 0 bare rows in 1.7M). The
        agent bound the bare key, so BOTH price lookups matched zero rows for
        every item and every user: a dossier — a Pro feature — carried no
        valuation and no 90-day chart, silently, because an empty join is a
        valid result.

        Structure could never catch this. The table, the column and the SQL
        were all correct; only the VALUE was from the wrong vocabulary.
        """
        from app.agents.dossier_agent import generate_dossier

        item_row = {
            "id": "i", "user_id": "u", "title": "T", "category": "pokemon",
            "condition": None, "attributes_json": None, "condition_grade": None,
            "canonical_key": "base1-base1-4",
            "canonical_ref": "pokemon:base1-base1-4",
            "created_at": None, "image_url": None,
            "cost_basis": None, "purchase_price": None,
            "purchase_currency": None, "purchased_at": None,
        }
        conn = _make_mock_conn(item_row=item_row)
        await generate_dossier("i", "u", conn)

        priced = [
            (sql, args) for sql, args in conn.recorded_calls
            if "item_ref = $1" in sql
        ]
        assert priced, "neither price lookup ran — the ref was never resolved"
        for sql, args in priced:
            assert args[0] == "pokemon:base1-base1-4", (
                "bound the BARE canonical_key against item_ref; this matches "
                "zero rows and returns an empty dossier rather than an error"
            )

    @pytest.mark.asyncio
    async def test_basic_dossier_generation(self):
        from app.agents.dossier_agent import generate_dossier

        item_row = {
            "id": "test-item-id",
            "user_id": "test-user-id",
            "title": "Charizard Base Set Holo",
            "category": "pokemon",
            "condition": "Near Mint",
            # `condition_grade` is the COLUMN grade lives in — the importer
            # writes it (import_router.py:249) and the exporter reads it
            # (items_export_router.py:193). This row used to carry a
            # top-level "grade", a column `items` does not have, so it
            # asserted a shape the database cannot produce. That is what hid
            # the agent reading attrs["grade"], which nothing writes.
            "condition_grade": "PSA 9",
            # BOTH keys, and they are not interchangeable: `canonical_key` is
            # bare, `canonical_ref` is namespaced, and the price lookups bind
            # the ref. The old row carried NEITHER, so `canonical_key` was
            # None, both price queries were skipped entirely, and the q50
            # assertion below could never have run — it sat behind an earlier
            # failing assertion for long enough that nobody saw it.
            "canonical_key": "base1-base1-4",
            "canonical_ref": "pokemon:base1-base1-4",
            # graded_by and sealed DO live in attrs — same split the importer
            # applies, so this row now matches one real SELECT.
            "attributes_json": '{"set": "Base Set", "rarity": "Holo Rare", '
                               '"graded_by": "PSA", "sealed": false}',
            "taxonomy_version": "v1.0",
            "subtype_id": "holo_rare",
            # `image_url` (single text column), not an `images` array —
            # `items` has no such column. The agent reads image_url and adds
            # any object_pointers rows on top.
            "image_url": "https://img.example.com/char.jpg",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 10, tzinfo=timezone.utc),
        }

        pred_row = {
            "q10": 150.0,
            "q50": 250.0,
            "q90": 400.0,
            "conf_score": 0.85,
            "explanation": "Based on 15 recent sales",
            "evidence_summary": '{"sources": [{"source": "ebay", "count": 10, "avg_price": 240.0}], "total_comps": 10}',
            "evidence_hit_ids": '["hit-1", "hit-2"]',
            "asof": datetime(2026, 1, 10, tzinfo=timezone.utc),
        }

        prov_rows = [
            {
                "id": "prov-1",
                "event_type": "purchase",
                "note": "Bought at local card shop",
                "source": "receipt",
                "metadata": None,
                "created_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
            {
                "id": "prov-2",
                "event_type": "graded",
                "note": "Sent to PSA",
                "source": "PSA",
                "metadata": '{"grade": "9"}',
                "created_at": datetime(2025, 8, 15, tzinfo=timezone.utc),
            },
        ]

        mh_rows = [
            {
                "title": "Charizard Base Set 1st Ed",
                "price": 350.0,
                "currency": "EUR",
                "provider": "ebay",
                "ended_at": datetime(2026, 1, 5, tzinfo=timezone.utc),
                "url": "https://ebay.com/itm/123",
                "condition": "Near Mint",
            },
        ]

        conn = _make_mock_conn(
            item_row=item_row,
            pred_row=pred_row,
            prov_rows=prov_rows,
            mh_rows=mh_rows,
        )

        dossier = await generate_dossier("test-item-id", "test-user-id", conn)

        assert dossier.item_id == "test-item-id"
        assert dossier.identity["name"] == "Charizard Base Set Holo"
        assert dossier.identity["category"] == "pokemon"
        assert dossier.identity["grade"] == "PSA 9"
        assert dossier.identity["graded_by"] == "PSA"
        assert dossier.identity["canonical_key"] == "base1-base1-4"
        assert dossier.valuation["q50"] == 250.0
        assert dossier.valuation["confidence_score"] == 0.85
        assert len(dossier.provenance) == 2
        assert dossier.provenance[0]["event_type"] == "purchase"
        assert len(dossier.market_comps) == 1
        assert dossier.market_comps[0]["price"] == 350.0
        assert len(dossier.photos) >= 1
        # Empty, like the dedicated collections test below: `items` has no
        # `collections` column, so the agent hardcodes []. The row used to
        # carry one and this asserted it came back — a shape the database
        # cannot produce. The real column (`collection_name`) is noted there.
        assert dossier.collections == []

        # Authenticity signals from purchase + graded + receipt
        assert "purchase_recorded" in dossier.authenticity_signals
        assert "professionally_graded" in dossier.authenticity_signals
        assert "receipt_on_file" in dossier.authenticity_signals

        # Completeness should be high (has photo, provenance, prediction, attributes, comps)
        assert dossier.completeness_score == 1.0

    @pytest.mark.asyncio
    async def test_minimal_dossier_no_extras(self):
        from app.agents.dossier_agent import generate_dossier

        item_row = {
            "id": "min-item-id",
            "user_id": "user-id",
            "title": "Unknown Item",
            "category": None,
            "condition": None,
            "grade": None,
            "graded_by": None,
            "sealed": False,
            "attributes_json": None,
            "taxonomy_version": None,
            "subtype_id": None,
            "collections": None,
            "images": None,
            "created_at": None,
            "updated_at": None,
        }

        conn = _make_mock_conn(item_row=item_row)
        dossier = await generate_dossier("min-item-id", "user-id", conn)

        assert dossier.item_id == "min-item-id"
        assert dossier.identity["name"] == "Unknown Item"
        assert dossier.valuation == {}
        assert dossier.provenance == []
        assert dossier.market_comps == []
        assert dossier.photos == []
        assert dossier.collections == []
        assert dossier.completeness_score == 0.0

    @pytest.mark.asyncio
    async def test_collections_as_list(self):
        """Test collections field when stored as a list instead of JSON string."""
        from app.agents.dossier_agent import generate_dossier

        item_row = {
            "id": "id",
            "user_id": "uid",
            "title": "Test",
            "category": "pokemon",
            "condition": None,
            "grade": None,
            "graded_by": None,
            "sealed": False,
            "attributes_json": None,
            "taxonomy_version": None,
            "subtype_id": None,
            "images": None,
            "created_at": None,
            "updated_at": None,
        }

        conn = _make_mock_conn(item_row=item_row)
        dossier = await generate_dossier("id", "uid", conn)
        # ALWAYS empty, and this pins that rather than a wish. `items` has no
        # `collections` column, so `generate_dossier` hardcodes []; the test
        # fed a column that does not exist and asserted it came back.
        #
        # ⚠️ There IS a real column it could use — `items.collection_name`
        # (singular), which `/items-export/full` already surfaces. Wiring it
        # changes what the dossier PDF prints, so it is Merle's call, not a
        # side effect of a test-triage pass. Until then the field is dead and
        # says so here.
        assert dossier.collections == []


# ---------------------------------------------------------------------------
# HTML export format
# ---------------------------------------------------------------------------


class TestDossierHtmlExport:
    """Tests for the HTML rendering in dossier_router._render_html."""

    def test_html_contains_item_name(self):
        from app.agents.dossier_agent import ItemDossier
        from app.agents.dossier_router import _render_html

        dossier = ItemDossier(
            item_id="html-test",
            generated_at="2026-01-15T12:00:00",
            identity={"name": "Charizard Holo", "category": "pokemon",
                       "condition": "NM", "grade": "PSA 9", "graded_by": "PSA",
                       "sealed": False, "attributes": {}, "image_url": None},
            valuation={"q10": 100.0, "q50": 200.0, "q90": 300.0,
                        "confidence_score": 0.8, "explanation": "Market data"},
        )
        html_output = _render_html(dossier)

        assert "Charizard Holo" in html_output
        assert "CollectAI" in html_output
        assert "<!DOCTYPE html>" in html_output
        assert "pokemon" in html_output

    def test_html_contains_valuation(self):
        from app.agents.dossier_agent import ItemDossier
        from app.agents.dossier_router import _render_html

        dossier = ItemDossier(
            item_id="val-test",
            generated_at="2026-01-15T12:00:00",
            identity={"name": "Test", "category": "funko", "condition": None,
                       "grade": None, "graded_by": None, "sealed": False,
                       "attributes": {}, "image_url": None},
            valuation={"q10": 10.0, "q50": 25.0, "q90": 50.0,
                        "confidence_score": 0.7, "explanation": None},
        )
        html_output = _render_html(dossier)
        assert "Valuation" in html_output

    def test_html_contains_provenance(self):
        from app.agents.dossier_agent import ItemDossier
        from app.agents.dossier_router import _render_html

        dossier = ItemDossier(
            item_id="prov-test",
            generated_at="2026-01-15T12:00:00",
            identity={"name": "Test", "category": "pokemon", "condition": None,
                       "grade": None, "graded_by": None, "sealed": False,
                       "attributes": {}, "image_url": None},
            provenance=[
                {"event_type": "purchase", "note": "Bought it",
                 "source": "store", "timestamp": "2025-01-01", "metadata": {}},
            ],
        )
        html_output = _render_html(dossier)
        assert "Provenance Timeline" in html_output
        assert "Purchase" in html_output

    def test_html_contains_market_comps(self):
        from app.agents.dossier_agent import ItemDossier
        from app.agents.dossier_router import _render_html

        dossier = ItemDossier(
            item_id="comp-test",
            generated_at="2026-01-15T12:00:00",
            identity={"name": "Test", "category": "pokemon", "condition": None,
                       "grade": None, "graded_by": None, "sealed": False,
                       "attributes": {}, "image_url": None},
            market_comps=[
                {"title": "Comparable Sale", "price": 99.0, "currency": "EUR",
                 "source": "ebay", "sold_date": "2026-01-10", "url": None,
                 "condition": "NM"},
            ],
        )
        html_output = _render_html(dossier)
        assert "Market Comparables" in html_output
        assert "Comparable Sale" in html_output

    def test_html_completeness_bar(self):
        from app.agents.dossier_router import _completeness_bar

        bar = _completeness_bar(0.8)
        assert "80%" in bar
        assert "#81D8D0" in bar  # Tiffany blue for high completeness

        bar_low = _completeness_bar(0.2)
        assert "20%" in bar_low
        assert "#EF4444" in bar_low  # Red for low completeness

    def test_html_escapes_special_chars(self):
        from app.agents.dossier_agent import ItemDossier
        from app.agents.dossier_router import _render_html

        dossier = ItemDossier(
            item_id="xss-test",
            generated_at="2026-01-15T12:00:00",
            identity={"name": '<script>alert("xss")</script>', "category": "test",
                       "condition": None, "grade": None, "graded_by": None,
                       "sealed": False, "attributes": {}, "image_url": None},
        )
        html_output = _render_html(dossier)
        # The script tag should be escaped, not present raw
        assert "<script>" not in html_output
        assert "&lt;script&gt;" in html_output
