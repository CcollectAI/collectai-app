"""
Tests for pipelines/notes_parser.py — parsing free-text notes into
structured attributes_json fields.
"""

from pipelines.notes_parser import parse_notes, _extract_kv


# ---------------------------------------------------------------------------
# Generic key:value extractor
# ---------------------------------------------------------------------------

class TestExtractKV:
    def test_reference_number(self):
        assert _extract_kv("Ref. 126610LN") == ("reference_number", "126610LN")
        assert _extract_kv("Reference 116500LN-BK") == ("reference_number", "116500LN-BK")

    def test_sku(self):
        assert _extract_kv("SKU: 555088-101") == ("sku", "555088-101")
        assert _extract_kv("Style Code: ABC123") == ("sku", "ABC123")

    def test_year(self):
        assert _extract_kv("1985") == ("year", 1985)
        assert _extract_kv("2024") == ("year", 2024)
        # 4-digit non-year should not match
        assert _extract_kv("1234") is None

    def test_caliber(self):
        assert _extract_kv("Cal. 3235") == ("movement_caliber", "3235")
        assert _extract_kv("Caliber 7750") == ("movement_caliber", "7750")

    def test_movement(self):
        assert _extract_kv("Automatic Cal. 3235") == ("movement", "Automatic 3235")
        assert _extract_kv("Quartz Cal. F950") == ("movement", "Quartz F950")

    def test_age_years(self):
        assert _extract_kv("18 Years Old") == ("age_years", 18)
        assert _extract_kv("12 year old") == ("age_years", 12)

    def test_proof_and_abv(self):
        assert _extract_kv("90 proof") == ("proof", 90.0)
        assert _extract_kv("43% ABV") == ("abv_percent", 43.0)
        assert _extract_kv("46.5%") == ("abv_percent", 46.5)

    def test_bottle_size(self):
        assert _extract_kv("750ml") == ("bottle_size_ml", 750)
        assert _extract_kv("700 ml") == ("bottle_size_ml", 700)

    def test_piece_count(self):
        assert _extract_kv("1500 pieces") == ("piece_count", 1500)
        assert _extract_kv("250 pcs") == ("piece_count", 250)

    def test_scale(self):
        assert _extract_kv("1/35") == ("scale", "1/35")
        assert _extract_kv("1:48") == ("scale", "1/48")

    def test_generic_key_value(self):
        assert _extract_kv("Color: Red") == ("color", "Red")
        assert _extract_kv("Material: Stainless Steel") == ("material", "Stainless Steel")

    def test_returns_none_for_unparseable(self):
        assert _extract_kv("Stainless Steel") is None
        assert _extract_kv("") is None
        assert _extract_kv("   ") is None


# ---------------------------------------------------------------------------
# Watches parser
# ---------------------------------------------------------------------------

class TestParseWatches:
    def test_rolex_submariner(self):
        notes = "Rolex | Submariner Date | Ref. 126610LN | Automatic Cal. 3235 | Stainless Steel"
        attrs = parse_notes("watches", notes, brand="Rolex")
        assert attrs["brand"] == "Rolex"
        assert attrs["model_name"] == "Submariner Date"
        assert attrs["reference_number"] == "126610LN"
        assert attrs["case_material"] == "Stainless Steel"
        # movement may be either from movement or movement_caliber regex
        assert "movement" in attrs or "movement_caliber" in attrs

    def test_omega(self):
        notes = "Omega | Speedmaster Professional | Ref. 311.30.42.30.01.005 | Manual Cal. 1861 | Stainless Steel"
        attrs = parse_notes("watches", notes, brand="Omega")
        assert attrs["brand"] == "Omega"
        assert attrs["model_name"] == "Speedmaster Professional"
        assert attrs["reference_number"] == "311.30.42.30.01.005"


# ---------------------------------------------------------------------------
# Sneakers parser
# ---------------------------------------------------------------------------

class TestParseSneakers:
    def test_jordan_with_sku(self):
        notes = "OG Colorway | SKU: 555088-101"
        attrs = parse_notes("sneakers", notes)
        assert attrs["release_type"] == "OG Colorway"
        assert attrs["sku"] == "555088-101"

    def test_collab(self):
        notes = "Collaboration | SKU: DH3227-105"
        attrs = parse_notes("sneakers", notes)
        assert attrs["release_type"] == "Collaboration"
        assert attrs["sku"] == "DH3227-105"


# ---------------------------------------------------------------------------
# Comic books parser
# ---------------------------------------------------------------------------

class TestParseComicBooks:
    def test_marvel_key(self):
        notes = "Marvel | Amazing Fantasy | Golden Age Key"
        attrs = parse_notes("comic_books", notes)
        assert attrs["publisher"] == "Marvel"
        assert attrs["series_title"] == "Amazing Fantasy"
        assert attrs["key_issue_note"] == "Golden Age Key"

    def test_dc_key(self):
        notes = "DC | Batman | Golden Age Key"
        attrs = parse_notes("comic_books", notes)
        assert attrs["publisher"] == "DC"
        assert attrs["series_title"] == "Batman"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_notes(self):
        assert parse_notes("watches", "") == {}
        assert parse_notes("watches", "   ") == {}

    def test_unknown_category_uses_generic(self):
        # Should still extract via generic kv parser
        notes = "Some Brand | Ref. ABC123 | 2020"
        attrs = parse_notes("nonexistent_category", notes)
        assert attrs["reference_number"] == "ABC123"
        assert attrs["year"] == 2020

    def test_single_part(self):
        notes = "Just one thing"
        attrs = parse_notes("watches", notes, brand="Rolex")
        # Should not crash; brand-only template will populate brand
        assert "brand" in attrs or attrs == {}

    def test_pipe_with_empty_parts(self):
        notes = "Marvel || X-Men || Silver Age Key"
        attrs = parse_notes("comic_books", notes)
        assert attrs["publisher"] == "Marvel"
