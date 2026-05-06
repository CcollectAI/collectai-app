"""On-demand enrichment for thin-category items.

When a user views or saves an item that has too few recent comps, we fire
a single paid-scraper call (Scrape.do today, SerpAPI later) to pull fresh
listings for that specific item. Results are persisted to `market_hits`
and the lookup is cached so repeat requests within TTL skip the paid call.

Strategy notes:
- We don't pre-crawl thin categories. Background crawl × 140k items × paid
  scraper would be unaffordable. On-demand × actual user views × paid
  scraper is cheap (most items are never viewed).
- Every paid lookup permanently improves the dataset for that item:
  rows go into market_hits which feeds aggregate_catalog_attributes,
  valuation comps, and calibration. Net cost per item amortizes to zero
  after the first lookup.
- Spend caps: per-cycle check via spend_tracker (~€150/mo budget cap with
  alerts at 75/90/100%).

Public entry: `enrich_item(item_ref, query, category) -> dict`
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default TTL — cats with rapidly-changing markets refresh more often.
DEFAULT_TTL_DAYS = int(os.getenv("ON_DEMAND_TTL_DAYS", "14"))
TTL_BY_CATEGORY: Dict[str, int] = {
    "watches": 30,        # Slow-moving, high-value
    "whiskey": 30,
    "art": 30,
    "fragrances": 21,
    # everything else uses DEFAULT_TTL_DAYS
}

# Estimated cost per Scrape.do call (€). Updated when SerpAPI wires in.
COST_PER_CALL_EUR = float(os.getenv("ON_DEMAND_COST_EUR", "0.02"))


def _ttl_for(category: str) -> int:
    return TTL_BY_CATEGORY.get(category, DEFAULT_TTL_DAYS)


async def _is_cache_fresh(conn, item_ref: str, category: str) -> bool:
    """True if a cached lookup exists and is within TTL."""
    row = await conn.fetchrow(
        """
        SELECT last_fetched_at FROM public.on_demand_lookups
        WHERE item_ref = $1
        """,
        item_ref,
    )
    if not row:
        return False
    age_days = (datetime.now(timezone.utc) - row["last_fetched_at"]).days
    return age_days < _ttl_for(category)


async def enrich_item(
    conn,
    item_ref: str,
    query: str,
    category: str,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Fire one paid-scraper call for this item, persist hits, return summary.

    Returns:
        {
            "skipped": bool,         # True if cache fresh or budget exhausted
            "reason": str,           # 'cache_fresh' | 'budget_exhausted' | 'ok' | 'error'
            "hits_persisted": int,
            "cost_cents": int,
        }
    """
    # 1. Cache check
    if not force and await _is_cache_fresh(conn, item_ref, category):
        return {"skipped": True, "reason": "cache_fresh", "hits_persisted": 0, "cost_cents": 0}

    # 2. Try Scrape.do first (real comps > synthetic estimate). Falls
    # through to the Claude estimator on any of:
    #   - SpendTracker budget exhausted
    #   - ScrapedoCaller not configured (SCRAPEDO_ENABLED=false / no key)
    #   - Scrape.do call returns 0 hits
    last_error: Optional[str] = None
    hits = []
    cost_cents = 0
    last_provider = "scrapedo"
    scrapedo_available = False

    try:
        from app.lib.spend_tracker import SpendTracker, BudgetExceededError  # noqa: F401
        tracker = SpendTracker.instance() if hasattr(SpendTracker, "instance") else SpendTracker()
        tracker.check("scrapedo")
        scrapedo_available = True
    except Exception as e:  # noqa: BLE001
        logger.info("on_demand_enrich scrapedo budget unavailable: %s", e)

    if scrapedo_available:
        from app.agents.adapters.scrapedo_caller import ScrapedoCaller
        caller = ScrapedoCaller()
        if getattr(caller, "configured", False):
            try:
                hits = await caller.search(query, category=category, limit=20) or []
                cost_cents = int(COST_PER_CALL_EUR * 100)
                try:
                    tracker.record("scrapedo", cost_eur=COST_PER_CALL_EUR)
                except Exception:
                    pass
            except Exception as e:  # noqa: BLE001
                last_error = f"scrapedo: {type(e).__name__}: {e!s}"[:300]
                logger.warning("on_demand_enrich scrape failed for %s: %s", item_ref, e)
        else:
            scrapedo_available = False

    # 3. Claude fallback — only when Scrape.do produced nothing usable.
    # Synthesises a single q10/q50/q90 row tagged source='claude_estimate'.
    # See claude_estimator.py for the cost-cap and prompt-cache details.
    if not hits:
        try:
            from app.agents.claude_estimator import (
                estimate_thin_cat_price, to_market_hit,
            )
            estimate = await estimate_thin_cat_price(
                category=category,
                title=query,
                attrs=None,
            )
            if estimate.get("ok"):
                synth = to_market_hit(
                    estimate,
                    category=category,
                    item_ref=item_ref,
                    listing_id=f"claude:{item_ref}",
                )
                if synth is not None:
                    hits = [synth]
                    cost_cents += int(estimate["cost_eur"] * 100)
                    last_provider = "claude_estimate"
            else:
                # Surface the reason in the cache row for ops visibility.
                last_error = (last_error + "; " if last_error else "") + (
                    f"claude_estimate: {estimate.get('reason', 'unknown')}"
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("on_demand_enrich claude fallback failed for %s: %s", item_ref, e)
            last_error = (last_error + "; " if last_error else "") + f"claude_estimate: {e!s}"[:200]

    # 4. Persist hits to market_hits (delegates to existing writer so all
    # the normalization/category-prefixing/attrs flow happens uniformly).
    persisted = 0
    if hits:
        try:
            from app.agents.marketplace_agent import persist_comps_to_db
            persisted = await persist_comps_to_db(
                conn, hits, category=category, normalized_key=item_ref,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("on_demand_enrich persist failed: %s", e)
            last_error = (last_error or "") + f"; persist: {e!s}"[:200]

    # If neither Scrape.do nor Claude produced anything, surface that.
    if not scrapedo_available and not hits:
        return {
            "skipped": True,
            "reason": "no_provider_available",
            "hits_persisted": 0,
            "cost_cents": 0,
        }

    # 5. Upsert cache row
    await conn.execute(
        """
        INSERT INTO public.on_demand_lookups
          (item_ref, category, last_fetched_at, fetch_count, hit_count,
           cost_cents, last_provider, last_error)
        VALUES ($1, $2, now(), 1, $3, $4, $5, $6)
        ON CONFLICT (item_ref) DO UPDATE
        SET last_fetched_at = excluded.last_fetched_at,
            fetch_count    = on_demand_lookups.fetch_count + 1,
            hit_count      = on_demand_lookups.hit_count + excluded.hit_count,
            cost_cents     = on_demand_lookups.cost_cents + excluded.cost_cents,
            last_provider  = excluded.last_provider,
            last_error     = excluded.last_error
        """,
        item_ref, category, persisted, cost_cents, last_provider, last_error,
    )

    return {
        "skipped": False,
        "reason": "ok" if not last_error else "error",
        "hits_persisted": persisted,
        "cost_cents": cost_cents,
        "provider": last_provider,
    }
