"""
Tests for app/agents/adapters/bezel_caller.py — Bezel watch marketplace adapter.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workers.circuit_breaker import bezel_circuit


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeListing:
    """Tests for _normalize_listing()."""

    def test_basic_normalization(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        item = {
            "id": "abc123",
            "brand": "Rolex",
            "model": "Submariner",
            "referenceNumber": "116610LN",
            "price": 12500.00,
            "imageUrl": "https://img.getbezel.com/sub.jpg",
            "condition": "Excellent",
            "slug": "rolex-submariner-abc123",
        }
        hit = _normalize_listing(item)
        assert hit["source"] == "bezel"
        assert hit["raw_id"] == "bezel-abc123"
        assert "Rolex" in hit["title"]
        assert "Submariner" in hit["title"]
        assert "116610LN" in hit["title"]
        assert hit["price"] == 12500.00
        assert hit["currency"] == "USD"
        assert hit["image_url"] == "https://img.getbezel.com/sub.jpg"
        assert hit["condition"] == "Excellent"
        assert hit["is_sold"] is False
        assert "getbezel.com/listing" in hit["url"]

    def test_sold_listing(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        item = {
            "id": "sold456",
            "brand": "Omega",
            "model": "Speedmaster",
            "price": 5800,
            "soldAt": "2026-02-15T10:00:00Z",
        }
        hit = _normalize_listing(item, is_sold=True)
        assert hit["is_sold"] is True
        assert hit["sold_at"] == "2026-02-15T10:00:00Z"
        assert hit["source"] == "bezel"

    def test_nested_price_object(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        item = {
            "id": "nested1",
            "title": "Tag Heuer Carrera",
            "price": {"amount": 3200, "currency": "USD"},
        }
        hit = _normalize_listing(item)
        assert hit["price"] == 3200.0

    def test_title_fallback(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        item = {"id": "x1", "title": "Custom Watch Title"}
        hit = _normalize_listing(item)
        assert hit["title"] == "Custom Watch Title"

    def test_empty_item(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        hit = _normalize_listing({})
        assert hit["source"] == "bezel"
        assert hit["raw_id"] == "bezel-"
        assert hit["price"] == 0.0

    def test_condition_dict(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        item = {"id": "c1", "condition": {"label": "Very Good", "name": "VG"}}
        hit = _normalize_listing(item)
        assert hit["condition"] == "Very Good"

    def test_images_list(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        item = {
            "id": "img1",
            "images": [{"url": "https://example.com/watch1.jpg"}],
        }
        hit = _normalize_listing(item)
        assert hit["image_url"] == "https://example.com/watch1.jpg"

    def test_title_truncation(self):
        from app.agents.adapters.bezel_caller import _normalize_listing

        item = {"id": "long", "title": "A" * 600}
        hit = _normalize_listing(item)
        assert len(hit["title"]) <= 500


# ---------------------------------------------------------------------------
# BezelCaller class tests
# ---------------------------------------------------------------------------

class TestBezelCaller:
    """Tests for the BezelCaller class."""

    def test_configured_default(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        caller = BezelCaller(enabled=True)
        assert caller.configured is True

    def test_not_configured(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        caller = BezelCaller(enabled=False)
        assert caller.configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        caller = BezelCaller(enabled=False)
        results = await caller.search("Rolex Submariner")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_returns_empty_when_not_configured(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        caller = BezelCaller(enabled=False)
        results = await caller.sold_comps("Omega Speedmaster")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_api_success(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        bezel_circuit.reset()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "listings": [
                {
                    "id": "bz-001",
                    "brand": "Rolex",
                    "model": "Daytona",
                    "price": 35000,
                    "imageUrl": "https://img.getbezel.com/daytona.jpg",
                    "condition": "Excellent",
                    "slug": "rolex-daytona-bz001",
                },
                {
                    "id": "bz-002",
                    "brand": "Omega",
                    "model": "Seamaster",
                    "price": 4500,
                    "condition": "Good",
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = BezelCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Rolex", limit=5)
        assert len(results) == 2
        assert results[0]["source"] == "bezel"
        assert results[0]["raw_id"] == "bezel-bz-001"
        assert results[0]["price"] == 35000
        assert results[1]["price"] == 4500

    @pytest.mark.asyncio
    async def test_search_falls_back_to_scrape(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        bezel_circuit.reset()

        # First call returns 403 (API blocked), second returns HTML
        responses = [
            MagicMock(status_code=403),
            MagicMock(
                status_code=200,
                text='<a href="/listing/bezel-watch-123">Watch</a> $5,500.00 <a href="/listing/bezel-watch-456">Watch 2</a> $3,200.00',
            ),
        ]
        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            resp = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.is_closed = False

        caller = BezelCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("watch")
        assert len(results) == 2
        assert results[0]["raw_id"] == "bezel-bezel-watch-123"
        assert results[0]["price"] == 5500.00

    @pytest.mark.asyncio
    async def test_search_handles_exception(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        bezel_circuit.reset()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection timeout"))
        mock_client.is_closed = False

        caller = BezelCaller(enabled=True)
        caller._http = mock_client

        results = await caller.search("Rolex")
        assert results == []

    @pytest.mark.asyncio
    async def test_sold_comps_with_api_success(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        bezel_circuit.reset()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "listings": [
                {
                    "id": "sold-1",
                    "brand": "Tudor",
                    "model": "Black Bay",
                    "price": 3200,
                    "soldAt": "2026-02-20T15:30:00Z",
                },
            ]
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = BezelCaller(enabled=True)
        caller._http = mock_client

        results = await caller.sold_comps("Tudor Black Bay")
        assert len(results) == 1
        assert results[0]["is_sold"] is True
        assert results[0]["sold_at"] == "2026-02-20T15:30:00Z"

    @pytest.mark.asyncio
    async def test_health_check_not_configured(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        caller = BezelCaller(enabled=False)
        healthy = await caller.health_check()
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        caller = BezelCaller(enabled=True)
        caller._http = mock_client

        healthy = await caller.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_close(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        mock_client = AsyncMock()
        mock_client.is_closed = False

        caller = BezelCaller(enabled=True)
        caller._http = mock_client

        await caller.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self):
        from app.agents.adapters.bezel_caller import BezelCaller

        # Trip the circuit breaker
        for _ in range(10):
            bezel_circuit.record_failure()

        caller = BezelCaller(enabled=True)
        results = await caller.search("anything")
        assert results == []

        # Reset for other tests
        bezel_circuit.reset()


# ---------------------------------------------------------------------------
# Constants / module-level tests
# ---------------------------------------------------------------------------

class TestBezelConstants:
    """Tests for module-level constants."""

    def test_supported_categories(self):
        from app.agents.adapters.bezel_caller import SUPPORTED_CATEGORIES

        assert "watches" in SUPPORTED_CATEGORIES

    def test_reliability_scores(self):
        from app.agents.adapters.bezel_caller import BEZEL_SOURCE_RELIABILITY, BEZEL_SOLD_RELIABILITY

        assert BEZEL_SOURCE_RELIABILITY == 0.80
        assert BEZEL_SOLD_RELIABILITY == 0.85
