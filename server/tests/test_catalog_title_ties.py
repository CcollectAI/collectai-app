"""Catalog rows that share a title must not produce a confident, arbitrary identity.

2026-09-24: /catalog/match returned FIVE pokemon "Charizard ex" rows at score
1.0 and `best` was the first (sv4pt5-234) — even with set_code "svp" sent. That
key prices the item and decides which Target Hit watchers are alerted: the
member watching SVP #161 would never hear of a seller's #161, and a watcher of
#234 would be alerted for the wrong card.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.intake.catalog_matching import resolve_title_ties  # noqa: E402

FIVE = [
    {"item_key": k, "match_score": 1.0, "set_code": s}
    for k, s in [
        ("sv4pt5-sv4pt5-234", "sv4pt5"), ("sv3-sv3-125", "sv3"), ("sv4pt5-sv4pt5-54", "sv4pt5"),
        ("svp-svp-161", "svp"), ("sv3pt5-sv3pt5-6", "sv3pt5"),
    ]
]


def test_unresolved_tie_is_flagged_and_capped_below_every_writer():
    out, ambiguous = resolve_title_ties(FIVE, None, None)
    assert ambiguous
    assert all(m["match_score"] < 0.6 and m["ambiguous"] for m in out)


def test_card_number_picks_the_card():
    out, ambiguous = resolve_title_ties(FIVE, None, "161")
    assert not ambiguous and out[0]["item_key"] == "svp-svp-161" and out[0]["match_score"] == 1.0


def test_number_with_a_set_total_and_leading_zeros():
    out, ambiguous = resolve_title_ties(FIVE, "sv4pt5", "054/091")
    assert not ambiguous and out[0]["item_key"] == "sv4pt5-sv4pt5-54"


def test_set_code_alone_resolves_when_unique():
    out, ambiguous = resolve_title_ties(FIVE, "svp", None)
    assert not ambiguous and out[0]["item_key"] == "svp-svp-161"


def test_set_code_that_still_leaves_two_is_ambiguous():
    _, ambiguous = resolve_title_ties(FIVE, "sv4pt5", None)
    assert ambiguous


def test_a_clear_winner_is_untouched():
    rows = [{"item_key": "a", "match_score": 1.0}, {"item_key": "b", "match_score": 0.7}]
    out, ambiguous = resolve_title_ties(rows, None, None)
    assert not ambiguous and out == rows


# ---------------------------------------------------------------------------
# 2026-09-26: the NUMBER read off the item decides between same-title rows.
# QuickScan of Base Set Charizard (printed 4/102) adopted the Celebrations
# reprint (printed 4/25, card_number "4" — the same head) at score 1.00 and
# priced it EUR 154 against EUR 1,159. Rows below are the real catalogue values.
# ---------------------------------------------------------------------------
from app.agents.intake.catalog_matching import number_agrees


def test_printed_number_separates_a_reprint():
    assert number_agrees("4/102", "4/102", "4") is True        # base1-base1-4
    assert number_agrees("4/102", "4/25", "4") is False        # cel25c-cel25c-4-a
    assert number_agrees("4/102", "4", "4") is True            # me55c: no printed total → heads agree


def test_heads_compare_when_no_total_was_read():
    assert number_agrees("4", "4/102", "4") is True
    assert number_agrees("BT5-087", None, "BT5-087") is True    # digimon code
    assert number_agrees("OP07-082", None, "OP07-083") is False


def test_nothing_read_or_nothing_stored_is_unknown():
    assert number_agrees("", "4/102", "4") is None
    assert number_agrees("4/102", None, None) is None


def test_a_tie_prefers_the_row_whose_number_agrees():
    tied = [
        {"item_key": "me55c-me55c-4", "set_code": "me55c", "match_score": 1.0, "number_agrees": None},
        {"item_key": "base1-base1-4", "set_code": "base1", "match_score": 1.0, "number_agrees": True},
    ]
    out, ambiguous = resolve_title_ties(tied, "BS", "4/102")
    assert not ambiguous
    assert out[0]["item_key"] == "base1-base1-4"


# Strategy 0b end to end, with the two real rows that print 4/102.
import asyncio  # noqa: E402
from app.agents.intake.catalog_matching import _match_catalog_items  # noqa: E402

_ROWS_4_102 = [
    {"id": "11111111-1111-1111-1111-111111111111", "category": "pokemon", "item_key": "hgss4-hgss4-4",
     "title": "Drapion", "brand": None, "rarity": None, "set_code": "hgss4", "image_url": None, "notes": None},
    {"id": "22222222-2222-2222-2222-222222222222", "category": "pokemon", "item_key": "base1-base1-4",
     "title": "Charizard", "brand": None, "rarity": None, "set_code": "base1", "image_url": None, "notes": None},
]


class _FakeConn:
    async def fetch(self, sql, *args):
        if "attributes_json ->> 'number')" in sql and "= $2" in sql:
            return _ROWS_4_102
        return []

    async def fetchrow(self, sql, *args):
        return None


class _FakePool:
    def acquire(self):
        class _Ctx:
            async def __aenter__(self_inner):
                return _FakeConn()

            async def __aexit__(self_inner, *a):
                return False
        return _Ctx()

    async def fetch(self, sql, *args):  # the number-agreement lookup
        return [{"id": r["id"], "printed": "4/102", "card_no": "4"} for r in _ROWS_4_102]


def test_a_decorated_name_still_finds_the_card_by_printed_number():
    out = asyncio.run(_match_catalog_items(
        category_id="pokemon", suggested_name="Charizard 1st Edition", search_keywords=[],
        brand=None, set_code="BS", pool=_FakePool(),
        extracted_attributes={"card_number": "4/102", "set_name": "Base Set"},
    ))
    assert out and out[0]["item_key"] == "base1-base1-4"
    assert out[0]["match_score"] >= 0.75           # adoptable
    assert all(m["item_key"] != "hgss4-hgss4-4" for m in out)  # same number, wrong title


def test_zero_padded_print_agrees_with_the_catalogue_form():
    # Vision reads the card's print "006/165"; the catalogue stores "6/165".
    # The first version compared them exactly and capped the right row (151 Charizard ex).
    from app.agents.intake.catalog_matching import norm_printed
    assert number_agrees("006/165", "6/165", "6") is True
    assert norm_printed("TG03/30") == "tg3/30"
    assert norm_printed("100/97") == "100/97"   # only LEADING zeros go


def test_two_rows_sharing_a_print_prefer_the_fuller_title():
    rows = [
        {"id": "33333333-3333-3333-3333-333333333333", "category": "pokemon", "item_key": "ecard1-ecard1-6",
         "title": "Charizard", "brand": None, "rarity": None, "set_code": "ecard1", "image_url": None, "notes": None},
        {"id": "44444444-4444-4444-4444-444444444444", "category": "pokemon", "item_key": "sv3pt5-sv3pt5-6",
         "title": "Charizard ex", "brand": None, "rarity": None, "set_code": "sv3pt5", "image_url": None, "notes": None},
    ]

    class Conn(_FakeConn):
        async def fetch(self, sql, *args):
            return rows if ("attributes_json ->> 'number')" in sql and "= $2" in sql) else []

    class Pool(_FakePool):
        def acquire(self):
            class _Ctx:
                async def __aenter__(self_inner):
                    return Conn()

                async def __aexit__(self_inner, *a):
                    return False
            return _Ctx()

        async def fetch(self, sql, *args):
            return [{"id": r["id"], "printed": "6/165", "card_no": "6"} for r in rows]

    out = asyncio.run(_match_catalog_items(
        category_id="pokemon", suggested_name="Charizard ex", search_keywords=[],
        brand=None, set_code="006", pool=Pool(),
        extracted_attributes={"card_number": "006/165"},
    ))
    assert out[0]["item_key"] == "sv3pt5-sv3pt5-6" and out[0]["match_score"] >= 0.75
    assert not out[0].get("ambiguous")
