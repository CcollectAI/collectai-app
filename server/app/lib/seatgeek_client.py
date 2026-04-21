"""
SeatGeek Search API client for CollectAI.

Parallels ticketmaster_client — thin async wrapper, circuit-breaker
gated, kill-switch via SEATGEEK_ENABLED. Used by
server/pipelines/seatgeek_events.py.

Docs: https://platform.seatgeek.com/
Auth: Client ID as `client_id` query param (Client Secret only needed
for write/OAuth endpoints, which we don't use).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import SEATGEEK_CLIENT_ID, SEATGEEK_ENABLED
from workers.circuit_breaker import seatgeek_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20.0
BASE_URL = "https://api.seatgeek.com/2"

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
    return _http_client


def configured() -> bool:
    return SEATGEEK_ENABLED and bool(SEATGEEK_CLIENT_ID)


async def close() -> None:
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


async def search_events(
    *,
    query: Optional[str] = None,
    taxonomy: Optional[str] = None,   # e.g. "concert", "sports"
    venue_city: Optional[str] = None,
    venue_country: Optional[str] = None,  # ISO-2 lowercase, e.g. "us"
    datetime_utc_gte: Optional[str] = None,  # ISO 8601
    datetime_utc_lte: Optional[str] = None,
    per_page: int = 50,
    page: int = 1,
) -> list[dict[str, Any]]:
    """Search SeatGeek /2/events. Returns raw event dicts (or [] on error/off)."""
    if not configured():
        return []

    try:
        seatgeek_circuit.check()
    except CircuitOpenError as e:
        logger.warning("[SeatGeek] circuit open — retry in %.0fs", e.retry_after)
        return []

    params: dict[str, Any] = {
        "client_id": SEATGEEK_CLIENT_ID,
        "per_page": per_page,
        "page": page,
    }
    if query:
        params["q"] = query
    if taxonomy:
        params["taxonomies.name"] = taxonomy
    if venue_city:
        params["venue.city"] = venue_city
    if venue_country:
        params["venue.country"] = venue_country
    if datetime_utc_gte:
        params["datetime_utc.gte"] = datetime_utc_gte
    if datetime_utc_lte:
        params["datetime_utc.lte"] = datetime_utc_lte

    url = f"{BASE_URL}/events"

    try:
        resp = await _get_client().get(url, params=params)
    except Exception as exc:
        seatgeek_circuit.record_failure()
        logger.error("[SeatGeek] network error: %r", exc)
        return []

    if resp.status_code == 429:
        seatgeek_circuit.record_failure()
        logger.warning("[SeatGeek] HTTP 429 rate limited")
        return []
    if resp.status_code == 403:
        seatgeek_circuit.record_failure()
        logger.error("[SeatGeek] HTTP 403 — client_id rejected")
        return []
    if resp.status_code != 200:
        seatgeek_circuit.record_failure()
        logger.error("[SeatGeek] HTTP %d for q=%r: %s", resp.status_code, query, resp.text[:200])
        return []

    seatgeek_circuit.record_success()

    try:
        data = resp.json()
    except Exception:
        logger.error("[SeatGeek] invalid JSON for q=%r", query)
        return []

    return data.get("events", []) or []
