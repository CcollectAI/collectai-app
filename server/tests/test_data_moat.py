"""Tests for data moat features: supply tracking, recency weighting, verified sales, demand signals."""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Price Recency Weighting (Item 15)
# ---------------------------------------------------------------------------

class TestRecencyWeights:
    """Tests for compute_recency_weights in train_price.py."""

    def test_no_timestamps_get_neutral_weight(self):
        from pipelines.train_price import compute_recency_weights
        features = [{"condition_score": 0.8}, {"rarity_score": 0.5}]
        weights = compute_recency_weights(features)
        assert len(weights) == 2
        assert all(w == 0.5 for w in weights)

    def test_recent_observation_gets_high_weight(self):
        from pipelines.train_price import compute_recency_weights
        now_iso = datetime.now(timezone.utc).isoformat()
        features = [{"condition_score": 0.8, "observed_at": now_iso}]
        weights = compute_recency_weights(features)
        assert weights[0] > 0.9  # Very recent → near 1.0

    def test_old_observation_gets_low_weight(self):
        from pipelines.train_price import compute_recency_weights
        old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        features = [{"condition_score": 0.8, "observed_at": old}]
        weights = compute_recency_weights(features, half_life_days=90.0)
        assert weights[0] < 0.3  # 365 days old with 90-day half-life → ~0.06

    def test_verified_sale_gets_2x_bonus(self):
        from pipelines.train_price import compute_recency_weights
        now_iso = datetime.now(timezone.utc).isoformat()
        features = [
            {"observed_at": now_iso, "source": "verified_sale"},
            {"observed_at": now_iso},
        ]
        weights = compute_recency_weights(features)
        # First should be ~2x the second
        assert weights[0] > weights[1] * 1.8

    def test_half_life_90_days(self):
        from pipelines.train_price import compute_recency_weights
        t90 = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        features = [{"observed_at": t90}]
        weights = compute_recency_weights(features, half_life_days=90.0)
        # At exactly 1 half-life, weight should be ~0.5
        assert abs(weights[0] - 0.5) < 0.05

    def test_invalid_timestamp_gets_neutral_weight(self):
        from pipelines.train_price import compute_recency_weights
        features = [{"observed_at": "not-a-date"}]
        weights = compute_recency_weights(features)
        assert weights[0] == 0.5

    def test_future_timestamp_clamped_to_max_1(self):
        from pipelines.train_price import compute_recency_weights
        future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        features = [{"observed_at": future}]
        weights = compute_recency_weights(features)
        # Future dates should be clamped: age_days = 0 → weight = 1.0
        assert weights[0] <= 1.0  # Must not exceed 1.0 (was a bug before fix)

    def test_minimum_weight_is_0_1(self):
        from pipelines.train_price import compute_recency_weights
        very_old = (datetime.now(timezone.utc) - timedelta(days=3650)).isoformat()
        features = [{"observed_at": very_old}]
        weights = compute_recency_weights(features, half_life_days=90.0)
        assert weights[0] >= 0.1


# ---------------------------------------------------------------------------
# Verified Sales Loading (Item 16 - training integration)
# ---------------------------------------------------------------------------

class TestVerifiedSalesLoading:
    """Tests for load_verified_sales in train_price.py."""

    def test_returns_empty_without_supabase(self):
        from pipelines.train_price import load_verified_sales
        # No SUPABASE_URL/SUPABASE_SERVICE_KEY → empty
        features, prices = load_verified_sales("pokemon")
        assert features == []
        assert prices == []

    def test_features_include_source_marker(self):
        """Verified sales should have source='verified_sale' for recency 2x bonus."""
        from pipelines.train_price import load_verified_sales
        # Can't test actual Supabase call, but verify the contract
        # is documented in the function
        import inspect
        src = inspect.getsource(load_verified_sales)
        assert '"source": "verified_sale"' in src or "'source': 'verified_sale'" in src


# ---------------------------------------------------------------------------
# Verified Sale Endpoint (Item 16 - API)
# ---------------------------------------------------------------------------

