"""Barcode lookup: check digits and the VIZ publisher (2026-10-15).

Probed /barcode/lookup as a member: a mistyped ISBN went to Open Library /
Google Books and came back "No match" ~1.5 s later, and Naruto vol 1 (VIZ,
listed by Open Library as bare "Viz") was classified comic_books.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DB_ENABLED", "false")

from app.features.barcode_lookup_router import _classify_category, _gs1_check_ok  # noqa: E402


@pytest.mark.parametrize("code,ok", [
    ("9780439023481", True),    # ISBN-13 Hunger Games
    ("9780439023482", False),   # same, last digit wrong
    ("0439023483", True),       # ISBN-10
    ("0439023484", False),
    ("5702015869935", True),    # EAN-13 LEGO 75192
    ("012345678905", True),     # UPC-A
])
def test_check_digit(code, ok):
    assert _gs1_check_ok(code) is ok


# 8 digits is left alone: a scanned UPC-E ("01234565", check digit of the
# expanded UPC-A 012345000065) fails the EAN-8 formula.
@pytest.mark.parametrize("code", ["12345", "ABC-123", "X1234567890Y", "01234565", "96385074"])
def test_other_shapes_are_left_to_the_lookup(code):
    assert _gs1_check_ok(code) is None


def test_viz_is_manga_and_matched_as_a_whole_word():
    assert _classify_category("Viz", "Naruto, Vol 1", ["comics"]) == "manga"
    assert _classify_category("Vizzini Press", "Some Novel", []) is None


class _Head:
    def __init__(self, code):
        self.code = code
        self.urls = []

    async def head(self, url, follow_redirects=True):
        self.urls.append(url)
        return type("R", (), {"status_code": self.code})()


def test_isbn_cover_fallback_only_when_the_cover_exists():
    import asyncio
    from app.features.barcode_lookup_router import _ol_isbn_cover
    ok = _Head(200)
    assert asyncio.run(_ol_isbn_cover(ok, "9781569319000")).endswith("9781569319000-L.jpg?default=false")
    assert "default=false" in ok.urls[0]  # a missing cover must 404, not draw a blank
    assert asyncio.run(_ol_isbn_cover(_Head(404), "9781569319000")) is None
