#!/usr/bin/env python3
"""Deal discovery worker — scans marketplaces for active purchase mandates.

Follows the same pattern as price_monitor_worker.py:
  - Connects to DB via asyncpg pool
  - Instantiates DealDiscoveryAgent
  - Scans all active mandates
  - Pushes notifications for new qualifying deals
  - Records run in worker registry
"""

import asyncio
import logging
import os
import uuid as _uuid

import asyncpg

from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [deal_discovery] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")


def _record_run(status: str) -> None:
    try:
        from app.worker_registry import record_run
        record_run("deal_discovery", status)
    except ImportError:
        pass


@with_async_retry(max_retries=3, base_delay=2.0, max_delay=60.0)
async def run_once():
    """Execute a single deal discovery cycle."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        _record_run("error")
        return

    # Use a connection pool instead of a single raw connection
    pool = await asyncpg.create_pool(DSN, min_size=2, max_size=5)
    logger.info("Connected to DB pool — starting deal discovery cycle")

    status = "ok"
    try:
        from app.agents.deal_discovery_agent import DealDiscoveryAgent
        from app.push import send_push_to_user

        agent = DealDiscoveryAgent()
        try:
            async with pool.acquire() as conn:
                new_deals = await agent.scan_all_active(conn)
        finally:
            await agent.close()

        # Push-notify each new deal (reuse a single connection)
        notified = 0
        async with pool.acquire() as conn:
            for deal in new_deals:
                try:
                    deal_uuid = _uuid.UUID(deal["id"])
                except (ValueError, AttributeError) as exc:
                    logger.warning("[deal_discovery] Invalid deal UUID %r: %s", deal.get("id"), exc)
                    continue

                # Check user preference before sending (P8)
                try:
                    from app.lib.notify import should_notify
                    allowed, reason = await should_notify(conn, deal["user_id"], "deal_alerts")
                    if not allowed:
                        logger.debug("Deal push skipped for user %s: %s", deal["user_id"][:8], reason)
                        continue
                except Exception:
                    pass  # Fallback: send anyway if check fails

                try:
                    sent = await send_push_to_user(
                        conn,
                        deal["user_id"],
                        title="Deal Found!",
                        body=(
                            f"{deal['listing_title'][:60]} \u2014 \u20ac{deal['listing_price']:.2f}"
                            + (f" ({deal.get('discount_pct', 0):.0f}% below market)" if deal.get('discount_pct') else "")
                        ),
                        data={
                            "type": "deal_alert",
                            "deal_id": deal["id"],
                            "url": deal.get("affiliate_url") or deal.get("listing_url", ""),
                        },
                    )
                    if sent > 0:
                        # Mark deal as notified
                        await conn.execute(
                            """
                            UPDATE public.mandate_deals
                            SET status = 'notified', notified_at = now()
                            WHERE id = $1
                            """,
                            deal_uuid,
                        )
                        notified += 1
                except Exception as exc:
                    logger.warning("[deal_discovery] Push failed for deal %s: %s", deal["id"], exc)

        logger.info(
            "Deal discovery cycle complete: %d new deals, %d notified",
            len(new_deals), notified,
        )

    except Exception:
        status = "error"
        raise
    finally:
        await pool.close()
        _record_run(status)


async def main():
    try:
        await run_once()
    except Exception as e:
        log_dead_letter("deal_discovery_worker", {}, e)
        logger.exception("deal_discovery_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
