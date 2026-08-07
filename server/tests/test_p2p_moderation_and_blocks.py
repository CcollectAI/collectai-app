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


# ── 3. The supply hook's skip must be visible ───────────────────────────────
#
# Found 2026-08-07 by walking the marketplace end-to-end with real user tokens:
# publishing a listing wrote NO market_hits row. The skip is deliberate — a
# listing with no canonical identity could only match Target Hit's fuzzy title
# arm, where the false positives live — and the hook itself is healthy (a
# listing WITH an identity writes `mtg:sum-283-bayou` correctly). What was
# missing was visibility:
#   * the seller got a listing that can never fire an alert and was not told;
#   * §6's go/no-go metric counts the skip as "no supply", which is the wrong
#     number to cancel Stage 2/3 on.
# Only 4 of 16 `items` carry a canonical_key, so this is the majority case.
#
# NOTE the log line was never actually missing — `collectai-bake.service` writes
# StandardOutput to /opt/collectors/bake.log, not journald, so `journalctl`
# shows none of it and looks like silence. It was at INFO in a 90MB INFO log;
# WARNING makes a coverage gap greppable at its real severity.

def test_reaches_target_hit_matches_the_hook_precondition():
    """The flag and the guard must be the SAME rule.

    If they drift, the API tells a seller their listing reaches Target Hit
    while the hook silently skips it — a worse failure than the original
    silence, because now it is a false promise.
    """
    guard_src = _code_only(inspect.getsource(listings._publish_supply_hook))
    assert "_reaches_target_hit(" in guard_src, (
        "the hook no longer uses the shared predicate — the flag can now lie"
    )


@pytest.mark.parametrize("canonical_key,category,expected", [
    ("sm10-sm10-101", "pokemon", True),
    (None,            "pokemon", False),
    ("sm10-sm10-101", None,      False),
    (None,            None,      False),
    ("",              "pokemon", False),   # empty string is not an identity
    ("sm10-sm10-101", "",        False),
])
def test_reaches_target_hit_predicate(canonical_key, category, expected):
    assert listings._reaches_target_hit(canonical_key, category) is expected


def test_every_listing_response_carries_the_flag():
    """All three ListingOut construction sites, not two of three — the same
    drift that left create_offer's RETURNING behind."""
    src = _code_only(inspect.getsource(listings))
    built = src.count("is_mine=")
    flagged = src.count("reaches_target_hit=_reaches_target_hit(")
    assert flagged == built, (
        f"{built} ListingOut construction sites but only {flagged} set "
        f"reaches_target_hit — a listing would default to False and wrongly "
        f"warn the seller"
    )


def test_skip_is_logged_loudly_enough_to_see():
    """A coverage gap that silently defeats the feature's purpose is not INFO.

    bake.log is ~90MB and almost entirely INFO, so an INFO line is written and
    unread. WARNING is the level at which "this listing can never fire an
    alert" is greppable.
    """
    src = _code_only(inspect.getsource(listings._publish_supply_hook))
    skip_block = src.split("_reaches_target_hit(", 1)[1].split("return", 1)[0]
    assert "logger.warning" in skip_block, "the skip must not be logged at INFO"
    assert "logger.info" not in skip_block


# ── 4. The closed loop: a completed trade becomes a sold comp ───────────────
#
# Until 2026-08-07 completion deleted the buyable row and recorded NOTHING about
# the price the item actually sold for. `valuation_worker` selects
# `WHERE is_listing IS NOT TRUE` — it consumes sold data and ignores asking
# prices — while every row P2P wrote was `is_listing = TRUE`. So the single
# highest-quality datum the marketplace produces (a two-sided-confirmed sale at
# a known price) fed nothing, while ~62k catalogue items have no price at all
# precisely because `ebay_caller.sold_comps()` returns [].

def test_completion_writes_a_sold_comp():
    from app.features import p2p_offers_router as offers_mod
    src = _code_only(inspect.getsource(offers_mod.confirm_exchange))
    assert "_sold_comp_hook" in src, "completion does not record the sale"


def test_sold_comp_is_awaited_not_fire_and_forget():
    """A lost buyable row is a non-event; a lost sale cannot be reconstructed."""
    from app.features import p2p_offers_router as offers_mod
    src = _code_only(inspect.getsource(offers_mod.confirm_exchange))
    assert "await _sold_comp_hook" in src
    assert "spawn_bg(_sold_comp_hook" not in src