class TestVerifiedSaleEndpoint:
    """Tests for POST /feedback/verified-sale."""

    def test_verified_sale_offline_mode(self):
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/feedback/verified-sale", json={
            "item_id": "00000000-0000-0000-0000-000000000001",
            "sale_price": 150.0,
            "currency": "EUR",
            "platform": "eBay",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "offline" in data["message"].lower()

    def test_verified_sale_negative_price_rejected(self):
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/feedback/verified-sale", json={
            "item_id": "00000000-0000-0000-0000-000000000001",
            "sale_price": -10.0,
        })
        assert resp.status_code == 422  # Pydantic validation

    def test_verified_sale_zero_price_rejected(self):
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/feedback/verified-sale", json={
            "item_id": "00000000-0000-0000-0000-000000000001",
            "sale_price": 0,
        })
        assert resp.status_code == 422

    def test_verified_sale_with_all_fields(self):
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/feedback/verified-sale", json={
            "item_id": "00000000-0000-0000-0000-000000000001",
            "sale_price": 250.0,
            "currency": "USD",
            "platform": "Mercari",
            "condition": "Near Mint",
            "sold_at": "2026-02-15T10:00:00Z",
            "notes": "Sold at local convention",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_verified_sale_invalid_currency_rejected(self):
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/feedback/verified-sale", json={
            "item_id": "00000000-0000-0000-0000-000000000001",
            "sale_price": 100.0,
            "currency": "XYZ",
        })
        assert resp.status_code == 400

    def test_verified_sale_future_date_rejected(self):
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/feedback/verified-sale", json={
            "item_id": "00000000-0000-0000-0000-000000000001",
            "sale_price": 100.0,
            "sold_at": "2030-01-01T00:00:00Z",
        })
        assert resp.status_code == 400

    def test_verified_sale_price_cap(self):
        from starlette.testclient import TestClient
        from main import app
        client = TestClient(app)

        resp = client.post("/feedback/verified-sale", json={
            "item_id": "00000000-0000-0000-0000-000000000001",
            "sale_price": 2_000_000,
        })
        assert resp.status_code == 422  # Exceeds le=1_000_000


# ---------------------------------------------------------------------------
# Demand Signal Recording (Item 17)
# ---------------------------------------------------------------------------

class TestDemandSignals:
    """Tests for demand signal helper functions."""

    @pytest.mark.asyncio
    async def test_record_demand_signal_no_db(self):
        from app.features.data_moat import record_demand_signal
        result = await record_demand_signal(
            signal_type="mandate_created",
            category="pokemon",
            item_key="charizard",
            user_id=None,
        )
        assert result is False  # No DB pool

    @pytest.mark.asyncio
    async def test_invalid_signal_type_rejected(self):
        from app.features.data_moat import record_demand_signal
        result = await record_demand_signal(
            signal_type="invalid_type",
            category="pokemon",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_record_supply_snapshot_no_db(self):
        from app.features.data_moat import record_supply_snapshot
        result = await record_supply_snapshot(
            category="pokemon",
            item_key="base-set-charizard",
            listing_count=15,
            avg_price_eur=350.0,
        )
        assert result is False  # No DB pool

    @pytest.mark.asyncio
    async def test_get_supply_trend_no_db(self):
        from app.features.data_moat import get_supply_trend
        result = await get_supply_trend("pokemon", "charizard", days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_demand_heat_no_db(self):
        from app.features.data_moat import get_demand_heat
        result = await get_demand_heat(category="pokemon")
        assert result == []


# ---------------------------------------------------------------------------
# Ridge training with sample_weight (integration)
# ---------------------------------------------------------------------------

class TestWeightedTraining:
    """Test that train_ridge_model accepts sample weights."""

    def test_training_with_recency_weights(self):
        from pipelines.train_price import train_ridge_model
        features = [
            {"condition_score": 0.9, "rarity_score": 0.8, "edition_score": 0.7,
             "observed_at": datetime.now(timezone.utc).isoformat()},
            {"condition_score": 0.5, "rarity_score": 0.3, "edition_score": 0.2,
             "observed_at": (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()},
        ] * 20  # Need enough samples for Ridge
        prices = [100.0, 30.0] * 20

        model = train_ridge_model(
            "test_cat", features, prices, "test_v1",
            alpha=1.0, use_recency_weights=True,
        )
        assert model.train_size == 40
        assert model.category == "test_cat"

    def test_training_without_recency_weights(self):
        from pipelines.train_price import train_ridge_model
        features = [
            {"condition_score": 0.9, "rarity_score": 0.8, "edition_score": 0.7},
            {"condition_score": 0.5, "rarity_score": 0.3, "edition_score": 0.2},
        ] * 20
        prices = [100.0, 30.0] * 20

        model = train_ridge_model(
            "test_cat", features, prices, "test_v1",
            alpha=1.0, use_recency_weights=False,
        )
        assert model.train_size == 40


# ---------------------------------------------------------------------------
# Supply snapshot wiring in deal discovery (Item 14)
# ---------------------------------------------------------------------------

class TestSupplySnapshotWiring:
    """Test that supply snapshot recording is wired into deal discovery."""

    def test_deal_discovery_agent_has_supply_snapshot_call(self):
        """Verify the supply snapshot call exists in deal_discovery_agent.py."""
        import inspect
        from app.agents.deal_discovery_agent import DealDiscoveryAgent
        src = inspect.getsource(DealDiscoveryAgent)
        assert "record_supply_snapshot" in src

    def test_mandate_creation_has_demand_signal(self):
        """Verify mandate creation records a demand signal."""
        import inspect
        from app.agents import purchase_router
        src = inspect.getsource(purchase_router.create_mandate)
        assert "record_demand_signal" in src
