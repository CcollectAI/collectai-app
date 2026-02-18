"""Tests for circuit breaker integration in marketplace adapters.

Verifies that EbayCaller and TCGPlayerCaller correctly interact with their
respective circuit breakers:
  - check() is called before HTTP requests
  - record_failure() is called on HTTP errors
  - record_success() is called on successful responses
  - search() returns [] when circuit is OPEN (no HTTP call made)
  - .configured returns False when credentials are missing

Uses unittest.mock to patch httpx responses and circuit breaker instances,
so no real HTTP calls or API credentials are needed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import httpx
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_ENABLED", "false")
os.environ.setdefault("DATABASE_URL", "mock://localhost")
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from workers.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    ebay_circuit,
    tcgplayer_circuit,
)


@pytest.fixture(autouse=True)
def _reset_circuits():
    """Reset global circuit breakers between tests."""
    ebay_circuit.reset()
    tcgplayer_circuit.reset()
    yield
    ebay_circuit.reset()
    tcgplayer_circuit.reset()


# ---------------------------------------------------------------------------
# Helper: build a fake httpx.Response
# ---------------------------------------------------------------------------

def _fake_response(status_code: int = 200, json_body: dict | None = None) -> httpx.Response:
    """Build a minimal httpx.Response for mocking."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_body or {},
        request=httpx.Request("GET", "https://fake.example.com"),
    )
    return resp


# ===========================================================================
# EbayCaller — circuit breaker integration
# ===========================================================================

class TestEbayCallerCircuit:
    """Verify EbayCaller.search() integrates with ebay_circuit."""

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.ebay_caller import EbayCaller
        return EbayCaller(client_id="test-id", client_secret="test-secret")

    @pytest.mark.asyncio
    async def test_search_calls_circuit_check_before_http(self, caller):
        """search() should call ebay_circuit.check() before making any HTTP request."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        # OAuth token response
        oauth_resp = _fake_response(200, {"access_token": "tok", "expires_in": 3600})
        # Browse API response
        browse_resp = _fake_response(200, {"itemSummaries": []})
        mock_client.post = AsyncMock(return_value=oauth_resp)
        mock_client.get = AsyncMock(return_value=browse_resp)
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.ebay_circuit.check") as mock_check:
            with patch("workers.circuit_breaker.ebay_circuit.record_success") as mock_success:
                result = await caller.search("test query")

        mock_check.assert_called_once()
        mock_success.assert_called_once()
        assert result == []  # no itemSummaries

    @pytest.mark.asyncio
    async def test_search_records_failure_on_http_error(self, caller):
        """search() should call record_failure() when HTTP request fails."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        # OAuth succeeds
        oauth_resp = _fake_response(200, {"access_token": "tok", "expires_in": 3600})
        mock_client.post = AsyncMock(return_value=oauth_resp)
        # Browse API returns 500
        error_resp = _fake_response(500, {"error": "server error"})
        mock_client.get = AsyncMock(return_value=error_resp)
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.ebay_circuit.record_failure") as mock_fail:
            result = await caller.search("test query")

        mock_fail.assert_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_records_success_on_good_response(self, caller):
        """search() should call record_success() on a successful response."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        oauth_resp = _fake_response(200, {"access_token": "tok", "expires_in": 3600})
        browse_resp = _fake_response(200, {
            "itemSummaries": [
                {"itemId": "v1|123", "title": "Test Card", "price": {"value": "10.00", "currency": "USD"}},
            ]
        })
        mock_client.post = AsyncMock(return_value=oauth_resp)
        mock_client.get = AsyncMock(return_value=browse_resp)
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.ebay_circuit.record_success") as mock_success:
            result = await caller.search("test query")

        mock_success.assert_called_once()
        assert len(result) == 1
        assert result[0]["source"] == "ebay"

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_circuit_open(self, caller):
        """When ebay_circuit is OPEN, search() should return [] without HTTP."""
        # Trip the circuit
        for _ in range(5):
            ebay_circuit.record_failure()
        assert ebay_circuit.state == CircuitState.OPEN

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.search("test query")

        assert result == []
        # No HTTP calls should have been made
        mock_client.get.assert_not_called()
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_records_failure_on_rate_limit(self, caller):
        """429 responses should record a failure on the circuit."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        oauth_resp = _fake_response(200, {"access_token": "tok", "expires_in": 3600})
        rate_limited = _fake_response(429)
        mock_client.post = AsyncMock(return_value=oauth_resp)
        mock_client.get = AsyncMock(return_value=rate_limited)
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.ebay_circuit.record_failure") as mock_fail:
            result = await caller.search("test query")

        mock_fail.assert_called_once()
        assert result == []

    def test_configured_false_when_missing_credentials(self):
        """EbayCaller.configured should be False when client_id or secret is empty."""
        from app.agents.adapters.ebay_caller import EbayCaller

        caller_no_id = EbayCaller(client_id="", client_secret="some-secret")
        assert caller_no_id.configured is False

        caller_no_secret = EbayCaller(client_id="some-id", client_secret="")
        assert caller_no_secret.configured is False

        caller_both_empty = EbayCaller(client_id="", client_secret="")
        assert caller_both_empty.configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        """Unconfigured caller should return [] immediately."""
        from app.agents.adapters.ebay_caller import EbayCaller

        caller = EbayCaller(client_id="", client_secret="")
        assert caller.configured is False
        result = await caller.search("anything")
        assert result == []


