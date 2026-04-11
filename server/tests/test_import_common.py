"""Tests for pipelines/import_common.py — shared pipeline utilities."""
import json
import sys
from pathlib import Path

import pytest

# Ensure pipelines is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_common import (
    rarity_score,
    condition_score,
    RARITY_SCORE_MAP,
    CONDITION_SCORE_MAP,
    CatalogItem,
    PriceObservation,
    MarketHit,
    IngestStats,
    ValidationError,
    _validate_item_key,
    _validate_price,
    slugify,
    to_eur,
    _FALLBACK_FX,
)


# ---------------------------------------------------------------------------
# rarity_score
# ---------------------------------------------------------------------------

class TestRarityScore:
    def test_known_rarity(self):
        assert rarity_score("Common") == 0.1
        assert rarity_score("Rare") == 0.5
        assert rarity_score("Mythic Rare") == 0.9
        assert rarity_score("Starlight Rare") == 0.98

    def test_unknown_rarity_defaults_0_3(self):
        assert rarity_score("something_unknown") == 0.3

    def test_empty_string(self):
        assert rarity_score("") == 0.3

    def test_case_sensitive(self):
        # Map keys are case-sensitive
        assert rarity_score("common") == 0.3  # lowercase not in map
        assert rarity_score("Common") == 0.1


# ---------------------------------------------------------------------------
# condition_score
# ---------------------------------------------------------------------------

class TestConditionScore:
    def test_known_conditions(self):
        assert condition_score("Mint") == 1.0
        assert condition_score("Near Mint") == 0.9
        assert condition_score("NM") == 0.9
        assert condition_score("PSA 10") == 1.0
        assert condition_score("Damaged") == 0.1

    def test_unknown_defaults_0_5(self):
        assert condition_score("???") == 0.5

    def test_psa_grades(self):
        for grade in range(1, 11):
            key = f"PSA {grade}"
            assert condition_score(key) == grade / 10.0


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class TestValidation:
    def test_validate_item_key_strips(self):
        assert _validate_item_key("  hello  ") == "hello"

    def test_validate_item_key_empty_raises(self):
        with pytest.raises(ValidationError, match="empty"):
            _validate_item_key("")

    def test_validate_item_key_whitespace_raises(self):
        with pytest.raises(ValidationError, match="empty"):
            _validate_item_key("   ")

    def test_validate_item_key_too_long(self):
        with pytest.raises(ValidationError, match="too long"):
            _validate_item_key("x" * 256)

    def test_validate_price_valid(self):
        assert _validate_price(0.0) == 0.0
        assert _validate_price(99.99) == 99.99

    def test_validate_price_negative(self):
        with pytest.raises(ValidationError, match=">= 0"):
            _validate_price(-1.0)

    def test_validate_price_too_high(self):
        # MAX_PRICE_EUR raised to €20M in R50f to accommodate grail collectibles
        # (F.P. Journe watches, Action Comics #1, Paul Newman Daytona etc.)
        with pytest.raises(ValidationError, match="exceeds max"):
            _validate_price(25_000_000.0)


# ---------------------------------------------------------------------------
# CatalogItem
# ---------------------------------------------------------------------------

class TestCatalogItem:
    def test_basic_creation(self):
        item = CatalogItem(
            category="pokemon",
            item_key="base-charizard",
            title="Charizard Holo",
        )
        assert item.category == "pokemon"
        assert item.item_key == "base-charizard"

    def test_empty_category_raises(self):
        with pytest.raises(ValidationError, match="category"):
            CatalogItem(category="", item_key="test", title="Test")

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError, match="title"):
            CatalogItem(category="pokemon", item_key="test", title="")

    def test_long_title_truncated(self):
        item = CatalogItem(
            category="pokemon",
            item_key="test",
            title="x" * 600,
        )
        assert len(item.title) == 500

    def test_to_row(self):
        item = CatalogItem(
            category="pokemon",
            item_key="test-item",
            title="Test Item",
            set_code="base",
            brand="Pokemon TCG",
            rarity="Rare",
            attributes_json={"set": "Base Set"},
        )
        row = item.to_row()
        assert row["category"] == "pokemon"
        assert row["item_key"] == "test-item"
        assert "attributes_json" in row
        assert json.loads(row["attributes_json"]) == {"set": "Base Set"}

    def test_to_row_omits_empty_optional_fields(self):
        item = CatalogItem(
            category="pokemon",
            item_key="test",
            title="Test",
        )
        row = item.to_row()
        assert "image_url" not in row
        assert "barcode" not in row
        assert "attributes_json" not in row


# ---------------------------------------------------------------------------
# PriceObservation
# ---------------------------------------------------------------------------

class TestPriceObservation:
    def test_basic_creation(self):
        obs = PriceObservation(
            features={"condition_score": 0.9, "rarity_score": 0.5},
            price=25.50,
        )
        assert obs.price == 25.50

    def test_negative_price_raises(self):
        with pytest.raises(ValidationError):
            PriceObservation(features={}, price=-5.0)

    def test_non_numeric_feature_raises(self):
        with pytest.raises(ValidationError, match="numeric"):
            PriceObservation(
                features={"condition_score": "good"},
                price=10.0,
            )

    def test_to_jsonl(self):
        obs = PriceObservation(
            features={"rarity_score": 0.8},
            price=42.0,
        )
        line = obs.to_jsonl()
        data = json.loads(line)
        assert data["price"] == 42.0
        assert data["features"]["rarity_score"] == 0.8


# ---------------------------------------------------------------------------
# IngestStats
# ---------------------------------------------------------------------------

class TestIngestStats:
    def test_initial_state(self):
        stats = IngestStats()
        assert stats.total_errors == 0
        assert stats.has_errors is False

    def test_error_counting(self):
        stats = IngestStats()
        stats.catalog_errors = 3
        stats.market_hits_errors = 2
        stats.transform_errors = 1
        assert stats.total_errors == 6
        assert stats.has_errors is True

    def test_record_warning(self):
        stats = IngestStats()
        stats.record_warning("test warning")
        assert len(stats.warnings) == 1
        assert stats.warnings[0] == "test warning"

    def test_summary(self):
        stats = IngestStats()
        stats.catalog_upserted = 100
        stats.catalog_errors = 2
        summary = stats.summary()
        assert "100" in summary
        assert "2" in summary


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("Charizard (Holo) #4/102") == "charizard-holo-4102"

    def test_multiple_spaces_and_dashes(self):
        assert slugify("a  --  b") == "a-b"

    def test_strip_leading_trailing(self):
        assert slugify("  --hello--  ") == "hello"

    def test_unicode_kept(self):
        result = slugify("pokémon")
        assert "pok" in result


# ---------------------------------------------------------------------------
# to_eur (with fallback FX rates)
# ---------------------------------------------------------------------------

class TestToEur:
    def test_eur_passthrough(self):
        assert to_eur(100.0, "EUR") == 100.0

    def test_usd_conversion(self):
        result = to_eur(100.0, "USD")
        # Should use fallback rate 0.92
        assert result == round(100.0 * _FALLBACK_FX["USD"], 2)

    def test_jpy_conversion(self):
        result = to_eur(10000.0, "JPY")
        assert result == round(10000.0 * _FALLBACK_FX["JPY"], 2)

    def test_case_insensitive_currency(self):
        result = to_eur(100.0, "usd")
        assert result == round(100.0 * _FALLBACK_FX["USD"], 2)

    def test_unknown_currency_returns_as_is(self):
        result = to_eur(50.0, "XYZ")
        assert result == 50.0
