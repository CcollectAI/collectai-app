"""
Marketplace Aggregation Router.

Exposes the MarketplaceAgent as HTTP endpoints for searching, fetching
sold comparables, and checking adapter health.
"""

import json
import logging
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user_id
from app.db import db_configured, get_conn
from app.errors import error_response
from app.lib.affiliate import build_affiliate_url
from app.lib.shipping_service import detect_listing_region, estimate_shipping
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

# Per-user: 60 search requests per minute
_search_user_limit = per_user_rate_limit(60, window_seconds=60, scope="marketplace_search")

# Per-user: 20 comps requests per minute
_comps_user_limit = per_user_rate_limit(20, window_seconds=60, scope="marketplace_comps")


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
    source: Optional[List[str]] = Field(None, description="Filter to only these marketplace sources")
    condition: Optional[List[str]] = Field(None, description="Filter to only these conditions")
    sort: Optional[str] = Field(None, description="Sort order: relevance/price_asc/price_desc/newest")


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
    _rl: None = Depends(_search_user_limit),
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

        # Build affiliate URLs + shipping estimates for each hit
        hits_out = []
        for h in result.hits:
            raw_url = h.hit.get("url") or ""
            source_name = h.hit.get("source") or ""
            aff_url, aff_source = build_affiliate_url(raw_url, source_name)

            # Detect listing region & estimate shipping
            listing_region = detect_listing_region(
                source=source_name,
                ships_from=h.hit.get("ships_from"),
                url=raw_url,
            )
            adapter_shipping = h.hit.get("shipping_cost")
            shipping_estimate = None
            if region or listing_region:
                est = estimate_shipping(listing_region, region)
                shipping_estimate = {
                    "min_eur": est.min_cost_eur,
                    "max_eur": est.max_cost_eur,
                    "exact_eur": adapter_shipping,
                    "is_domestic": est.is_domestic,
                    "disclaimer": est.disclaimer,
                }

            hits_out.append({
                "source": source_name,
                "title": h.hit.get("title"),
                "price": h.hit.get("price"),
                "currency": h.hit.get("currency", "EUR"),
                "source_price": h.hit.get("source_price"),
                "source_currency": h.hit.get("source_currency"),
                "url": raw_url,
                "affiliate_url": aff_url if aff_url != raw_url else None,
                "affiliate_source": aff_source or None,
                "image_url": h.hit.get("image_url"),
                "condition": h.hit.get("condition"),
                "is_sold": h.is_sold,
                "provenance_score": round(h.provenance_score, 3),
                "source_reliability": round(h.source_reliability, 3),
                "recency_score": round(h.recency_score, 3),
                "shipping_cost": adapter_shipping,
                "ships_from": h.hit.get("ships_from"),
                "domestic_only": h.hit.get("domestic_only", False),
                "listing_region": listing_region,
                "shipping_estimate": shipping_estimate,
            })

        # ── Post-query filters ────────────────────────────────────────────
        if request.source:
            allowed = {s.lower() for s in request.source}
            hits_out = [h for h in hits_out if (h.get("source") or "").lower() in allowed]

        if request.condition:
            cond_lower = {c.lower() for c in request.condition}
            hits_out = [
                h for h in hits_out
                if h.get("condition") and any(c in (h["condition"] or "").lower() for c in cond_lower)
            ]

        if request.min_price is not None:
            hits_out = [h for h in hits_out if h.get("price") is not None and h["price"] >= request.min_price]

        if request.max_price is not None:
            hits_out = [h for h in hits_out if h.get("price") is not None and h["price"] <= request.max_price]

        if request.sort:
            if request.sort == "price_asc":
                hits_out.sort(key=lambda h: (h.get("price") is None, h.get("price") or 0))
            elif request.sort == "price_desc":
                hits_out.sort(key=lambda h: (h.get("price") is None, -(h.get("price") or 0)))
            # "newest" and "relevance" keep the default order from the agent

        # Record demand signal with geo enrichment (best-effort)
        try:
            from app.features.data_moat import record_demand_signal, get_user_geo
            geo_region, geo_country = await get_user_geo(user_id)
            await record_demand_signal(
                signal_type="search_query",
                category=request.category,
                query_text=request.query,
                user_id=user_id,
                region=geo_region,
                country_code=geo_country,
            )
        except Exception:
            pass

        return {
            "hits": hits_out,
            "total_sources_queried": result.total_sources_queried,
            "successful_sources": result.successful_sources,
            "aggregate_confidence": round(result.aggregate_confidence, 3),
            "dedup_count": result.dedup_count,
            "total_results": len(hits_out),
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
    _rl: None = Depends(_comps_user_limit),
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
async def marketplace_health() -> dict:
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


@router.get("/adapter-health")
async def adapter_health() -> dict:
    """Combined adapter health + circuit breaker status for all 11 sources."""
    from app.agents.marketplace_agent import MarketplaceAgent
    from workers.circuit_breaker import all_circuit_status

    agent = MarketplaceAgent()
    try:
        health = await agent.health_check()
    except Exception:
        health = {"adapters": {}, "any_healthy": False}
    finally:
        await agent.close()

    circuits = all_circuit_status()
    return {
        "adapters": health.get("adapters", {}),
        "any_healthy": health.get("any_healthy", False),
        "circuit_breakers": circuits,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _persist_hits(scored_hits: list, user_id: str) -> None:
    """Write scored market hits into the market_hits table.

    Schema columns: provider, listing_id, title, price, currency,
    condition, ended_at, url, normalized_key, features_json,
    shipping, ships_from, domestic_only.
    """
    async with get_conn() as conn:
        async with conn.transaction():
            for sh in scored_hits[:50]:  # cap to 50 per request
                h = sh.hit
                await conn.execute(
                    """
                    INSERT INTO public.market_hits
                        (provider, listing_id, title, price, currency,
                         condition, ended_at, url, normalized_key, features_json,
                         shipping, ships_from, domestic_only)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb,
                            $11, $12, $13)
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
                    h.get("shipping_cost"),
                    h.get("ships_from"),
                    h.get("domestic_only", False),
                )
