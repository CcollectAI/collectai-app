"""Tests for app/features/barcode_lookup_router.py — barcode lookup, classification, ISBN detection.

All tests use the in-memory fallback (DB_ENABLED=false) so no real database is needed.
External HTTP calls (Open Library, Google Books) are mocked.
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")

from starlette.testclient import TestClient
from main import app  # noqa: E402
from app.features.barcode_lookup_router import (
    _is_isbn,
    _classify_category,
    PUBLISHER_CATEGORY_MAP,
    SUBJECT_CATEGORY_MAP,
)

client = TestClient(app)


# ===========================================================================
# _is_isbn helper
# ===========================================================================

class TestIsIsbn:
    def test_isbn13_978(self):
        assert _is_isbn("9781421504902") is True

    def test_isbn13_979(self):
        assert _is_isbn("9791234567890") is True

    def test_isbn13_with_dashes(self):
        assert _is_isbn("978-1-4215-0490-2") is True

    def test_isbn13_with_spaces(self):
        assert _is_isbn("978 1 4215 0490 2") is True

    def test_isbn10(self):
        assert _is_isbn("1421504901") is True

    def test_not_isbn_short(self):
        assert _is_isbn("12345") is False

    def test_not_isbn_wrong_prefix(self):
        assert _is_isbn("1234567890123") is False

    def test_ean13_non_isbn(self):
        """EAN13 barcodes that aren't ISBNs (not starting with 978/979)."""
        assert _is_isbn("0012345678905") is False

    def test_empty_string(self):
        assert _is_isbn("") is False

    def test_upc_barcode(self):
        assert _is_isbn("036000291452") is False


# ===========================================================================
# _classify_category helper
# ===========================================================================

class TestClassifyCategory:
    def test_publisher_viz_media_returns_manga(self):
        assert _classify_category("VIZ Media", "One Punch Man", []) == "manga"

    def test_publisher_kodansha_returns_manga(self):
        assert _classify_category("Kodansha Comics", "Attack on Titan", []) == "manga"

    def test_publisher_games_workshop_returns_warhammer(self):
        assert _classify_category("Games Workshop", "Codex: Space Marines", []) == "warhammer"

    def test_publisher_lego_returns_lego(self):
        assert _classify_category("LEGO Systems Inc", "Creator Expert", []) == "lego"

    def test_publisher_nintendo_returns_nintendo(self):
        assert _classify_category("Nintendo", "The Legend of Zelda", []) == "nintendo_merch"

    def test_publisher_disney_returns_disney(self):
        assert _classify_category("Disney Press", "Frozen Art Book", []) == "disney"

    def test_publisher_ghibli_returns_ghibli(self):
        assert _classify_category("Studio Ghibli", "Art of Spirited Away", []) == "ghibli"

    def test_publisher_hybe_returns_kpop(self):
        assert _classify_category("HYBE Labels", "BTS Photobook", []) == "kpop_merch"

    def test_subject_pokemon_returns_pokemon(self):
        assert _classify_category("", "Random Title", ["pokemon", "games"]) == "pokemon"

    def test_subject_mtg_returns_mtg(self):
        assert _classify_category("", "Card Game", ["Magic: The Gathering"]) == "mtg"

    def test_subject_yugioh_returns_yugioh(self):
        assert _classify_category("", "Game", ["Yu-Gi-Oh"]) == "yugioh"

    def test_subject_funko_returns_funko(self):
        assert _classify_category("", "Pop Figure", ["Funko"]) == "funko"

    def test_subject_gundam_returns_gunpla(self):
        assert _classify_category("", "MG Wing Zero", ["gundam", "model kit"]) == "gunpla"

    def test_subject_vtuber_returns_vtuber(self):
        assert _classify_category("", "Hololive Goods", ["vtuber merch"]) == "vtuber"

    def test_title_contains_keyword(self):
        """Subjects + title are combined for lookup, so title keywords work."""
        assert _classify_category("", "The Art of Warhammer", []) == "warhammer"

    def test_no_match_returns_none(self):
        assert _classify_category("Random Publisher", "Cooking Recipes", ["food"]) is None

    def test_publisher_takes_precedence(self):
        """Publisher match should take precedence over subject match."""
        # Publisher says manga, subjects say pokemon
        result = _classify_category("VIZ Media", "Pokemon Adventures", ["pokemon"])
        assert result == "manga"

    def test_case_insensitive_publisher(self):
        assert _classify_category("GAMES WORKSHOP", "Test", []) == "warhammer"

    def test_case_insensitive_subjects(self):
        assert _classify_category("", "Test", ["POKEMON"]) == "pokemon"

    def test_taylor_swift_from_publisher(self):
        assert _classify_category("Taylor Swift Merch", "Era Tour Book", []) == "taylor_swift"

    def test_bandai_from_publisher(self):
        assert _classify_category("Bandai Spirits", "Gunpla Kit", []) == "bandai_premium"