def test_sold_comp_is_not_a_listing_row():
    """`is_listing = FALSE` is the whole point — TRUE would make it look like
    supply and valuation_worker would skip it, which is the bug being fixed.

    Asserts on the VALUES tail of the INSERT specifically. A looser grep over
    the function body matches the docstring, which discusses both spellings —
    the test passed on the prose and would have passed on wrong SQL.
    """
    src = inspect.getsource(listings._sold_comp_hook)
    assert "now(), now(), FALSE" in src, "sold comp must be is_listing = FALSE"
    assert "now(), now(), TRUE" not in src, "that is the publish hook's row shape"
    # And the publish hook still writes the opposite, so the two are distinct.
    assert "now(), now(), TRUE" in inspect.getsource(listings._publish_supply_hook)


def test_sold_comp_uses_the_agreed_amount_not_the_asking_price():
    """After a counter, `p2p_offers.amount` is what was paid;
    `marketplace_listings.price` is what was hoped for. Storing the ask as a
    sale biases every prediction upward."""
    from app.features import p2p_offers_router as offers_mod
    call = _code_only(inspect.getsource(offers_mod.confirm_exchange))
    assert 'fresh["amount"]' in call
    hook = _code_only(inspect.getsource(listings._sold_comp_hook))
    assert "l.price" not in hook and "row[\"price\"]" not in hook


def test_sold_comp_is_idempotent():
    """market_hits has no usable unique key, so a re-confirm would otherwise
    write a second sale — the same trap the publish hook hit with ON CONFLICT."""
    src = _code_only(inspect.getsource(listings._sold_comp_hook))
    assert "WHERE NOT EXISTS" in src


def test_sold_comp_is_tagged_with_its_own_source():
    """Separable forever: the lever to exclude P2P prices from valuation if they
    prove unreliable, and the way to measure the marketplace's contribution."""
    assert listings.SPARROW_SOLD_SOURCE == "sparrow_p2p"
    src = _code_only(inspect.getsource(listings._sold_comp_hook))
    assert "SPARROW_SOLD_SOURCE" in src


def test_sold_comp_requires_a_canonical_identity():
    """No canonical identity means no item_ref, and valuation_worker requires
    one — the row would be inert. Same predicate as the publish hook."""
    src = _code_only(inspect.getsource(listings._sold_comp_hook))
    assert "_reaches_target_hit(" in src


# ── 5. Marketplace-only sellers, and photos enriching the catalogue ─────────
#
# Two gaps Merle named on 2026-08-07:
#   * `item_id` was required and the only entry point is the item-detail
#     screen, so a marketplace-only seller had to build a collection they did
#     not want before they could sell one thing.
#   * The create flow captured NO photo, so the catalogue's 54,115 missing
#     images could never be filled by the people holding the actual objects.

def test_listing_can_be_created_without_a_collection_item():
    fields = listings.ListingCreate.model_fields
    assert fields["item_id"].is_required() is False
    assert "title" in fields, "no free-text path for a marketplace-only seller"


def test_free_text_listing_requires_a_title():
    """Neither an item nor a title is not a listing, and must fail loudly
    rather than create an untitled row."""
    src = _code_only(inspect.getsource(listings.create_listing))
    assert "ITEM_OR_TITLE_REQUIRED" in src


def test_auto_created_item_is_tagged_and_not_archived():
    """`source='marketplace'` makes these separable from collection adds.
    Archiving would read as 'the app archived my thing' — archive is a user
    action everywhere else."""
    src = _code_only(inspect.getsource(listings.create_listing))
    assert "'marketplace'" in src
    assert "archived" not in src


def test_listing_keys_off_the_resolved_item_not_the_payload():
    """On the free-text path `payload.item_id` is None. Any query still using
    it would silently key on NULL — the dup check would never fire and the
    listing would be written with a null item_id, breaking every hook."""
    src = _code_only(inspect.getsource(listings.create_listing))
    after_resolve = src.split("ITEM_NOT_FOUND", 1)[1]
    assert "payload.item_id" not in after_resolve, (
        "create_listing still keys on the payload after resolving the item"
    )


def test_catalogue_consent_defaults_to_off():
    """Absence of a choice is not consent — defaulted in the model AND the
    column, so a client that omits the field cannot opt a user in."""
    assert listings.ListingCreate.model_fields["photo_catalogue_consent"].default is False


