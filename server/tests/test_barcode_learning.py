"""Barcodes learned from members' saves — who may see what (2026-09-26)."""
import asyncio
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.lib.barcode_learning import lookup_learned, record_observation  # noqa: E402

LEGO = "5702015869935"
T0 = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)


def _row(user, title, category="lego", key=None, day=0):
    return {"user_id": user, "category": category, "title": title,
            "canonical_key": key, "updated_at": T0 + dt.timedelta(days=day)}


class _Conn:
    def __init__(self, rows=None):
        self.rows, self.executed = rows or [], []

    async def fetch(self, sql, *args):
        return self.rows

    async def execute(self, sql, *args):
        self.executed.append(args)


def _look(rows, user):
    return asyncio.run(lookup_learned(_Conn(rows), LEGO, user))


def test_a_catalogue_link_is_shared_with_anyone():
    got = _look([_row("u1", "my falcon", key="75192-1-millennium-falcon")], "someone-else")
    assert got["canonical_key"] == "75192-1-millennium-falcon"
    assert got["source"] == "learned_catalogue"


def test_the_link_more_members_agree_on_wins():
    rows = [_row("u1", "x", key="wrong-1"),
            _row("u2", "y", key="75192-1-millennium-falcon"),
            _row("u3", "z", key="75192-1-millennium-falcon")]
    assert _look(rows, None)["canonical_key"] == "75192-1-millennium-falcon"


def test_own_free_text_comes_back_to_its_author():
    got = _look([_row("u1", "Grandpa's Falcon box")], "u1")
    assert got["title"] == "Grandpa's Falcon box" and got["source"] == "learned_own"


def test_one_members_free_text_is_never_shown_to_another():
    assert _look([_row("u1", "Grandpa's Falcon box")], "u2") is None


def test_free_text_is_shared_once_two_members_agree():
    rows = [_row("u1", "LEGO Millennium Falcon 75192"), _row("u2", "lego millennium falcon 75192!")]
    got = _look(rows, "u3")
    assert got["source"] == "learned_agreed" and got["members"] == 2


def test_nothing_learned_is_none():
    assert _look([], "u1") is None


def test_record_rejects_an_invalid_barcode_and_an_empty_title():
    c = _Conn()
    assert asyncio.run(record_observation(c, "u1", "not-a-code", "x", "lego", None)) is False
    assert asyncio.run(record_observation(c, "u1", LEGO, "  ", "lego", None)) is False
    assert c.executed == []


def test_record_upserts_a_valid_one():
    c = _Conn()
    assert asyncio.run(record_observation(c, "u1", LEGO, "Millennium Falcon", "lego", "75192-1-millennium-falcon"))
    assert c.executed[0][:3] == (LEGO, "u1", "lego")


def test_a_serial_style_code_is_neither_learned_nor_looked_up():
    c = _Conn([_row("u1", "x", key="k")])
    assert asyncio.run(record_observation(c, "u1", "SN-ABC-123", "x", "lego", None)) is False
    assert asyncio.run(lookup_learned(c, "SN-ABC-123", "u1")) is None