# ===========================================================================
# POST /barcode/lookup — main endpoint
# ===========================================================================

class TestBarcodeLookup:
    def test_lookup_isbn_no_external_match(self):
        """When Open Library and Google Books return nothing, we get 'no match'."""
        with patch(
            "app.features.barcode_lookup_router._lookup_open_library",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.features.barcode_lookup_router._lookup_google_books",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.post("/barcode/lookup", json={"barcode": "9781421504902"})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] is None
        assert data["category_id"] is None
        assert "title" in data["missing_required"]
        assert "categoryId" in data["missing_required"]
        assert any("No match" in s for s in data["rationale"])

    def test_lookup_isbn_open_library_match(self):
        """When Open Library returns data, it should be classified."""
        ol_data = {
            "title": "Naruto Vol. 1",
            "publisher": "VIZ Media",
            "publishers": ["VIZ Media"],
            "authors": ["Masashi Kishimoto"],
            "subjects": ["manga", "shonen"],
            "cover_url": "https://covers.openlibrary.org/b/id/12345-L.jpg",
            "pages": 200,
            "isbn": "9781569319000",
            "publish_date": "2003",
            "source": "open_library",
        }
        with patch(
            "app.features.barcode_lookup_router._lookup_open_library",
            new_callable=AsyncMock,
            return_value=ol_data,
        ), patch(
            "app.features.barcode_lookup_router._lookup_market_price",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.post("/barcode/lookup", json={"barcode": "9781569319000"})

        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Naruto Vol. 1"
        assert data["category_id"] == "manga"
        assert data["attributes"]["publisher"] == "VIZ Media"
        assert data["attributes"]["isbn"] == "9781569319000"
        assert data["image_url"] == ol_data["cover_url"]
        assert any("Open Library" in s for s in data["rationale"])

    def test_lookup_isbn_google_books_fallback(self):
        """When Open Library fails, Google Books is used as fallback."""
        gb_data = {
            "title": "Pokemon Adventures Vol. 1",
            "publisher": "VIZ Media",
            "publishers": ["VIZ Media"],
            "authors": ["Hidenori Kusaka"],
            "subjects": ["manga"],
            "cover_url": None,
            "pages": 200,
            "isbn": "9781421530543",
            "publish_date": "2009",
            "source": "google_books",
        }
        with patch(
            "app.features.barcode_lookup_router._lookup_open_library",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.features.barcode_lookup_router._lookup_google_books",
            new_callable=AsyncMock,
            return_value=gb_data,
        ), patch(
            "app.features.barcode_lookup_router._lookup_market_price",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.post("/barcode/lookup", json={"barcode": "9781421530543"})

        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Pokemon Adventures Vol. 1"
        assert any("Google Books" in s for s in data["rationale"])

    def test_lookup_non_isbn_barcode_no_catalog(self):
        """Non-ISBN barcodes with no local catalog match suggest QuickScan."""
        r = client.post("/barcode/lookup", json={"barcode": "036000291452"})
        assert r.status_code == 200
        data = r.json()
        assert data["title"] is None
        assert any("QuickScan" in s for s in data["rationale"])

    def test_lookup_with_code_type_isbn(self):
        """When code_type=isbn, treat barcode as ISBN even if it doesn't look like one."""
        with patch(
            "app.features.barcode_lookup_router._lookup_open_library",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.features.barcode_lookup_router._lookup_google_books",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.post("/barcode/lookup", json={
                "barcode": "1234567890",
                "code_type": "isbn",
            })

        assert r.status_code == 200
        data = r.json()
        # Should have tried ISBN lookup
        assert any("ISBN" in s for s in data["rationale"])

    def test_lookup_with_code_type_ean13(self):
        """code_type=ean13 triggers ISBN lookup path."""
        with patch(
            "app.features.barcode_lookup_router._lookup_open_library",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.features.barcode_lookup_router._lookup_google_books",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.post("/barcode/lookup", json={
                "barcode": "036000291452",
                "code_type": "ean13",
            })
        assert r.status_code == 200

    def test_lookup_unclassified_book(self):
        """Book found but not matching any category should set missing_required."""
        ol_data = {
            "title": "Cooking 101",
            "publisher": "Random House",
            "publishers": ["Random House"],
            "authors": ["Chef Bob"],
            "subjects": ["cooking"],
            "cover_url": None,
            "pages": 300,
            "isbn": "9780000000001",
            "publish_date": "2020",
            "source": "open_library",
        }
        with patch(
            "app.features.barcode_lookup_router._lookup_open_library",
            new_callable=AsyncMock,
            return_value=ol_data,
        ), patch(
            "app.features.barcode_lookup_router._lookup_market_price",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = client.post("/barcode/lookup", json={"barcode": "9780000000001"})

        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Cooking 101"
        assert data["category_id"] is None
        assert "categoryId" in data["missing_required"]
        assert any("Could not auto-classify" in s for s in data["rationale"])

    # ---- Validation / error cases ----

    def test_lookup_empty_barcode_422(self):
        r = client.post("/barcode/lookup", json={"barcode": ""})
        assert r.status_code == 422

    def test_lookup_missing_barcode_422(self):
        r = client.post("/barcode/lookup", json={})
        assert r.status_code == 422

    def test_lookup_barcode_too_long_422(self):
        r = client.post("/barcode/lookup", json={"barcode": "X" * 51})
        assert r.status_code == 422

    def test_lookup_empty_body_422(self):
        r = client.post("/barcode/lookup")
        assert r.status_code == 422

    def test_lookup_response_shape(self):
        """Verify the response conforms to BarcodeLookupResponse model."""
        r = client.post("/barcode/lookup", json={"barcode": "036000291452"})
        assert r.status_code == 200
        data = r.json()
        # All expected fields must be present
        assert "title" in data
        assert "category_id" in data
        assert "taxonomy_version" in data
        assert data["taxonomy_version"] == "v1.0"
        assert "collections" in data
        assert isinstance(data["collections"], list)
        assert "attributes" in data
        assert isinstance(data["attributes"], dict)
        assert "missing_required" in data
        assert isinstance(data["missing_required"], list)
        assert "rationale" in data
        assert isinstance(data["rationale"], list)

    def test_lookup_whitespace_barcode_trimmed(self):
        """Leading/trailing whitespace in the barcode should be handled."""
        r = client.post("/barcode/lookup", json={"barcode": "  036000291452  "})
        assert r.status_code == 200

    def test_lookup_isbn_with_price_band(self):
        """When market price data is available, price_band should be returned."""
        from app.features.barcode_lookup_router import PriceBand

        ol_data = {
            "title": "One Piece Vol. 1",
            "publisher": "VIZ Media",
            "publishers": ["VIZ Media"],
            "authors": ["Eiichiro Oda"],
            "subjects": ["manga"],
            "cover_url": None,
            "pages": 208,
            "isbn": "9781569319017",
            "publish_date": "2003",
            "source": "open_library",
        }
        mock_price = PriceBand(q10=5.0, q50=12.0, q90=25.0, confidence=0.7, currency="EUR")

        with patch(
            "app.features.barcode_lookup_router._lookup_open_library",
            new_callable=AsyncMock,
            return_value=ol_data,
        ), patch(
            "app.features.barcode_lookup_router._lookup_market_price",
            new_callable=AsyncMock,
            return_value=mock_price,
        ):
            r = client.post("/barcode/lookup", json={"barcode": "9781569319017"})

        assert r.status_code == 200
        data = r.json()
        assert data["price_band"] is not None
        assert data["price_band"]["q10"] == 5.0
        assert data["price_band"]["q50"] == 12.0
        assert data["price_band"]["q90"] == 25.0
        assert data["price_band"]["confidence"] == 0.7
        assert data["price_band"]["currency"] == "EUR"


# ===========================================================================
# Publisher / Subject mapping coverage
# ===========================================================================

class TestCategoryMappingCoverage:
    def test_publisher_map_has_entries(self):
        assert len(PUBLISHER_CATEGORY_MAP) > 10

    def test_subject_map_has_entries(self):
        assert len(SUBJECT_CATEGORY_MAP) > 20

    def test_all_publisher_categories_are_valid_strings(self):
        for pattern, cat in PUBLISHER_CATEGORY_MAP:
            assert isinstance(pattern, str)
            assert isinstance(cat, str)
            assert len(cat) > 0

    def test_all_subject_categories_are_valid_strings(self):
        for pattern, cat in SUBJECT_CATEGORY_MAP:
            assert isinstance(pattern, str)
            assert isinstance(cat, str)
            assert len(cat) > 0

    def test_publisher_patterns_are_lowercase(self):
        """All publisher patterns should be lowercase for case-insensitive matching."""
        for pattern, _cat in PUBLISHER_CATEGORY_MAP:
            assert pattern == pattern.lower(), f"Pattern '{pattern}' should be lowercase"

    def test_subject_patterns_are_lowercase(self):
        """All subject patterns should be lowercase for case-insensitive matching."""
        for pattern, _cat in SUBJECT_CATEGORY_MAP:
            assert pattern == pattern.lower(), f"Pattern '{pattern}' should be lowercase"
