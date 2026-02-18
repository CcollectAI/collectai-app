"""
Tests for the ingest pipeline.
Covers taxonomy mapping, deduplication, and idempotency.
"""

import pytest
import sys
from pathlib import Path

# Add server/ and repo root to path
_server_dir = Path(__file__).parent.parent
_repo_root = _server_dir.parent
sys.path.insert(0, str(_server_dir))
sys.path.insert(0, str(_repo_root))

from src.ingest.types import RawObservation, TrainingCandidate, TAXONOMY_VERSION
from src.ingest.taxonomy_mapper import (
    map_category,
    map_subtype,
    apply_taxonomy_mapping,
    batch_apply_taxonomy,
)


class TestTaxonomyMapper:
    """Tests for taxonomy mapping functionality."""

    def test_map_pokemon_card(self):
        """Should map Pokemon card titles correctly."""
        category, confidence, rationale = map_category("Pikachu VMAX PSA 10")
        assert category == "pokemon"
        assert confidence > 0.5
        assert "pokemon" in rationale.lower()

    def test_map_charizard(self):
        """Should map Charizard variants."""
        category, confidence, _ = map_category("Charizard Base Set 1st Edition")
        assert category == "pokemon"

    def test_map_mtg_black_lotus(self):
        """Should map MTG cards."""
        category, confidence, _ = map_category("Black Lotus Alpha MTG")
        assert category == "mtg"

    def test_map_funko_pop(self):
        """Should map Funko Pops."""
        category, confidence, _ = map_category("Funko Pop Batman SDCC Exclusive")
        assert category == "funko"

    def test_map_warhammer(self):
        """Should map Warhammer minis."""
        category, confidence, _ = map_category("Warhammer 40k Space Marine")
        assert category == "warhammer"

    def test_map_unknown_returns_none(self):
        """Should return None for unrecognized items."""
        category, confidence, rationale = map_category("Random household item")
        assert category is None
        assert confidence == 0.0

    def test_map_empty_returns_none(self):
        """Should handle empty input gracefully."""
        category, confidence, _ = map_category("")
        assert category is None
        assert confidence == 0.0

    def test_map_subtype_graded(self):
        """Should identify graded items."""
        subtype, confidence = map_subtype("PSA 10 Charizard", "pokemon")
        assert subtype == "graded"
        assert confidence > 0.5

    def test_map_subtype_sealed(self):
        """Should identify sealed product."""
        subtype, confidence = map_subtype("Sealed Booster Box Pokemon", "pokemon")
        assert subtype == "sealed"

    def test_apply_taxonomy_to_observation(self):
        """Should apply taxonomy mapping to RawObservation."""
        obs = RawObservation(
            observation_id="test-1",
            source="ebay",
            source_id="123",
            title="Pikachu VMAX Rainbow PSA 10",
            category_raw="Pokemon Cards",
        )

        result = apply_taxonomy_mapping(obs)

        assert result.category_id == "pokemon"
        assert result.subtype_id == "graded"
        assert result.taxonomy_version == TAXONOMY_VERSION
        assert result.mapping_confidence > 0.5

    def test_batch_apply_taxonomy(self):
        """Should map a batch of observations."""
        observations = [
            RawObservation(
                observation_id=f"test-{i}",
                source="ebay",
                source_id=str(i),
                title=title,
                category_raw="",
            )
            for i, title in enumerate([
                "Pikachu VMAX",
                "Black Lotus MTG",
                "Funko Pop Marvel",
                "Random item",
            ])
        ]

        results = batch_apply_taxonomy(observations)

        assert len(results) == 4
        assert results[0].category_id == "pokemon"
        assert results[1].category_id == "mtg"
        assert results[2].category_id == "funko"
        assert results[3].category_id is None  # Unmapped


class TestDeduplication:
    """Tests for hash-based deduplication."""

    def test_content_hash_consistency(self):
        """Same content should produce same hash."""
        obs1 = RawObservation(
            observation_id="test-1",
            source="ebay",
            source_id="123",
            title="Pikachu VMAX",
            category_raw="Pokemon",
            price_eur=100.0,
        )
        obs2 = RawObservation(
            observation_id="test-2",
            source="ebay",
            source_id="123",
            title="Pikachu VMAX",
            category_raw="Pokemon",
            price_eur=100.0,
        )

        # Same content hash despite different observation_id
        assert obs1.compute_hash() == obs2.compute_hash()

    def test_content_hash_differs_on_price(self):
        """Different prices should produce different hashes."""
        obs1 = RawObservation(
            observation_id="test-1",
            source="ebay",
            source_id="123",
            title="Pikachu VMAX",
            category_raw="",
            price_eur=100.0,
        )
        obs2 = RawObservation(
            observation_id="test-2",
            source="ebay",
            source_id="123",
            title="Pikachu VMAX",
            category_raw="",
            price_eur=200.0,
        )

        assert obs1.compute_hash() != obs2.compute_hash()

    def test_content_hash_differs_on_source_id(self):
        """Different source_id should produce different hashes."""
        obs1 = RawObservation(
            observation_id="test-1",
            source="ebay",
            source_id="123",
            title="Pikachu VMAX",
            category_raw="",
            price_eur=100.0,
        )
        obs2 = RawObservation(
            observation_id="test-2",
            source="ebay",
            source_id="456",
            title="Pikachu VMAX",
            category_raw="",
            price_eur=100.0,
        )

        assert obs1.compute_hash() != obs2.compute_hash()


class TestIdempotency:
    """Tests for idempotent behavior."""

    def test_observation_to_dict_includes_hash(self):
        """to_dict() should include content_hash."""
        obs = RawObservation(
            observation_id="test-1",
            source="ebay",
            source_id="123",
            title="Test Item",
            category_raw="",
        )

        d = obs.to_dict()

        assert 'content_hash' in d
        assert d['content_hash'] is not None
        assert len(d['content_hash']) == 16  # SHA256 truncated

    def test_from_market_observation(self):
        """Should create RawObservation from market_observations row."""
        row = {
            'provider': 'ebay',
            'source_id': '123456',
            'title': 'Pokemon Card',
            'category': 'Pokemon',
            'condition': 'Near Mint',
            'price': 50.0,
            'price_eur': 50.0,
            'currency': 'EUR',
            'is_sold': True,
            'observed_at': '2026-01-15T10:00:00Z',
            'image_url': 'https://example.com/image.jpg',
            'url': 'https://ebay.com/item/123456',
            'raw': {'original': 'data'},
        }

        obs = RawObservation.from_market_observation(row)

        assert obs.observation_id == "ebay-123456"
        assert obs.source == "ebay"
        assert obs.source_id == "123456"
        assert obs.title == "Pokemon Card"
        assert obs.price_eur == 50.0
        assert obs.is_sold is True


class TestTrainingCandidate:
    """Tests for TrainingCandidate creation."""

    def test_create_candidate(self):
        """Should create valid training candidate."""
        candidate = TrainingCandidate(
            candidate_id="cand-123",
            observation_id="obs-123",
            category_id="pokemon",
            subtype_id="graded",
            required_attrs={'title': 'Pikachu PSA 10'},
            price_q50=100.0,
            confidence=0.85,
        )

        d = candidate.to_dict()

        assert d['candidate_id'] == "cand-123"
        assert d['category_id'] == "pokemon"
        assert d['taxonomy_version'] == TAXONOMY_VERSION
        assert d['label_state'] == 'pending'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
