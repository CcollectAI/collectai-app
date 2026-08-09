"""Tests for app/features/p2p_offers_router.py — offers, tracking, completion.

Written alongside the tracking feature (2026-08-07). Two things are pinned:

  1. **Every query feeding `_row_to_offer` must carry the tracking columns.**
     The serializer reads them unconditionally, so a query that omits them is a
     `KeyError` — a 500, on that path only. This actually happened while
     building the feature: three SELECTs were centralised into `_OFFER_COLUMNS`
     but `create_offer`'s `RETURNING` cannot use it (that list is alias-
     qualified `o.`), so the primary Stage 2 entry point was left broken.
     Exactly learning_duplicate_impl_silently_drops_the_fix.

  2. **Tracking is display-only.** Nothing may derive completion from a carrier.
     `set_tracking` must not write `status`, `seller_confirmed_at` or
     `buyer_confirmed_at` — see docs/P2P_MARKETPLACE_SPEC.md §5b. Auto-
     completing on "delivered" substitutes our judgment for the buyer's and we
     would own the outcome when the box arrives empty.

Per learning_verify_the_display_seam_not_isolated_units, test 1 below PROVES
the failure first (a row without the columns really does raise) rather than
only asserting the fixed state.
"""
import inspect
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")

from app.features import p2p_offers_router as p2p  # noqa: E402

TRACKING_COLUMNS = ("tracking_carrier", "tracking_code", "tracking_set_at")


def _code_only(src: str) -> str:
    """Strip Python (#) and SQL (--) comment lines.

    The module is heavily commented, including SQL comments INSIDE query
    strings — `create_offer`'s RETURNING carries a `-- ...` note naming the
    very columns these tests grep for. A naive substring match would pass on
    the explanation while the SQL itself was wrong, which is the failure mode
    the same helper in test_p2p_listing_router.py was written for.
    """
    out = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("--"):
            continue
        out.append(line)
    return "\n".join(out)


def _row(**overrides):
    """A row shaped like every query that feeds _row_to_offer."""
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "listing_id": "22222222-2222-2222-2222-222222222222",
        "listing_title": "Charizard",
        "buyer_id": "33333333-3333-3333-3333-333333333333",
        "seller_id": "44444444-4444-4444-4444-444444444444",
        "amount": 40.0,
        "currency": "EUR",
        "status": "accepted",
        "message": None,
        "counter_count": 0,
        "created_at": None,
        "seller_confirmed_at": None,
        "buyer_confirmed_at": None,
        "tracking_carrier": None,
        "tracking_code": None,
        "tracking_set_at": None,
    }
    base.update(overrides)
    return base


# ── 1. Every _row_to_offer feeder carries the tracking columns ──────────────

def test_row_to_offer_really_breaks_without_tracking_columns():
    """PROVE the hazard, so the greps below are guarding something real."""
    incomplete = _row()
    for col in TRACKING_COLUMNS:
        del incomplete[col]
    with pytest.raises(KeyError):
        p2p._row_to_offer(incomplete, incomplete["seller_id"])


def test_offer_columns_constant_carries_tracking():
    for col in TRACKING_COLUMNS:
        assert f"o.{col}" in p2p._OFFER_COLUMNS, f"_OFFER_COLUMNS missing {col}"


def test_create_offer_returning_carries_tracking():
    """The one query that cannot use _OFFER_COLUMNS, so the one that drifts."""
    src = _code_only(inspect.getsource(p2p.create_offer))
    assert "RETURNING" in src
    for col in TRACKING_COLUMNS:
        assert col in src, (
            f"create_offer RETURNING is missing {col}; _row_to_offer will "
            f"KeyError on every offer creation"
        )


def test_every_p2p_offers_query_feeding_the_serializer_has_tracking():
    """Sweep the module rather than trusting the three call sites we know of.

    Any SELECT/RETURNING against p2p_offers that reaches _row_to_offer must
    carry the columns. `SELECT *` and the narrow guard queries (which do not
    reach the serializer) are excluded explicitly.
    """
    src = _code_only(inspect.getsource(p2p))
    offenders = []
    seen_centralised = 0
    for chunk in src.split("await conn."):
        if "p2p_offers" not in chunk:
            continue
        # Interpolates the shared list — its contents are pinned by
        # test_offer_columns_constant_carries_tracking, so it is correct by
        # construction and adding a column there fixes every one of these.
        if "_OFFER_COLUMNS" in chunk:
            seen_centralised += 1
            continue
        # SELECT * / o.* carry every column already; the narrow guard queries
        # (SELECT 1, SELECT seller_id …) never reach the serializer.
        if "SELECT *" in chunk or "SELECT o.*" in chunk or "RETURNING" not in chunk:
            continue
        if not all(c in chunk for c in TRACKING_COLUMNS):
            offenders.append(chunk.strip()[:120])
    assert not offenders, f"queries missing tracking columns: {offenders}"
    # Guard the guard: if the constant stops being used the loop above would
    # silently have nothing to skip and this test would pass vacuously.
    assert seen_centralised >= 3, (
        f"expected the shared column list in >=3 queries, saw {seen_centralised}"
    )


# ── 2. Tracking is display-only ─────────────────────────────────────────────

