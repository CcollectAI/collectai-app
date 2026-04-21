"""
Ticketmaster Discovery API client for CollectAI.

Thin async wrapper around the Discovery API's /events.json endpoint.
Used by server/pipelines/ticketmaster_events.py to surface
collectible-relevant events (conventions, card shows, signings,
concerts driving merch demand) into the events table.

Docs: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/

Auth: Consumer Key passed as `apikey` query param. No OAuth needed
for Discovery endpoints. The Consumer Secret is stored but unused
until we add any Partner/Commerce API calls.

Quota: free tier = 5,000 calls/day, 5 calls/sec. Callers must
self-throttle; this client does not enforce QPS internally.

Env vars:
    TICKETMASTER_API_KEY        — Consumer Key (required)
    TICKETMASTER_CONSUMER_SECRET — unused by Discovery API, stored for later
    TICKETMASTER_ENABLED         — kill-switch (default true)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import (
    TICKETMASTER_API_KEY,
    TICKETMASTER_ENABLED,
)
from workers.circuit_breaker import ticketmaster_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20.0
BASE_URL = "https://app.ticketmaster.com/discovery/v2"


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
    """Return True if Ticketmaster is enabled and API key is set."""
    return TICKETMASTER_ENABLED and bool(TICKETMASTER_API_KEY)


async def close() -> None:
    """Close the shared HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---------------------------------------------------------------------------
# Discovery API: events search
# ---------------------------------------------------------------------------

async def search_events(
    *,
    keyword: Optional[str] = None,
    classification_name: Optional[str] = None,
    country_code: Optional[str] = None,
    start_date_time: Optional[str] = None,  # ISO8601, e.g. 2026-04-21T00:00:00Z
    end_date_time: Optional[str] = None,
    size: int = 50,
    page: int = 0,
) -> list[dict[str, Any]]:
    """Search the Discovery API for events matching the given criteria.

    Returns the raw event dicts from `_embedded.events` (empty list on
    no results or circuit-open). Caller is responsible for mapping to
    ScrapedEvent and rate-limiting (Ticketmaster allows 5 calls/sec).
    """
    if not configured():
        logger.debug("[Ticketmaster] not configured — skipping")
        return []

    try:
        ticketmaster_circuit.check()
    except CircuitOpenError as e:
        logger.warning("[Ticketmaster] circuit open — retry in %.0fs", e.retry_after)
        return []

    params: dict[str, Any] = {
        "apikey": TICKETMASTER_API_KEY,
        "size": size,
        "page": page,
    }
    if keyword:
        params["keyword"] = keyword
    if classification_name:
        params["classificationName"] = classification_name
    if country_code:
        params["countryCode"] = country_code
    if start_date_time:
        params["startDateTime"] = start_date_time
    if end_date_time:
        params["endDateTime"] = end_date_time

    url = f"{BASE_URL}/events.json"

    try:
        resp = await _get_client().get(url, params=params)
    except Exception as exc:
        ticketmaster_circuit.record_failure()
        logger.error("[Ticketmaster] network error: %r", exc)
        return []

    if resp.status_code == 429:
        ticketmaster_circuit.record_failure()
        logger.warning("[Ticketmaster] HTTP 429 rate limited — backing off")
        return []
    if resp.status_code == 401:
        ticketmaster_circuit.record_failure()
        logger.error("[Ticketmaster] HTTP 401 — invalid or disabled API key")
        return []
    if resp.status_code != 200:
        ticketmaster_circuit.record_failure()
        logger.error(
            "[Ticketmaster] HTTP %d for keyword=%r: %s",
            resp.status_code, keyword, resp.text[:200],
        )
        return []

    ticketmaster_circuit.record_success()

    try:
        data = resp.json()
    except Exception:
        logger.error("[Ticketmaster] invalid JSON response for keyword=%r", keyword)
        return []

    events = data.get("_embedded", {}).get("events", []) or []
    return events
