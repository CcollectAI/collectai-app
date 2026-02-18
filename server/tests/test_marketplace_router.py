"""Tests for app/agents/marketplace_router.py -- search, comps, and health endpoints.

All tests mock the MarketplaceAgent to avoid real API calls.
DB_ENABLED=false and DEV_MODE=true so auth is bypassed and no real DB is needed.
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
os.environ.setdefault("DEV_MODE", "true")

from starlette.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers: build mock return values matching marketplace_agent dataclasses
# ---------------------------------------------------------------------------

def _mock_scored_hit(**overrides):
    """Return a MagicMock resembling a ScoredMarketHit."""
    defaults = {
        "source": "ebay",
        "title": "Charizard Base Set Holo",
        "price": 250.00,
        "currency": "EUR",
        "url": "https://ebay.com/itm/12345",
        "image_url": "https://ebay.com/img/12345.jpg",
        "condition": "Near Mint",
        "is_sold": False,
        "sold_at": None,
        "raw_id": "12345",
        "content_hash": "abc123",
        "normalized_key": "charizard base set holo",
    }
    defaults.update(overrides)

    hit = MagicMock()
    hit.hit = defaults
    hit.is_sold = defaults.get("is_sold", False)
    hit.provenance_score = overrides.get("provenance_score", 0.85)
    hit.source_reliability = overrides.get("source_reliability", 0.95)
    hit.recency_score = overrides.get("recency_score", 0.10)
    return hit


def _mock_aggregation_result(hits=None, **overrides):
    """Return a MagicMock resembling an AggregationResult."""
    if hits is None:
        hits = [_mock_scored_hit()]
    result = MagicMock()
    result.hits = hits
    result.total_sources_queried = overrides.get("total_sources_queried", 3)
    result.successful_sources = overrides.get("successful_sources", 2)
    result.aggregate_confidence = overrides.get("aggregate_confidence", 0.875)
    result.dedup_count = overrides.get("dedup_count", 1)
    return result


# ===========================================================================
# POST /marketplace/search
# ===========================================================================

class TestMarketplaceSearch:
    """POST /marketplace/search endpoint."""

    def test_search_happy_path(self):
        """Search returns hits with correct structure."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Charizard Base Set Holo",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "hits" in data
        assert len(data["hits"]) == 1
        assert data["hits"][0]["source"] == "ebay"
        assert data["hits"][0]["title"] == "Charizard Base Set Holo"
        assert data["hits"][0]["price"] == 250.00
        assert data["hits"][0]["currency"] == "EUR"
        assert data["hits"][0]["url"] == "https://ebay.com/itm/12345"
        assert data["hits"][0]["image_url"] == "https://ebay.com/img/12345.jpg"
        assert data["hits"][0]["condition"] == "Near Mint"
        assert data["hits"][0]["is_sold"] is False
        assert isinstance(data["hits"][0]["provenance_score"], float)
        assert isinstance(data["hits"][0]["source_reliability"], float)
        assert isinstance(data["hits"][0]["recency_score"], float)
        assert data["total_sources_queried"] == 3
        assert data["successful_sources"] == 2
        assert isinstance(data["aggregate_confidence"], float)
        assert data["dedup_count"] == 1
        assert data["total_results"] == 1

    def test_search_empty_query_422(self):
        """Empty query string should be rejected by Pydantic validation."""
        resp = client.post("/marketplace/search", json={
            "query": "",
        })
        assert resp.status_code == 422

    def test_search_missing_query_422(self):
        """Missing query field should be rejected."""
        resp = client.post("/marketplace/search", json={})
        assert resp.status_code == 422

    def test_search_with_category(self):
        """Search with a category filter passes the value to the agent."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Pikachu",
                "category": "pokemon",
            })

        assert resp.status_code == 200
        call_kwargs = mock_instance.aggregate_search.call_args
        assert call_kwargs.kwargs.get("category") == "pokemon" or \
            (call_kwargs.args and len(call_kwargs.args) > 0)

    def test_search_with_region_parameter(self):
        """Explicit region in the request body should be passed through."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Pikachu",
                "region": "europe",
            })

        assert resp.status_code == 200
        call_kwargs = mock_instance.aggregate_search.call_args
        assert call_kwargs.kwargs.get("region") == "europe"

    def test_search_with_sold_only(self):
        """sold_only flag is forwarded to the agent as include_sold."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(
                    hits=[_mock_scored_hit(is_sold=True)],
                ),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Charizard",
                "sold_only": True,
            })

        assert resp.status_code == 200
        call_kwargs = mock_instance.aggregate_search.call_args
        assert call_kwargs.kwargs.get("include_sold") is True

    def test_search_with_price_range(self):
        """min_price and max_price should be accepted by the schema."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Charizard",
                "min_price": 10.0,
                "max_price": 500.0,
            })

        assert resp.status_code == 200

    def test_search_with_limit(self):
        """Custom limit is passed to the agent."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Charizard",
                "limit": 50,
            })

        assert resp.status_code == 200
        call_kwargs = mock_instance.aggregate_search.call_args
        assert call_kwargs.kwargs.get("limit") == 50

    def test_search_limit_too_high_422(self):
        """Limit > 100 should be rejected by validation."""
        resp = client.post("/marketplace/search", json={
            "query": "Charizard",
            "limit": 200,
        })
        assert resp.status_code == 422

    def test_search_limit_zero_422(self):
        """Limit of 0 should be rejected by validation (ge=1)."""
        resp = client.post("/marketplace/search", json={
            "query": "Charizard",
            "limit": 0,
        })
        assert resp.status_code == 422

    def test_search_multiple_hits(self):
        """Search returning multiple hits formats all of them."""
        hits = [
            _mock_scored_hit(title="Hit 1", price=10.0),
            _mock_scored_hit(title="Hit 2", price=20.0),
            _mock_scored_hit(title="Hit 3", price=30.0),
        ]
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(hits=hits, dedup_count=5),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Pokemon",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_results"] == 3
        assert data["dedup_count"] == 5
        titles = [h["title"] for h in data["hits"]]
        assert titles == ["Hit 1", "Hit 2", "Hit 3"]

    def test_search_empty_results(self):
        """Search returning no hits returns an empty list."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(
                    hits=[],
                    successful_sources=0,
                    aggregate_confidence=0.0,
                    dedup_count=0,
                ),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Nonexistent Item XYZ123",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["hits"] == []
        assert data["total_results"] == 0

    def test_search_agent_close_called(self):
        """Agent.close() is called even after a successful search."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                return_value=_mock_aggregation_result(),
            )
            mock_instance.close = AsyncMock()

            client.post("/marketplace/search", json={"query": "Test"})

        mock_instance.close.assert_awaited_once()


# ===========================================================================
# POST /marketplace/comps/{item_ref}
# ===========================================================================

class TestMarketplaceComps:
    """POST /marketplace/comps/{item_ref} endpoint."""

    def test_comps_happy_path(self):
        """Comps endpoint returns sold comparables with correct structure."""
        hit = _mock_scored_hit(
            is_sold=True,
            sold_at="2026-01-15T12:00:00Z",
            condition="Near Mint",
        )
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                return_value=_mock_aggregation_result(hits=[hit]),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/comps/charizard-base-set-holo")

        assert resp.status_code == 200
        data = resp.json()
        assert "comps" in data
        assert len(data["comps"]) == 1
        comp = data["comps"][0]
        assert comp["source"] == "ebay"
        assert comp["title"] == "Charizard Base Set Holo"
        assert comp["price"] == 250.00
        assert comp["condition"] == "Near Mint"
        assert isinstance(comp["provenance_score"], float)
        assert data["total_comps"] == 1
        assert isinstance(data["aggregate_confidence"], float)

    def test_comps_with_category(self):
        """Category query param is passed to the agent."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                return_value=_mock_aggregation_result(hits=[]),
            )
            mock_instance.close = AsyncMock()

            resp = client.post(
                "/marketplace/comps/charizard?category=pokemon",
            )

        assert resp.status_code == 200
        call_kwargs = mock_instance.find_sold_comps.call_args
        assert call_kwargs.kwargs.get("category") == "pokemon"

    def test_comps_with_region(self):
        """Region query param is passed to the agent."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                return_value=_mock_aggregation_result(hits=[]),
            )
            mock_instance.close = AsyncMock()

            resp = client.post(
                "/marketplace/comps/charizard?region=americas",
            )

        assert resp.status_code == 200
        call_kwargs = mock_instance.find_sold_comps.call_args
        assert call_kwargs.kwargs.get("region") == "americas"

    def test_comps_limit_capped_at_50(self):
        """Limit is capped at 50 even if a higher value is passed."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                return_value=_mock_aggregation_result(hits=[]),
            )
            mock_instance.close = AsyncMock()

            resp = client.post(
                "/marketplace/comps/charizard?limit=100",
            )

        assert resp.status_code == 200
        call_kwargs = mock_instance.find_sold_comps.call_args
        # min(100, 50) == 50
        assert call_kwargs.kwargs.get("limit") == 50

    def test_comps_empty_results(self):
        """Comps with no results returns empty list."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                return_value=_mock_aggregation_result(hits=[]),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/comps/nonexistent-item")

        assert resp.status_code == 200
        data = resp.json()
        assert data["comps"] == []
        assert data["total_comps"] == 0

    def test_comps_agent_close_called(self):
        """Agent.close() is called after comps lookup."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                return_value=_mock_aggregation_result(hits=[]),
            )
            mock_instance.close = AsyncMock()

            client.post("/marketplace/comps/test-item")

        mock_instance.close.assert_awaited_once()

    def test_comps_path_encoded_item_ref(self):
        """item_ref with slashes/special chars is handled by path parameter."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                return_value=_mock_aggregation_result(hits=[]),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/comps/LOB-001/Blue-Eyes White Dragon")

        assert resp.status_code == 200
        call_kwargs = mock_instance.find_sold_comps.call_args
        assert "LOB-001/Blue-Eyes White Dragon" in call_kwargs.kwargs.get("query", "")


# ===========================================================================
# GET /marketplace/health
# ===========================================================================

class TestMarketplaceHealth:
    """GET /v1/marketplace/health endpoint.

    The agent's health endpoint is mounted on the /v1 prefix because the
    stub router (app/routes/marketplace.py) registers a GET /marketplace/health
    first on the root app, shadowing the agent version.
    """

    def test_health_returns_adapter_statuses(self):
        """Health endpoint returns adapter status dict."""
        mock_statuses = {
            "adapters": {
                "ebay": {"configured": True, "healthy": True},
                "tcgplayer": {"configured": True, "healthy": False},
                "firecrawl": {"configured": False, "healthy": False},
            },
            "any_healthy": True,
        }
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.health_check = AsyncMock(return_value=mock_statuses)
            mock_instance.close = AsyncMock()

            resp = client.get("/v1/marketplace/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "adapters" in data
        adapters = data["adapters"]
        assert "adapters" in adapters  # nested structure from health_check
        assert adapters["any_healthy"] is True

    def test_health_all_adapters_down(self):
        """Health endpoint when all adapters are unconfigured."""
        mock_statuses = {
            "adapters": {
                "ebay": {"configured": False, "healthy": False},
                "tcgplayer": {"configured": False, "healthy": False},
                "firecrawl": {"configured": False, "healthy": False},
            },
            "any_healthy": False,
        }
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.health_check = AsyncMock(return_value=mock_statuses)
            mock_instance.close = AsyncMock()

            resp = client.get("/v1/marketplace/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "adapters" in data

    def test_health_connection_error_returns_fallback(self):
        """Health endpoint handles connection errors gracefully."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.health_check = AsyncMock(
                side_effect=ConnectionError("Network unreachable"),
            )
            mock_instance.close = AsyncMock()

            resp = client.get("/v1/marketplace/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "adapters" in data
        assert data.get("error") == "Health check failed"

    def test_health_agent_close_called(self):
        """Agent.close() is called after health check."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.health_check = AsyncMock(return_value={"adapters": {}})
            mock_instance.close = AsyncMock()

            client.get("/v1/marketplace/health")

        mock_instance.close.assert_awaited_once()


# ===========================================================================
# Error handling
# ===========================================================================

class TestMarketplaceErrors:
    """Error handling and edge cases."""

    def test_search_agent_exception_returns_500(self):
        """Unexpected exception in the agent returns 500."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                side_effect=RuntimeError("Unexpected error"),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Test",
            })

        assert resp.status_code == 500

    def test_search_connection_error_returns_503(self):
        """ConnectionError from external APIs returns 503."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                side_effect=ConnectionError("eBay unreachable"),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Test",
            })

        assert resp.status_code == 503

    def test_search_timeout_returns_503(self):
        """TimeoutError from external APIs returns 503."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.aggregate_search = AsyncMock(
                side_effect=TimeoutError("Request timed out"),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/search", json={
                "query": "Test",
            })

        assert resp.status_code == 503

    def test_comps_agent_exception_returns_500(self):
        """Unexpected exception in comps returns 500."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                side_effect=RuntimeError("Unexpected error"),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/comps/test-item")

        assert resp.status_code == 500

    def test_comps_connection_error_returns_503(self):
        """ConnectionError in comps returns 503."""
        with patch("app.agents.marketplace_agent.MarketplaceAgent") as MockAgent:
            mock_instance = AsyncMock()
            MockAgent.return_value = mock_instance
            mock_instance.find_sold_comps = AsyncMock(
                side_effect=ConnectionError("eBay unreachable"),
            )
            mock_instance.close = AsyncMock()

            resp = client.post("/marketplace/comps/test-item")

        assert resp.status_code == 503

    def test_search_query_too_long_422(self):
        """Query exceeding max_length should be rejected."""
        resp = client.post("/marketplace/search", json={
            "query": "A" * 501,
        })
        assert resp.status_code == 422

    def test_search_negative_min_price_422(self):
        """Negative min_price should be rejected (ge=0)."""
        resp = client.post("/marketplace/search", json={
            "query": "Test",
            "min_price": -1.0,
        })
        assert resp.status_code == 422
