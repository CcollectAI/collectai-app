"""
Marketplace Aggregation Router.

Exposes the MarketplaceAgent as HTTP endpoints for searching, fetching
sold comparables, and checking adapter health.
"""

import json
import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import db_configured, get_conn
from app.errors import error_response
from app.lib.affiliate import build_affiliate_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class MarketSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = Field(None, max_length=64)
    limit: int = Field(20, ge=1, le=100)
    sold_only: bool = False
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    region: Optional[str] = Field(None, max_length=16, description="User region: americas/europe/japan/other")


class CompsRequest(BaseModel):
    item_ref: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=64)
    limit: int = Field(20, ge=1, le=50)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/search")
async def marketplace_search(
    request: MarketSearchRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Aggregate search across all configured market adapters."""
    from app.agents.marketplace_agent import MarketplaceAgent

    # Resolve region: explicit request > user_settings > None
    region = request.region
    if not region and db_configured():
        try:
            async with get_conn() as conn:
                row = await conn.fetchval(
                    "SELECT settings_json->>'region' FROM user_settings WHERE user_id = $1",
                    user_id,
                )
                if row:
                    region = row
        except Exception:
            logger.debug("Could not look up user region from DB")

    agent = MarketplaceAgent()
    try:
        result = await agent.aggregate_search(
            query=request.query,
            category=request.category,
            limit=request.limit,
            include_sold=request.sold_only,
            region=region,
        )

        # Persist new hits to market_hits if DB is configured
        if db_configured() and result.hits:
            try:
                await _persist_hits(result.hits, user_id)
            except asyncpg.PostgresError:
                logger.warning("Failed to persist market hits to DB")

        # Build affiliate URLs for each hit
        hits_out = []
        for h in result.hits:
            raw_url = h.hit.get("url") or ""
            source_name = h.hit.get("source") or ""
            aff_url, aff_source = build_affiliate_url(raw_url, source_name)
            hits_out.append({
                "source": source_name,
                "title": h.hit.get("title"),
                "price": h.hit.get("price"),
                "currency": h.hit.get("currency", "EUR"),
                "url": raw_url,
                "affiliate_url": aff_url if aff_url != raw_url else None,
                "affiliate_source": aff_source or None,
                "image_url": h.hit.get("image_url"),
                "condition": h.hit.get("condition"),
                "is_sold": h.is_sold,
                "provenance_score": round(h.provenance_score, 3),
                "source_reliability": round(h.source_reliability, 3),
                "recency_score": round(h.recency_score, 3),
            })

        return {
            "hits": hits_out,
            "total_sources_queried": result.total_sources_queried,
            "successful_sources": result.successful_sources,
            "aggregate_confidence": round(result.aggregate_confidence, 3),
            "dedup_count": result.dedup_count,
            "total_results": len(result.hits),
        }
    except HTTPException:
        raise
    except asyncpg.PostgresError:
        logger.exception("Marketplace search failed due to DB error")
        raise error_response(500, "Market search failed", code="DB_ERROR")
    except (ConnectionError, TimeoutError, OSError) as e:
        logger.exception("Marketplace search failed due to external API error")
        raise error_response(503, "Market search failed", code="EXTERNAL_API_ERROR")
    except Exception:
        logger.exception("Marketplace search failed")
        raise error_response(500, "Market search failed", code="INTERNAL_ERROR")
    finally:
        await agent.close()


@router.post("/comps/{item_ref:path}")
async def marketplace_comps(
    item_ref: str,
    category: Optional[str] = None,
    limit: int = 20,
    region: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
):
    """Find sold comparables for an item and persist to market_hits."""
    from app.agents.marketplace_agent import MarketplaceAgent

    # Resolve region: explicit param > user_settings > None
    if not region and db_configured():
        try:
            async with get_conn() as conn:
                row = await conn.fetchval(
                    "SELECT settings_json->>'region' FROM user_settings WHERE user_id = $1",
                    user_id,
                )
                if row:
                    region = row
        except Exception:
            logger.debug("Could not look up user region from DB")

    agent = MarketplaceAgent()
    try:
        result = await agent.find_sold_comps(
            query=item_ref,
            category=category,
            limit=min(limit, 50),
            region=region,
        )

        if db_configured() and result.hits:
            try:
                await _persist_hits(result.hits, user_id)
            except asyncpg.PostgresError:
                logger.warning("Failed to persist comp hits to DB")

        return {
            "comps": [
                {
                    "source": h.hit.get("source"),
                    "title": h.hit.get("title"),
                    "price": h.hit.get("price"),
                    "sold_at": h.hit.get("sold_at"),
                    "condition": h.hit.get("condition"),
                    "provenance_score": round(h.provenance_score, 3),
                }
                for h in result.hits
            ],
            "aggregate_confidence": round(result.aggregate_confidence, 3),
            "total_comps": len(result.hits),
        }
    except HTTPException:
        raise
    except asyncpg.PostgresError:
        logger.exception("Marketplace comps failed due to DB error")
        raise error_response(500, "Comps lookup failed", code="DB_ERROR")
    except (ConnectionError, TimeoutError, OSError) as e:
        logger.exception("Marketplace comps failed due to external API error")
        raise error_response(503, "Comps lookup failed", code="EXTERNAL_API_ERROR")
    except Exception:
        logger.exception("Marketplace comps failed")
        raise error_response(500, "Comps lookup failed", code="INTERNAL_ERROR")
    finally:
        await agent.close()


@router.get("/health")
async def marketplace_health():
    """Check health of all configured market adapters."""
    from app.agents.marketplace_agent import MarketplaceAgent

    agent = MarketplaceAgent()
    try:
        statuses = await agent.health_check()
        return {"adapters": statuses}
    except (ConnectionError, TimeoutError, OSError):
        logger.exception("Marketplace health check failed")
        return {"adapters": [], "error": "Health check failed"}
    finally:
        await agent.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _persist_hits(scored_hits, user_id: str):
    """Write scored market hits into the market_hits table.

    Schema columns: provider, listing_id, title, price, currency,
    condition, ended_at, url, normalized_key, features_json.
    """
    async with get_conn() as conn:
        async with conn.transaction():
            for sh in scored_hits[:50]:  # cap to 50 per request
                h = sh.hit
                await conn.execute(
                    """
                    INSERT INTO public.market_hits
                        (provider, listing_id, title, price, currency,
                         condition, ended_at, url, normalized_key, features_json)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
                    ON CONFLICT (provider, listing_id) DO NOTHING
                    """,
                    h.get("source", "unknown"),
                    h.get("raw_id") or h.get("content_hash") or h.get("url", "")[:255],
                    (h.get("title", "") or "")[:500],
                    h.get("price"),
                    h.get("currency", "EUR"),
                    h.get("condition"),
                    h.get("sold_at") or h.get("ended_at"),
                    (h.get("url", "") or "")[:1000],
                    (h.get("normalized_key", "") or "")[:255],
                    json.dumps({"image_url": h.get("image_url"), "user_id": user_id}),
                )
