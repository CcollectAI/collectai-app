"""
Etsy Open API v3 client for CollectAI.

Thin wrapper around the Etsy Open API v3 providing:
- search_listings()  -- search active listings by keyword
- configured()       -- check if API key is set

Etsy is a large marketplace for handmade, vintage, and craft items
including watches, pens, vintage toys, cameras, keycaps, and more.

Env vars:
    ETSY_API_KEY  - Etsy Open API v3 key (x-api-key header)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import ETSY_API_KEY
from workers.circuit_breaker import etsy_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

ETSY_BASE_URL = "https://openapi.etsy.com/v3"
DEFAULT_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Lazy HTTP client
# ---------------------------------------------------------------------------

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={
                "x-api-key": ETSY_API_KEY,
                "Accept": "application/json",
            },
        )
    return _http_client


def configured() -> bool:
    """Return True if the Etsy API key is set."""
    return bool(ETSY_API_KEY)


async def close() -> None:
    """Close the shared HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def search_listings(
    query: str,
    limit: int = 25,
    sort_on: str = "score",
) -> List[Dict[str, Any]]:
    """Search Etsy active listings.

    Parameters
    ----------
    query : str
        Keywords to search for.
    limit : int
        Maximum number of results (capped at 100 by Etsy).
    sort_on : str
        Sort order — "score" (relevance), "created", "price", "updated".

    Returns
    -------
    list[dict]
        Raw listing dicts from the Etsy API ``results`` array.
    """
    if not configured():
        logger.debug("Etsy not configured — skipping search")
        return []

    try:
        etsy_circuit.check()
    except CircuitOpenError:
        logger.warning("Etsy circuit open — skipping")
        return []

    try:
        client = _get_client()
        resp = await client.get(
            f"{ETSY_BASE_URL}/application/listings/active",
            params={
                "keywords": query,
                "limit": str(min(limit, 100)),
                "sort_on": sort_on,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        etsy_circuit.record_success()
        return data.get("results", [])

    except Exception as exc:
        etsy_circuit.record_failure()
        logger.warning("Etsy search error: %s", exc)
        return []
