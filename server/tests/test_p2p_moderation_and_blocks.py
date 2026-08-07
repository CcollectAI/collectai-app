"""Blocking across the marketplace, and DSA moderation.

Two gaps found by researching what marketplace regulation and App Review
actually require (2026-08-07), both of the "storage exists, nothing uses it"
shape this codebase keeps producing:

  1. **Blocking stopped at chat.** `user_blocks` was enforced in exactly one
     place (`chat_router._check_not_blocked`). The P2P marketplace shipped with
     none, so a blocked member's listings still appeared and they could still
     send offers. Apple App Review Guideline 1.2 asks for the ability to block
     abusive users *from the service*, not from one screen.

  2. **DSA Art 17 was unbuilt.** `listing_reports` has carried `status`,
     `resolution_note` and `resolved_at` since Stage 1 and nothing ever wrote
     them; the seller was never told a decision had been made. Art 17 sits in
     Section 2 of the DSA, so the Art 19 micro-enterprise exclusion (which only
     reaches Section 3, Arts 20-28) does not cover it at any size.

These tests pin the CONTRACT, not the plumbing: that every surface consults the
shared block helper, and that a statement of reasons carries the elements
Art 17(3) enumerates.
"""
import inspect
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")

from app.features import p2p_listing_router as listings  # noqa: E402
from app.features import p2p_offers_router as offers  # noqa: E402
from app.lib import blocks  # noqa: E402


def _code_only(src: str) -> str:
    """Strip Python (#) and SQL (--) comment lines.

    These modules explain themselves heavily, including inside SQL strings, so a
    naive substring match would pass on the prose while the code was wrong —
    the same reason test_p2p_listing_router.py carries this helper.
    """
    return "\n".join(
        line for line in src.splitlines()
        if not line.strip().startswith("#") and not line.strip().startswith("--")
    )


# ── 1. Blocking reaches every marketplace surface ───────────────────────────

def test_block_helper_is_symmetric_by_construction():
    """Both directions in one query. A one-directional check would let the
    blocked party keep watching the blocker, which is the thing blocking
    exists to prevent."""
    src = _code_only(inspect.getsource(blocks.is_blocked))
    assert "blocker_id = $1" in src and "blocked_id = $2" in src
    assert "blocker_id = $2" in src and "blocked_id = $1" in src


def test_blocked_user_ids_returns_both_directions():
    src = _code_only(inspect.getsource(blocks.blocked_user_ids))
    assert "UNION" in src, "must union blocks made AND blocks received"


def test_anonymous_caller_gets_no_blocks_rather_than_a_null_filter():
    """An anon browse must see everything, not nothing. Passing NULL into
    `= ANY($1::uuid[])` matches nothing and would silently empty the grid."""
    src = _code_only(inspect.getsource(blocks.blocked_user_ids))
    assert "return []" in src


def test_browse_listings_filters_blocked_sellers():
    src = _code_only(inspect.getsource(listings.browse_listings))
    assert "blocked_user_ids" in src, "browse does not consult the block list"
    assert "l.user_id = ANY" in src, "block list is fetched but not applied to the query"


def test_listing_detail_hides_a_blocked_sellers_listing():
    """The deep-link path matters more than browse: Target Hit URLs and shared
    links bypass the grid entirely."""
    src = _code_only(inspect.getsource(listings.get_listing))
    assert "is_blocked" in src


def test_listing_detail_uses_404_not_403_for_a_block():
    """A distinct status would confirm the listing exists to the blocked party."""
    src = _code_only(inspect.getsource(listings.get_listing))
    assert "LISTING_NOT_FOUND" in src
    assert "USER_BLOCKED" not in src, "must not leak that a block is the reason"


def test_create_offer_rejects_a_blocked_pair():
    """An offer creates a notification and a row on the other member's Offers
    screen — exactly the contact blocking is meant to stop."""
    src = _code_only(inspect.getsource(offers.create_offer))
    assert "raise_if_blocked" in src


