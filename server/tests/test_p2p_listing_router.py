"""Tests for app/features/p2p_listing_router.py — member-to-member listings.

These exist because four real bugs were found by hand-testing this router
against prod, and every one of them was a *contract* mismatch that a test
would have caught immediately:

  1. `marketplace_listings.marketplace_id` is TEXT (a key like 'ebay'), NOT an
     FK to marketplaces.id — passing the numeric id raised
     "expected str, got int".
  2. CHECK constraints narrower than the code: format must be 'fixed_price'
     (not 'fixed') and 'withdrawn' is not a legal status ('delisted' is).
  3. `ON CONFLICT DO NOTHING` on market_hits can never fire (its only unique
     key is (id, seen_at), id from a sequence), so a republish wrote a SECOND
     buyable row.
  4. The delist supply-hook was fire-and-forget, so a sold listing stayed
     buyable.

So these tests deliberately pin the *contract constants* and the *hook
semantics*, not just happy-path plumbing. Per
learning_tests_that_pin_a_stub, they assert real behaviour — the source-level
checks below verify guards exist rather than asserting a stubbed return.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")

from app.features import p2p_listing_router as p2p  # noqa: E402


def _code_only(src: str) -> str:
    """Strip Python (#) and SQL (--) comment lines from source.

    Needed because these tests assert on the SQL/code, and the module is
    heavily commented — including SQL comments INSIDE the query strings
    (e.g. "-- WHERE NOT EXISTS, not ON CONFLICT: ..."). A naive substring grep
    matches the explanation and fails on correct code, which is exactly what
    happened when these tests were first written.
    """
    out = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("--"):
            continue
        out.append(line)
    return "\n".join(out)



class TestStatusAndFormatContract:
    """The DB CHECK constraints are narrower than plain English."""

    def test_status_constants_are_legal_values(self):
        # marketplace_listings_status_check allows exactly:
        #   draft | active | sold | expired | delisted | error
        legal = {"draft", "active", "sold", "expired", "delisted", "error"}
        assert p2p._STATUS_ACTIVE in legal
        assert p2p._STATUS_SOLD in legal
        assert p2p._STATUS_DELISTED in legal

    def test_withdrawn_is_not_used(self):
        """'withdrawn' reads naturally and is NOT a legal status."""
        import inspect
        src = _code_only(inspect.getsource(p2p))
        assert '"withdrawn"' not in src
        assert "'withdrawn'" not in src

    def test_format_is_fixed_price_not_fixed(self):
        # marketplace_listings_format_check: fixed_price | auction | best_offer
        assert p2p._FORMAT_FIXED == "fixed_price"

    def test_marketplace_key_is_a_string_not_an_id(self):
        """marketplace_id is TEXT. Passing marketplaces.id (bigint) fails."""
        assert isinstance(p2p.SPARROW_MARKETPLACE_KEY, str)
        assert p2p.SPARROW_MARKETPLACE_KEY == "sparrow"


class TestSupplyHookSemantics:
    """The supply hook is the reason this feature exists."""

    def test_publish_uses_where_not_exists_not_on_conflict(self):
        """ON CONFLICT can never fire on market_hits — see module docstring."""
        import inspect
        src = _code_only(inspect.getsource(p2p._publish_supply_hook))
        assert "WHERE NOT EXISTS" in src
        assert "ON CONFLICT" not in src

    def test_publish_marks_row_buyable(self):
        """The snipe requires url IS NOT NULL AND is_listing IS TRUE."""
        import inspect
        src = inspect.getsource(p2p._publish_supply_hook)
        assert "is_listing" in src
        assert "TRUE" in src
        assert "https://sparrowcollect.com/l/" in src

    def test_publish_namespaces_item_ref(self):
        """items.canonical_key is BARE; market_hits.item_ref is NAMESPACED."""
        import inspect
        src = inspect.getsource(p2p._publish_supply_hook)
        assert "{row['category']}:{row['canonical_key']}" in src

    def test_publish_skips_without_canonical_identity(self):
        """A weakly-identified buyable row is what caused false positives."""
        import inspect
        src = inspect.getsource(p2p._publish_supply_hook)
        assert 'not row["canonical_key"]' in src

    def test_delist_awaits_the_stale_hook(self):
        """A lingering row sends a buyer to something already sold.

        Publish may be fire-and-forget (a missing row is a non-event); delist
        must NOT be. This asymmetry was a real bug — the end-to-end test caught
        the market_hits row surviving a sale.
        """
        import inspect
        src = inspect.getsource(p2p.delist)
        assert "await _stale_supply_hook" in src
        assert "spawn_bg(_stale_supply_hook" not in src

    def test_publish_is_fire_and_forget(self):
        """...and publish deliberately is NOT awaited, via spawn_bg."""
        import inspect
        src = inspect.getsource(p2p.create_listing)
        assert "spawn_bg(_publish_supply_hook" in src


class TestReportCounter:
    def test_counter_only_moves_on_a_new_report(self):
        """Re-reporting must not inflate reports_count and poison triage."""
        import inspect
        src = inspect.getsource(p2p.report_listing)
        assert "RETURNING id" in src
        assert "if inserted is not None:" in src


class TestOwnershipAndRoutes:
    def test_create_enforces_ownership_server_side(self):
        import inspect
        src = inspect.getsource(p2p.create_listing)
        assert "user_id = $2::uuid" in src
        assert "ITEM_NOT_FOUND" in src

    def test_deep_link_target_endpoint_exists(self):
        """market_hits.url points at /l/<id>; something must resolve it."""
        paths = {r.path for r in p2p.router.routes}
        assert "/p2p/listings/{listing_id}" in paths

    def test_all_stage1_routes_registered(self):
        paths = {r.path for r in p2p.router.routes}
        assert "/p2p/listings" in paths
        assert "/p2p/listings/{listing_id}/delist" in paths
        assert "/p2p/listings/{listing_id}/report" in paths

    def test_no_payment_endpoints_in_stage1(self):
        """Stage 1 never touches funds — that is what keeps PSD2 out of scope."""
        paths = " ".join(r.path for r in p2p.router.routes)
        for banned in ("checkout", "payment", "pay", "escrow", "payout"):
            assert banned not in paths
