"""A keyed mandate must not accept a DIFFERENT card that shares its name.

Walked 2026-09-24: a mandate keyed to SVP #161 "Charizard ex" passed Paldean
Fates #054 and Obsidian Flames #125 as deals — 4 of its 6 "deals" were other
cards, because the search query is the name and names repeat.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.policy_engine import evaluate  # noqa: E402

MANDATE = {"max_price": 30, "min_trust_score": 0.6, "allowed_sources": ["ebay"],
           "canonical_ref": "pokemon:svp-svp-161"}


def _hit(title):
    return {"title": title, "price": 6.0, "shipping_cost": 1.0, "source": "ebay", "provenance_score": 0.7}


def test_other_card_number_fails():
    v = evaluate(MANDATE, _hit("Charizard ex 054/091 Double Rare Paldean Fates"))
    assert not v.passed and any("not #161" in r for r in v.reasons)


def test_same_card_number_passes():
    assert evaluate(MANDATE, _hit("Charizard ex Holofoil EN [SVP - 161] NM")).passed


def test_title_without_a_number_is_not_rejected():
    assert evaluate(MANDATE, _hit("Charizard ex 161 Holo Promo Scarlet & Violet")).passed


def test_free_text_mandate_is_untouched():
    m = {**MANDATE, "canonical_ref": None}
    assert evaluate(m, _hit("Charizard ex 054/091 Double Rare")).passed


def test_cooldown_note_states_time_since_the_last_deal():
    """It printed the hours LEFT as 'ago': 23.6h ago for a deal 25 min old."""
    from datetime import datetime, timedelta, timezone
    m = {**MANDATE, "canonical_ref": None, "cooldown_hours": 24,
         "last_deal_at": datetime.now(timezone.utc) - timedelta(minutes=30)}
    note = next(r for r in evaluate(m, _hit("Charizard ex")).reasons if "cooldown note" in r)
    assert "0.5h ago" in note