def test_set_tracking_never_writes_completion_state():
    """The invariant the whole design rests on. See spec §5b."""
    src = _code_only(inspect.getsource(p2p.set_tracking))
    for forbidden in ("status =", "status=",
                      "seller_confirmed_at =", "seller_confirmed_at=",
                      "buyer_confirmed_at =", "buyer_confirmed_at="):
        assert forbidden not in src, (
            f"set_tracking writes {forbidden!r} — tracking must never advance "
            f"the trade; confirm_exchange is the only completion writer"
        )


def test_set_tracking_is_seller_only_and_state_gated():
    src = _code_only(inspect.getsource(p2p.set_tracking))
    assert "NOT_THE_SELLER" in src
    assert "NOT_EXCHANGEABLE" in src


def test_can_add_tracking_is_seller_only():
    seller = _row()["seller_id"]
    buyer = _row()["buyer_id"]
    assert p2p._row_to_offer(_row(), seller).can_add_tracking is True
    assert p2p._row_to_offer(_row(), buyer).can_add_tracking is False


@pytest.mark.parametrize("status,expected", [
    ("accepted", True), ("shipped", True),
    ("pending", False), ("completed", False), ("cancelled", False),
])
def test_can_add_tracking_only_while_live(status, expected):
    seller = _row()["seller_id"]
    out = p2p._row_to_offer(_row(status=status), seller)
    assert out.can_add_tracking is expected


# ── 3. Carrier registry — no dead buttons ───────────────────────────────────

def test_linkable_carrier_resolves_to_a_url():
    url = p2p._tracking_url("ups", "1Z999AA10123456784")
    assert url and url.startswith("https://") and "1Z999AA10123456784" in url


@pytest.mark.parametrize("carrier", ["postnl", "dpd", "gls", "bpost", "other"])
def test_postcode_carriers_return_no_link_rather_than_a_broken_one(carrier):
    """PostNL and DPD need the recipient's postcode, which we deliberately do
    not hold. An absent link is honest; a 404 is the dead-button failure Stage 1
    bug 0 was fixed to avoid."""
    assert p2p._tracking_url(carrier, "3STBJG123456789") is None


def test_unknown_carrier_degrades_instead_of_raising():
    assert p2p._tracking_url("carrier-added-later", "ABC123") is None
    # Label falls back to the raw key so the buyer still sees something.
    assert p2p._carrier_label("carrier-added-later") == "carrier-added-later"


def test_tracking_url_is_none_without_a_code():
    assert p2p._tracking_url("ups", None) is None
    assert p2p._tracking_url(None, "ABC123") is None


def test_tracking_code_is_url_encoded():
    """The code reaches the URL as a query value; separators must not escape it."""
    url = p2p._tracking_url("ups", "AB 12/34")
    assert " " not in url and "/34" not in url


def test_every_registry_template_is_https_and_takes_the_code():
    for key, (label, template) in p2p._CARRIER_TRACKING.items():
        assert label, f"{key} has no display label"
        if template is not None:
            assert template.startswith("https://"), f"{key} template is not https"
            assert "{code}" in template, f"{key} template ignores the code"


def test_tracking_code_validation_rejects_junk():
    from pydantic import ValidationError
    for bad in ["", "ab", "x" * 65, "<script>", "'; DROP TABLE", "   ", "A.B#C"]:
        with pytest.raises(ValidationError):
            p2p.TrackingIn(tracking_carrier="ups", tracking_code=bad)
    assert p2p.TrackingIn(
        tracking_carrier="ups", tracking_code="3STBJG123456789"
    ).tracking_code == "3STBJG123456789"


@pytest.mark.parametrize("raw", ["  3STBJG123  ", " 3STBJG123", "3STBJG123 ", "3STBJG123"])
def test_pasted_whitespace_is_trimmed_not_rejected(raw):
    """A leading space used to 422 with "string does not match regex" while a
    trailing one was silently accepted — two ends of the same paste failing
    differently, over a character the seller cannot see. Both are trimmed now."""
    assert p2p.TrackingIn(
        tracking_carrier="ups", tracking_code=raw
    ).tracking_code == "3STBJG123"


def test_carrier_key_charset_rejects_junk_but_allows_unknown_keys():
    from pydantic import ValidationError
    # An unknown key must still be ACCEPTED — it degrades to a copyable code
    # with no link, which beats a 422 the seller cannot act on.
    assert p2p.TrackingIn(
        tracking_carrier="carrier-added-later", tracking_code="ABC123"
    ).tracking_carrier == "carrier-added-later"
    for bad in ["", "   ", "UPS", "_leading", "a" * 41, "../etc"]:
        with pytest.raises(ValidationError):
            p2p.TrackingIn(tracking_carrier=bad, tracking_code="ABC123")


def test_every_registry_key_passes_its_own_validator():
    """A key in _CARRIER_TRACKING that the model would reject is a carrier the
    picker offers and the endpoint then refuses — a dead option."""
    for key in p2p._CARRIER_TRACKING:
        p2p.TrackingIn(tracking_carrier=key, tracking_code="ABC123")


def test_carrier_length_caps_match_the_db_constraint():
    """These MUST match p2p_offers_tracking_len_check in
    server/migrations/20260807_p2p_offer_tracking.sql — a guard narrower or
    wider than the constraint is learning_guard_must_match_constraint_type_space.
    """
    fields = p2p.TrackingIn.model_fields
    assert any(getattr(m, "max_length", None) == 40
               for m in fields["tracking_carrier"].metadata)
    assert any(getattr(m, "max_length", None) == 64
               for m in fields["tracking_code"].metadata)
