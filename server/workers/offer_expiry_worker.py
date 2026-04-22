#!/usr/bin/env python3
"""Auto-expire stale Deal Desk offers.

Hourly worker that flips pending/countered offers whose `expires_at` has
passed → status='expired' and emits an `expired` event into offer_events.
Mirrors eBay's auto-decline-after-48h pattern. Distinct from `cancelled`
so analytics can tell "user gave up" from "system timed out".

Wired into bake_orchestrator manifest with run_once + 3600s cadence.
Constants kept in sync with rpc_*_offer_v1 (48h response window, 5 max
counter rounds — see migration 20260422_deal_desk_activate.sql).
"""
from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

from app.worker_registry import record_run

logger = logging.getLogger("collectai.offer_expiry")

DSN = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")


async def run_once() -> None:
    """Sweep expired offers; record_run handled by bake_orchestrator wrapper."""
    if not DSN:
        logger.error("DB_DSN(_DIRECT) not set; skipping")
        record_run("offer_expiry_worker", "error", error_repr="DSN missing")
        return

    conn = await asyncpg.connect(DSN, timeout=30)
    try:
        # Two-step: capture expired offer ids first so we can fan-out events
        # without holding a transaction across two tables (offer_events FK
        # references offers anyway, so it cascades correctly).
        expired = await conn.fetch(
            """
            UPDATE public.offers
               SET status = 'expired', expires_at = NULL
             WHERE status IN ('pending','countered')
               AND expires_at IS NOT NULL
               AND expires_at < now()
            RETURNING id, seller_id, amount
            """
        )
        if not expired:
            logger.info("[offer_expiry] no offers to expire")
            return

        # Emit one offer_events row per expired offer. actor_id is the seller
        # by convention (system action attributed to listing owner).
        await conn.executemany(
            """
            INSERT INTO public.offer_events (offer_id, actor_id, event_type, price, message)
            VALUES ($1::uuid, $2::uuid, 'expired', $3::numeric, 'auto-expired (48h response window)')
            """,
            [(r["id"], r["seller_id"], r["amount"]) for r in expired],
        )

        logger.info("[offer_expiry] expired %d offer(s)", len(expired))
    finally:
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(run_once())