def test_catalogue_hook_only_fills_gaps_and_never_overwrites():
    """The whole safety story. Overwriting could displace a licensed asset with
    a photo of one member's copy."""
    src = _code_only(inspect.getsource(listings._catalogue_image_hook))
    assert "image_url IS NULL" in src, "hook could overwrite an existing catalogue image"


def test_catalogue_hook_requires_consent_and_a_real_seller_photo():
    src = _code_only(inspect.getsource(listings._catalogue_image_hook))
    assert "photo_catalogue_consent IS TRUE" in src
    # i.image_url, not the COALESCE fallback: copying the catalogue image back
    # into the catalogue is a no-op that looks like progress.
    assert "i.image_url IS NOT NULL" in src


def test_catalogue_contribution_records_provenance():
    """'Stop using my photo' is unanswerable without this."""
    src = _code_only(inspect.getsource(listings._catalogue_image_hook))
    for col in ("image_source", "image_contributed_by", "image_contributed_at"):
        assert col in src


def test_the_grant_is_actually_revocable():
    """ToS §3 promises revocation. Without a code path that is a promise we
    cannot keep."""
    src = _code_only(inspect.getsource(listings.withdraw_contributed_images))
    assert "image_contributed_by = $1" in src
    assert "image_url = NULL" in src


def test_catalogue_enrichment_never_blocks_publishing():
    """Enrichment is not a feature of the listing. It must not be able to fail
    a seller's publish."""
    src = _code_only(inspect.getsource(listings.create_listing))
    assert "spawn_bg(_catalogue_image_hook" in src
    assert "await _catalogue_image_hook" not in src


# ── 6. Promises the documents make that the code must actually keep ─────────
#
# Both were written into user-facing documents before the code did them, which
# is the worst kind of gap: a term someone relied on that cannot be exercised.

def test_catalogue_consent_is_actually_revocable_by_a_user():
    """ToS §3: "you can withdraw it at any time". `withdraw_contributed_images`
    existed and was tested, and NOTHING called it — so no user could."""
    paths = {r.path for r in listings.router.routes}
    assert "/p2p/catalogue-contributions" in paths
    src = _code_only(inspect.getsource(listings.withdraw_my_catalogue_photos))
    assert "withdraw_contributed_images" in src


def test_withdrawal_also_clears_consent_so_it_stays_withdrawn():
    """Clearing the images but leaving the flag means the next photo upload
    re-contributes — the withdrawal would silently undo itself."""
    src = _code_only(inspect.getsource(listings.withdraw_my_catalogue_photos))
    assert "photo_catalogue_consent = FALSE" in src
    assert "conn.transaction()" in src, "flag and images must clear together"


def test_a_new_report_pages_the_operator():
    """Marketplace Terms §5 and Acceptable Use §9 both promise action "within
    24 hours". Sparrow is one person; a queue nobody is told about is not a
    commitment."""
    src = _code_only(inspect.getsource(listings.report_listing))
    assert "_page_ops_new_report" in src


def test_only_new_reports_page_so_re_reports_cannot_spam_ops():
    """Asserts ADJACENCY, not "the guard appears somewhere above".

    The first version split on the function name and checked the text before
    it contained `if inserted is not None:` — which it always does, because the
    reports_count update earlier in the function is guarded the same way. It
    passed with the paging guard removed entirely. A gate with a false negative
    is worse than no gate.
    """
    src = _code_only(inspect.getsource(listings.report_listing))
    normalised = "\n".join(line.rstrip() for line in src.splitlines())
    assert "if inserted is not None:\n        spawn_bg(_page_ops_new_report" in normalised, (
        "the paging call is not directly guarded by the new-report check"
    )


def test_paging_cannot_fail_the_members_report():
    """The row is already committed. A Telegram outage must not surface to the
    member as a failed report."""
    src = _code_only(inspect.getsource(listings.report_listing))
    assert "spawn_bg(_page_ops_new_report" in src
    assert "await _page_ops_new_report" not in src
    page = _code_only(inspect.getsource(listings._page_ops_new_report))
    assert "except Exception" in page


def test_objectionable_content_is_filtered_before_publishing():
    """Apple Guideline 1.2's fourth limb. Checked at the one write path, before
    the item is created, so a rejected listing leaves nothing behind."""
    src = _code_only(inspect.getsource(listings.create_listing))
    assert "find_blocked_term" in src
    assert "OBJECTIONABLE_CONTENT" in src
    before_create = src.split("INSERT INTO public.items", 1)[0]
    assert "find_blocked_term" in before_create, "filter must run before the item is created"
