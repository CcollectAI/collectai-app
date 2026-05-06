"""
Google Shopping API client for CollectAI.

Thin wrapper around the SerpAPI Google Shopping endpoint providing:
- search()       -- search Google Shopping for product listings
- configured()   -- check if API key is set

Uses SerpAPI (https://serpapi.com) as the Google Shopping data provider.

Env vars:
    SERPAPI_API_KEY  - API key from serpapi.com
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import SERPAPI_API_KEY, SERPAPI_ENABLED
from app.lib.spend_tracker import spend_tracker, BudgetExceededError
from workers.circuit_breaker import google_shopping_circuit, CircuitOpenError

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 15.0
SERPAPI_BASE_URL = "https://serpapi.com/search"


# ---------------------------------------------------------------------------
# Lazy HTTP client
# ---------------------------------------------------------------------------

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
    return _http_client


def configured() -> bool:
    """Return True if SerpAPI API key is set."""
    return bool(SERPAPI_API_KEY)


async def close() -> None:
    """Close the shared HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def search(
    query: str,
    num: int = 10,
    gl: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Search Google Shopping via SerpAPI.

    Args:
        query: Search query string.
        num: Number of results to request (default: 10).
        gl: Country code for localised results (e.g. "us", "de", "jp").

    Returns:
        List of shopping_results dicts from SerpAPI, or empty list on failure.
    """
    if not configured():
        logger.debug("[GoogleShopping] Not configured (no SERPAPI_API_KEY)")
        return []

    # Killswitch — flip SERPAPI_ENABLED=false on EC2 when quota is
    # exhausted (Free tier = 250/mo, paid = pay-per-search). Without
    # this gate, every query goes through to SerpAPI, hits 429, gets
    # caught, and returns [] silently — no signal to the caller that
    # Google Shopping is offline. Mirror of FIRECRAWL_ENABLED /
    # SCRAPEDO_ENABLED. Confirmed needed 2026-05-01 (250/250 used).
    if not SERPAPI_ENABLED:
        logger.info("[GoogleShopping] disabled via SERPAPI_ENABLED=false")
        return []

    try:
        spend_tracker.check("serpapi")
    except BudgetExceededError:
        logger.warning("[GoogleShopping] call blocked by spend budget")
        return []

    try:
        google_shopping_circuit.check()
    except CircuitOpenError:
        logger.warning("[GoogleShopping] circuit open — skipping search")
        return []

    params: Dict[str, Any] = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": str(num),
    }
    if gl:
        params["gl"] = gl

    client = _get_client()
    try:
        resp = await client.get(SERPAPI_BASE_URL, params=params)
        if resp.status_code == 429:
            logger.warning("[GoogleShopping] Rate limited")
            google_shopping_circuit.record_failure()
            return []
        resp.raise_for_status()
        google_shopping_circuit.record_success()
        spend_tracker.record("serpapi")
        data = resp.json()
        return data.get("shopping_results", [])
    except httpx.HTTPStatusError as e:
        logger.error("[GoogleShopping] HTTP %d", e.response.status_code)
        google_shopping_circuit.record_failure()
        return []
    except Exception:
        logger.error("[GoogleShopping] search failed", exc_info=True)
        google_shopping_circuit.record_failure()
        return []
