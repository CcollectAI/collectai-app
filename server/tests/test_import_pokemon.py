"""Tests for pipelines/import_pokemon.py — Pokémon TCG catalog importer (Item 15)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.import_pokemon import (
    card_to_catalog_item,
    card_to_price_observations,
    card_to_market_hits,
    set_to_collection_row,
)


SAMPLE_CARD = {
    "id": "base1-4",
    "name": "Charizard",
    "supertype": "Pokémon",
    "subtypes": ["Stage 2"],
    "hp": "120",
    "types": ["Fire"],
    "number": "4",
    "rarity": "Rare Holo",
    "artist": "Mitsuhiro Arita",
    "set": {
        "id": "base1",
        "name": "Base",
        "series": "Base",
        "printedTotal": 102,
        "total": 102,
        "releaseDate": "1999/01/09",
        "images": {"symbol": "https://images.pokemontcg.io/base1/symbol.png"},
    },
    "images": {
        "small": "https://images.pokemontcg.io/base1/4.png",
        "large": "https://images.pokemontcg.io/base1/4_hires.png",
    },
    "tcgplayer": {
        "url": "https://prices.pokemontcg.io/tcgplayer/base1-4",
        "updatedAt": "2026-01-15",
        "prices": {
            "holofoil": {"market": 250.00, "low": 200.00, "mid": 260.00},
        },
    },
    "cardmarket": {
        "url": "https://prices.pokemontcg.io/cardmarket/base1-4",
        "updatedAt": "2026-01-15",
        "prices": {
            "averageSellPrice": 220.0,
            "avg30": 215.0,
        },
    },
}

SAMPLE_SET = {
    "id": "base1",
    "name": "Base",
    "series": "Base",
    "printedTotal": 102,
    "total": 102,
    "releaseDate": "1999/01/09",
    "images": {
        "symbol": "https://images.pokemontcg.io/base1/symbol.png",
        "logo": "https://images.pokemontcg.io/base1/logo.png",
    },
}


class TestCardToCatalogItem:
    def test_basic_fields(self):
        item = card_to_catalog_item(SAMPLE_CARD, "Base")
        assert item.category == "pokemon"
        assert item.title == "Charizard"
        assert item.brand == "Pokemon TCG"
        assert "base1" in item.item_key
        assert item.set_code == "base1"
        assert item.image_url == "https://images.pokemontcg.io/base1/4.png"

    def test_attributes(self):
        item = card_to_catalog_item(SAMPLE_CARD, "Base")
        attrs = item.attributes_json
        assert attrs["set"] == "Base"
        assert attrs["rarity"] == "Rare Holo"
        assert attrs["supertype"] == "Pokémon"
        assert "Stage 2" in attrs["subtypes"]
        assert attrs["artist"] == "Mitsuhiro Arita"

    def test_notes_format(self):
        item = card_to_catalog_item(SAMPLE_CARD, "Base")
        assert "Base" in item.notes
        assert "4/102" in item.notes


class TestCardToPriceObservations:
    def test_tcgplayer_prices(self):
        obs = card_to_price_observations(SAMPLE_CARD)
        # Should have at least 1 TCGPlayer + 1 Cardmarket observation
        assert len(obs) >= 2

    def test_tcgplayer_eur_conversion(self):
        obs = card_to_price_observations(SAMPLE_CARD)
        tcg_obs = [o for o in obs if o.features.get("variant") != "cardmarket"]
        assert len(tcg_obs) >= 1
        # Price should be in EUR (converted from USD)
        assert tcg_obs[0].price > 0
        assert tcg_obs[0].price < 250  # Should be less than USD amount

    def test_cardmarket_observation(self):
        obs = card_to_price_observations(SAMPLE_CARD)
        cm_obs = [o for o in obs if o.features.get("variant") == "cardmarket"]
        assert len(cm_obs) == 1
        assert cm_obs[0].price == 220.0  # Already EUR

    def test_no_prices(self):
        card = {**SAMPLE_CARD, "tcgplayer": {}, "cardmarket": {}}
        obs = card_to_price_observations(card)
        assert len(obs) == 0

    def test_features_present(self):
        obs = card_to_price_observations(SAMPLE_CARD)
        for o in obs:
            assert "condition_score" in o.features
            assert "rarity_score" in o.features


class TestCardToMarketHits:
    def test_hits_from_tcgplayer_and_cardmarket(self):
        hits = card_to_market_hits(SAMPLE_CARD)
        providers = {h.provider for h in hits}
        assert "tcgplayer" in providers
        assert "cardmarket" in providers

    def test_hit_fields(self):
        hits = card_to_market_hits(SAMPLE_CARD)
        for hit in hits:
            assert hit.category == "pokemon"
            assert hit.currency == "EUR"
            assert hit.price > 0
            assert hit.normalized_key
            assert hit.listing_id

    def test_no_prices_yields_no_hits(self):
        card = {**SAMPLE_CARD, "tcgplayer": {}, "cardmarket": {}}
        hits = card_to_market_hits(card)
        assert len(hits) == 0


class TestSetToCollectionRow:
    def test_basic_fields(self):
        row = set_to_collection_row(SAMPLE_SET)
        assert row["category"] == "pokemon"
        assert row["collection_key"] == "base1"
        assert row["display_name"] == "Base"
        assert row["total_items"] == 102
        assert row["release_date"] == "1999/01/09"

    def test_image_url(self):
        row = set_to_collection_row(SAMPLE_SET)
        assert "logo" in row["image_url"]

    def test_notes_contains_series(self):
        row = set_to_collection_row(SAMPLE_SET)
        assert "Base" in row["notes"]