# ===========================================================================
# TCGPlayerCaller — circuit breaker integration
# ===========================================================================

class TestTCGPlayerCallerCircuit:
    """Verify TCGPlayerCaller.search() integrates with tcgplayer_circuit."""

    @pytest.fixture()
    def caller(self):
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller
        return TCGPlayerCaller(bearer_token="test-bearer-token")

    @pytest.mark.asyncio
    async def test_search_calls_circuit_check_before_http(self, caller):
        """search() should call tcgplayer_circuit.check() before HTTP request."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        catalog_resp = _fake_response(200, {"results": []})
        mock_client.get = AsyncMock(return_value=catalog_resp)
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.tcgplayer_circuit.check") as mock_check:
            with patch("workers.circuit_breaker.tcgplayer_circuit.record_success") as mock_success:
                result = await caller.search("test query", category="pokemon")

        mock_check.assert_called_once()
        mock_success.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_records_failure_on_http_error(self, caller):
        """search() should call record_failure() when HTTP request fails."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        error_resp = _fake_response(500, {"error": "server error"})
        mock_client.get = AsyncMock(return_value=error_resp)
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.tcgplayer_circuit.record_failure") as mock_fail:
            result = await caller.search("test query", category="pokemon")

        mock_fail.assert_called()
        assert result == []

    @pytest.mark.asyncio
    async def test_search_records_success_on_good_response(self, caller):
        """search() should call record_success() on a successful response."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        catalog_resp = _fake_response(200, {
            "results": [
                {"productId": 12345, "name": "Charizard V", "url": "/product/12345"},
            ]
        })
        # Second call for price fetch
        price_resp = _fake_response(200, {
            "results": [
                {"productId": 12345, "marketPrice": 55.0, "subTypeName": "Normal"},
            ]
        })
        mock_client.get = AsyncMock(side_effect=[catalog_resp, price_resp])
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.tcgplayer_circuit.record_success") as mock_success:
            result = await caller.search("Charizard", category="pokemon")

        mock_success.assert_called_once()
        assert len(result) == 1
        assert result[0]["source"] == "tcgplayer"

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_circuit_open(self, caller):
        """When tcgplayer_circuit is OPEN, search() returns [] without HTTP."""
        # Trip the circuit
        for _ in range(5):
            tcgplayer_circuit.record_failure()
        assert tcgplayer_circuit.state == CircuitState.OPEN

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        caller._http = mock_client

        result = await caller.search("test query", category="pokemon")

        assert result == []
        mock_client.get.assert_not_called()

    def test_configured_false_when_token_missing(self):
        """TCGPlayerCaller.configured should be False when bearer_token is empty."""
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller

        caller_empty = TCGPlayerCaller(bearer_token="")
        assert caller_empty.configured is False

        caller_none = TCGPlayerCaller(bearer_token=None)
        assert caller_none.configured is False

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_not_configured(self):
        """Unconfigured caller should return [] immediately."""
        from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller

        caller = TCGPlayerCaller(bearer_token="")
        assert caller.configured is False
        result = await caller.search("anything", category="pokemon")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_records_failure_on_request_error(self, caller):
        """Network-level errors (httpx.RequestError) should record a failure."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.is_closed = False

        caller._http = mock_client

        with patch("workers.circuit_breaker.tcgplayer_circuit.record_failure") as mock_fail:
            result = await caller.search("test", category="pokemon")

        mock_fail.assert_called()
        assert result == []


# ===========================================================================
# Cross-adapter: circuit state isolation
# ===========================================================================

class TestCircuitIsolation:
    """Verify that eBay and TCGPlayer circuits are independent."""

    def test_tripping_ebay_does_not_affect_tcgplayer(self):
        """Failures on ebay_circuit should not open tcgplayer_circuit."""
        for _ in range(5):
            ebay_circuit.record_failure()

        assert ebay_circuit.state == CircuitState.OPEN
        assert tcgplayer_circuit.state == CircuitState.CLOSED

    def test_tripping_tcgplayer_does_not_affect_ebay(self):
        """Failures on tcgplayer_circuit should not open ebay_circuit."""
        for _ in range(5):
            tcgplayer_circuit.record_failure()

        assert tcgplayer_circuit.state == CircuitState.OPEN
        assert ebay_circuit.state == CircuitState.CLOSED
