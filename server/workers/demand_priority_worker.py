#!/usr/bin/env python3
"""Demand priority worker — refresh prices for the most-demanded catalog items.

Runs in parallel to `catalog_crawler_worker` (which is round-robin per category
for fairness). This worker explicitly picks the top-N items by recent
demand_signals count and triggers a fresh marketplace scrape for each, so
items with active user interest stay price-fresh without compromising
catalog-wide coverage.

Closes the loop:
  user view/scan/watchlist → demand_signals → demand_priority_worker
  → fresh market_hits → updated price_predictions → user sees fresh price

Scope guard: only refreshes items where demand_signals.item_key resolves to
an actual item UUID (those signals come from predict_router/dossier_router
where the FE has a real item.id). Title-based item_keys (watchlist_add) are
skipped here — catalog_crawler will eventually pick them via fairness.
"""

from __future__ import annotations

import asyncio
import logging
import os
import statistics
import uuid

import asyncpg

from app.worker_registry import record_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [demand_priority] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")

LOOKBACK_DAYS = int(os.getenv("DEMAND_PRIORITY_LOOKBACK_DAYS", "14"))
TOP_N = int(os.getenv("DEMAND_PRIORITY_TOP_N", "30"))
INTER_DELAY = float(os.getenv("DEMAND_PRIORITY_DELAY", "2.0"))


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False


async def run_once() -> dict[str, int]:
    if not DSN:
        logger.warning("DB_DSN not set — skipping")
        record_run("demand_priority_worker", "error")
        return {"refreshed": 0, "hits": 0}

    conn = await asyncpg.connect(DSN)
    refreshed = 0
    total_hits = 0
    try:
        # Top items by recent demand_signals (UUID-shaped item_keys only —
        # those are real item refs we can pull title/category for).
        rows = await conn.fetch(
            """
            SELECT ds.item_key, COUNT(*) AS sig_count
            FROM public.demand_signals ds
            WHERE ds.signal_type IN ('item_viewed','item_scanned','price_alert_set')
              AND ds.item_key IS NOT NULL
              AND ds.created_at >= now() - ($1 || ' days')::interval
            GROUP BY ds.item_key
            ORDER BY sig_count DESC
            LIMIT $2
            """,
            LOOKBACK_DAYS, TOP_N,
        )

        if not rows:
            logger.info("No demand priority candidates this cycle")
            record_run("demand_priority_worker", "ok")
            return {"refreshed": 0, "hits": 0}

        # Resolve item_key (UUID) → (title, category) via items table.
        candidates = []
        for r in rows:
            ik = r["item_key"]
            if not _is_uuid(ik):
                continue
            item = await conn.fetchrow(
                """
                SELECT COALESCE(title, name, manual_name, ai_label) AS title,
                       category, canonical_key
                FROM public.items
                WHERE id = $1::uuid
                """,
                ik,
            )
            if item and item["title"] and item["category"]:
                candidates.append({
                    "id": ik,
                    "title": item["title"],
                    "category": item["category"],
                    "canonical_key": item["canonical_key"] or item["title"],
                    "sig_count": r["sig_count"],
                })

        if not candidates:
            logger.info("Top-demand items resolved 0 catalog matches this cycle")
            record_run("demand_priority_worker", "ok")
            return {"refreshed": 0, "hits": 0}

        # Lazy import the agent — avoids loading heavy deps at module load
        from app.agents.marketplace_agent import MarketplaceAgent
        agent = MarketplaceAgent()
        try:
            for c in candidates:
                try:
                    result = await agent.aggregate_search(
                        query=c["title"], category=c["category"],
                        limit=20, include_sold=True,
                    )
                    hit_count = len(getattr(result, "hits", []) or [])
                    if hit_count:
                        normalized_key = f"{c['category']}:{c['canonical_key']}"
                        await agent.persist_comps_to_db(
                            result, normalized_key=normalized_key,
                            category=c["category"],
                        )
                        total_hits += hit_count
                    refreshed += 1
                    logger.info(
                        "  refreshed item=%s sig_count=%d hits=%d",
                        c["id"][:8], c["sig_count"], hit_count,
                    )
                except Exception as e:
                    logger.warning("  item=%s failed: %s", c["id"][:8], e)
                await asyncio.sleep(INTER_DELAY)
        finally:
            try:
                await agent.close()
            except Exception:
                pass

        logger.info(
            "demand_priority cycle complete: refreshed=%d/%d total_hits=%d",
            refreshed, len(candidates), total_hits,
        )
        record_run("demand_priority_worker", "ok")
        return {"refreshed": refreshed, "hits": total_hits}
    finally:
        await conn.close()


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("demand_priority_worker", "error")
        logger.exception("demand_priority_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
