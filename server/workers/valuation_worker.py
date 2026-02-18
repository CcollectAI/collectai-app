#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os

import asyncpg
from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [valuation_worker] %(levelname)s: %(message)s",
)

DSN = os.getenv("DB_DSN")

_EVIDENCE_LOOKBACK_DAYS = 90


def _build_evidence(hits: list[dict]) -> tuple[list[str], dict, str]:
    """
    Build evidence artifacts from a list of market hit dicts.

    Args:
        hits: List of dicts with keys ``id``, ``source``, ``price``,
              ``observed_at``.

    Returns:
        Tuple of (evidence_hit_ids, evidence_summary, explanation_text).
    """
    evidence_hit_ids: list[str] = [str(h["id"]) for h in hits]

    # Group by source
    source_groups: dict[str, list[dict]] = {}
    for h in hits:
        src = h["source"] or "unknown"
        source_groups.setdefault(src, []).append(h)

    source_summaries: list[dict] = []
    for src, group in sorted(source_groups.items()):
        prices = [float(g["price"]) for g in group]
        dates = [g["observed_at"] for g in group if g["observed_at"] is not None]
        avg_price = round(sum(prices) / len(prices), 2)

        date_range = None
        if dates:
            earliest = min(dates).strftime("%Y-%m-%d")
            latest = max(dates).strftime("%Y-%m-%d")
            date_range = f"{earliest} to {latest}" if earliest != latest else earliest

        source_summaries.append({
            "source": src,
            "count": len(group),
            "avg_price": avg_price,
            "date_range": date_range,
        })

    evidence_summary = {
        "sources": source_summaries,
        "total_comps": len(hits),
    }

    # Human-readable explanation
    _SOURCE_NAMES = {
        "ebay": "eBay sold",
        "tcgplayer": "TCGPlayer",
        "cardmarket": "Cardmarket",
        "mercari": "Mercari",
        "amazon": "Amazon",
        "catawiki": "Catawiki",
        "vinted": "Vinted",
        "stockx": "StockX",
        "discogs": "Discogs",
    }
    parts: list[str] = []
    for s in source_summaries:
        src_label = _SOURCE_NAMES.get(s["source"].lower(), s["source"].replace("_", " ").title())
        parts.append(
            f"{s['count']} {src_label} listing{'s' if s['count'] != 1 else ''} "
            f"(avg \u20ac{s['avg_price']:.2f})"
        )

    explanation_text = (
        f"Based on {' and '.join(parts)} "
        f"over the last {_EVIDENCE_LOOKBACK_DAYS} days."
    )

    return evidence_hit_ids, evidence_summary, explanation_text


@with_async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def run_once():
    if not DSN:
        logging.error("DB_DSN not set in environment")
        return

    conn = await asyncpg.connect(DSN)
    logging.info("Connected to DB")
    try:
        # -------------------------------------------------------------------
        # Fetch unprocessed market hits with full detail for evidence building
        # -------------------------------------------------------------------
        hit_rows = await conn.fetch("""
            SELECT id, item_ref, source, price::numeric AS price, observed_at
            FROM public.market_hits
            WHERE processed = false
              AND price IS NOT NULL
            ORDER BY item_ref, observed_at
        """)

        if not hit_rows:
            logging.info("No unprocessed market_hits found")
            return

        # Group by item_ref
        groups: dict[str, list[dict]] = {}
        for row in hit_rows:
            ref = row["item_ref"]
            groups.setdefault(ref, []).append({
                "id": row["id"],
                "source": row["source"],
                "price": row["price"],
                "observed_at": row["observed_at"],
            })

        logging.info("Found %d item_ref groups to process", len(groups))

        for item_ref, hits in groups.items():
            prices = sorted(float(h["price"]) for h in hits)
            if not prices:
                logging.warning("No valid prices for item_ref=%s, skipping", item_ref)
                continue

            n = len(prices)

            def q(p: float, _prices=prices, _n=n) -> float:
                """Simple quantile helper: p in [0,1]."""
                idx = max(0, min(_n - 1, int(round(p * (_n - 1)))))
                return _prices[idx]

            q10 = q(0.10)
            q50 = q(0.50)
            q90 = q(0.90)

            now = datetime.datetime.now(datetime.timezone.utc)

            # Build evidence artifacts
            evidence_hit_ids, evidence_summary, explanation_text = _build_evidence(hits)

            logging.info(
                "item_ref=%s n=%d q10=%.2f q50=%.2f q90=%.2f comps=%d",
                item_ref, n, q10, q50, q90, len(evidence_hit_ids),
            )

            # ---------------------------------------------------------------
            # INSERT price prediction with evidence columns
            # ---------------------------------------------------------------
            await conn.execute(
                """
                INSERT INTO public.price_predictions
                    (item_ref, q10, q50, q90, generated_at,
                     evidence_hit_ids, evidence_summary, explanation)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
                """,
                item_ref,
                q10,
                q50,
                q90,
                now,
                evidence_hit_ids,
                json.dumps(evidence_summary),
                explanation_text,
            )

            # ---------------------------------------------------------------
            # INSERT price history snapshot for anomaly detection (Task 3)
            # ---------------------------------------------------------------
            await conn.execute(
                """
                INSERT INTO public.price_history
                    (item_ref, price_q50, price_q10, price_q90, source, snapshot_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                item_ref,
                q50,
                q10,
                q90,
                "valuation_worker",
                now,
            )

            # Mark hits as processed
            await conn.execute(
                "UPDATE public.market_hits SET processed = true WHERE item_ref = $1",
                item_ref,
            )

        logging.info("Done valuation cycle")
    finally:
        await conn.close()
    record_run("valuation_worker", "ok")


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run("valuation_worker", "error")
        log_dead_letter("valuation_worker", {}, e)
        logging.exception("valuation_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
