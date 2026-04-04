"""
Scrape.do API client for CollectAI.

Thin wrapper around the Scrape.do REST API providing:
- scrape_url()   -- scrape a single URL to HTML/markdown via Scrape.do proxy
- configured()   -- check if API key is set

Scrape.do is a high-reliability web scraping proxy with 98% success rate,
anti-bot bypass (rotating proxies, headless rendering), and global coverage.

Env vars:
    SCRAPEDO_API_KEY  - API token from scrape.do
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import SCRAPEDO_API_KEY
from app.lib.spend_tracker import spend_tracker, BudgetExceededError
from workers.circuit_breaker import scrapedo_circuit, CircuitOpenError

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 30.0
SCRAPEDO_BASE_URL = "https://api.scrape.do"


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
    """Return True if Scrape.do API key is set."""
    return bool(SCRAPEDO_API_KEY)


async def close() -> None:
    """Close the shared HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_url(
    url: str,
    render: bool = True,
    super_proxy: bool = False,
) -> Optional[str]:
    """
    Scrape a single URL via Scrape.do proxy.

    Args:
        url: The URL to scrape.
        render: Whether to use headless browser rendering (default: True).
        super_proxy: Whether to use residential/super proxies for harder targets.

    Returns:
        HTML/text content of the page, or None on failure.
    """
    if not configured():
        logger.debug("[Scrape.do] Not configured (no SCRAPEDO_API_KEY)")
        return None

    try:
        spend_tracker.check("scrapedo")
    except BudgetExceededError:
        logger.warning("[Scrape.do] call blocked by spend budget")
        return None

    try:
        scrapedo_circuit.check()
    except CircuitOpenError:
        logger.warning("[Scrape.do] circuit open — skipping scrape")
        return None

    params: dict[str, Any] = {
        "token": SCRAPEDO_API_KEY,
        "url": url,
    }
    if render:
        params["render"] = "true"
    if super_proxy:
        params["super"] = "true"

    client = _get_client()
    try:
        resp = await client.get(
            SCRAPEDO_BASE_URL,
            params=params,
        )
        if resp.status_code == 429:
            logger.warning("[Scrape.do] Rate limited for %s", url)
            scrapedo_circuit.record_failure()
            return None
        resp.raise_for_status()
        scrapedo_circuit.record_success()
        spend_tracker.record("scrapedo")
        return resp.text
    except httpx.HTTPStatusError as e:
        logger.error("[Scrape.do] HTTP %d for %s", e.response.status_code, url)
        scrapedo_circuit.record_failure()
        return None
    except Exception:
        logger.error("[Scrape.do] scrape failed for %s", url, exc_info=True)
        scrapedo_circuit.record_failure()
        return None