def test_chat_delegates_to_the_shared_helper_rather_than_a_private_copy():
    """The duplicate is how one surface got the fix and the others did not."""
    from app.features import chat_router
    src = _code_only(inspect.getsource(chat_router._check_not_blocked))
    assert "is_blocked" in src
    assert "SELECT 1 FROM user_blocks" not in src, "private copy is back"


# ── 2. DSA Art 17 statement of reasons ──────────────────────────────────────

def test_statement_names_the_decision_and_the_listing():
    s = listings._compose_statement("Charizard Base Set", True, "counterfeit", None)
    assert "Charizard Base Set" in s
    assert "removed" in s


def test_statement_distinguishes_removal_from_dismissal():
    removed = listings._compose_statement("X", True, "terms_breach", None)
    kept = listings._compose_statement("X", False, "terms_breach", None)
    assert removed != kept
    assert "left online" in kept


def test_statement_states_the_ground_in_words_not_a_code():
    s = listings._compose_statement("X", True, "counterfeit", None)
    assert listings._MODERATION_GROUNDS["counterfeit"] in s
    assert "counterfeit" in s


def test_statement_declares_no_automated_means():
    """Art 17(3)(b). True only while every decision is a human calling the
    endpoint — add automated moderation and this must change with it."""
    s = listings._compose_statement("X", True, "illegal_content", None)
    assert "not automatically" in s


def test_statement_offers_redress():
    """Art 17(3)(f)."""
    s = listings._compose_statement("X", True, "illegal_content", None)
    assert "reviewed again" in s


def test_operator_explanation_is_included_when_given():
    s = listings._compose_statement("X", True, "misleading", "Photo is of a different card")
    assert "Photo is of a different card" in s


def test_every_ground_composes_without_raising():
    for g in listings._MODERATION_GROUNDS:
        assert listings._compose_statement("X", True, g, None)


def test_unknown_ground_is_rejected_by_the_endpoint():
    src = _code_only(inspect.getsource(listings.action_listing_reports))
    assert "_MODERATION_GROUNDS" in src and "UNKNOWN_GROUND" in src


def test_takedown_and_notification_share_one_transaction():
    """If the seller cannot be told, the removal must not stand. A listing
    removed with the seller un-notified is the Art 17 breach itself."""
    src = _code_only(inspect.getsource(listings.action_listing_reports))
    assert "conn.transaction()" in src
    txn = src.split("conn.transaction()", 1)[1]
    assert "notification_history" in txn, "notification is outside the transaction"
    assert "delisted" in txn, "takedown is outside the transaction"


def test_removal_awaits_the_supply_hook():
    """A removed listing keeping its buyable market_hits row would fire Target
    Hits at content we just took down — the Stage 1 delist bug, again."""
    src = _code_only(inspect.getsource(listings.action_listing_reports))
    assert "await _stale_supply_hook" in src
    assert "spawn_bg(_stale_supply_hook" not in src, "must not be fire-and-forget"


def test_moderation_endpoints_are_ops_key_not_jwt():
    for fn in (listings.list_open_reports, listings.action_listing_reports):
        src = _code_only(inspect.getsource(fn))
        assert "require_ops_key" in src
        assert "get_current_user_id" not in src


def test_ops_routes_are_not_nested_under_the_p2p_prefix():
    """Operators look under /ops. /p2p/ops/... would be a second convention."""
    paths = {r.path for r in listings.ops_router.routes}
    assert "/ops/listing-reports" in paths
    assert not any(p.startswith("/p2p") for p in paths)


def test_moderation_queue_is_oldest_first():
    """Art 16 asks for timely handling; newest-first starves the oldest
    complaint (learning_per_category_fairness_in_select_queues)."""
    src = _code_only(inspect.getsource(listings.list_open_reports))
    assert "ORDER BY min(r.created_at) ASC" in src
