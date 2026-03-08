"""
Portfolio router.

Provides portfolio summary (from in-memory demo items) and proxy
endpoints to the Signals micro-service for overview, items, and
timeseries data.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends

from app.auth import require_api_key
from app.errors import error_response
from app.config import API_SHARED_SECRET, SIGNALS_BASE_URL
from app.rate_limit import per_user_rate_limit

router = APIRouter(tags=["portfolio"])

_logger = logging.getLogger(__name__)

# Per-user: 20 requests per minute for portfolio endpoints
_portfolio_user_limit = per_user_rate_limit(20, scope="portfolio")

# Module-level httpx client — created lazily, closed by lifespan shutdown
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


async def close_http_client() -> None:
    """Close the module-level httpx client. Called during app shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---- Helpers ----

async def _proxy_signals(path: str) -> dict:
    """Proxy a request to the Signals service with error handling."""
    try:
        client = _get_http_client()
        r = await client.get(
            f"{SIGNALS_BASE_URL}{path}",
            headers={"X-API-Key": API_SHARED_SECRET},
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        _logger.error("Upstream %s returned %d", path, e.response.status_code)
        raise error_response(502, "Upstream service error")
    except httpx.RequestError as e:
        _logger.error("Upstream %s request failed: %s", path, e)
        raise error_response(503, "Upstream service unavailable")


# ---- Endpoints ----

@router.get("/portfolio/overview", dependencies=[Depends(_portfolio_user_limit)])
async def portfolio_overview(_: bool = Depends(require_api_key)):
    return await _proxy_signals("/portfolio/overview")


@router.get("/portfolio/items", dependencies=[Depends(_portfolio_user_limit)])
async def portfolio_items(_: bool = Depends(require_api_key)):
    return await _proxy_signals("/portfolio/items")


@router.get("/portfolio/timeseries", dependencies=[Depends(_portfolio_user_limit)])
async def portfolio_timeseries(_: bool = Depends(require_api_key)):
    return await _proxy_signals("/portfolio/timeseries")


@router.get("/portfolio/summary")
async def portfolio_summary():
    """
    Backend sync v1: lightweight portfolio summary based on the same
    store that /items uses (_DEMO_ITEMS for now). Later this can be
    swapped to Supabase/Signals without changing the mobile app.
    """
    from app.routes.items_router import get_demo_items

    items_payload = []

    try:
        for it in get_demo_items():
            try:
                value = float(it.estimated_value or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            items_payload.append(
                {
                    "id": it.id,
                    "name": it.name,
                    "category": it.category or "Uncategorized",
                    "value": value,
                    "change_pct": 0.0,
                }
            )
    except Exception as e:
        logging.getLogger("uvicorn").warning(
            "[portfolio_summary] demo items unavailable: %s", e
        )

    total_value = sum(i["value"] for i in items_payload) if items_payload else 0.0
    avg_change_pct = 0.0

    return {
        "total_value": total_value,
        "avg_change_pct": avg_change_pct,
        "items": items_payload,
        "watchlist": [],
    }
