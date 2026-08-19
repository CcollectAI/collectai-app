#!/usr/bin/env python3
"""Grade reminder worker — one nudge to rate a trade that was never rated.

Ratings are the whole trust model (P2P spec §8e: we build the *felt* half of
buyer protection out of facts we already hold, because §5b forbids the funded
half). A rating that is never left is a fact we never get, and the ask at
completion time competes with the member actually unwrapping the thing they
just bought.

So: exactly ONE reminder per party per trade, 24h after completion, and only
while that member's grade is still missing. Never a second one — a marketplace
that nags for reviews trains people to swipe its notifications away, and the
completion push has already asked once.

Idempotency lives in `notification_history`, not in a new column. The row this
worker writes IS the record that it fired: `data->>'kind' = 'p2p_grade_reminder'`
plus `data->>'offer_id'`. That is queryable because `app/push.py` passes the
DICT to a jsonb column with a codec, so `data->>'x'` is real JSON rather than a
double-encoded string (fixed 2026-08-09). No DDL, so no schema.lock regen and
no restart-time bomb (learning_stale_schema_lock_is_a_restart_time_bomb).

Schedule: hourly. The 24h boundary is enforced in the QUERY, not by the
interval — a worker that oversleeps must still send the right thing, and a
docstring is not a schedule (learning_third_party_rate_bans_and_schedule_drift).
"""

from __future__ import annotations

import asyncio
import logging
import os

import asyncpg

from app.worker_registry import record_run
from workers.retry import with_async_retry, log_dead_letter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [grade_reminder] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

DSN = os.getenv("DB_DSN")

# Wait this long after completion before nudging.
REMIND_AFTER_HOURS = int(os.getenv("GRADE_REMIND_AFTER_HOURS", "24"))
# And give up entirely after this. Bounds the blast radius the first time this
# worker runs against a database that already holds old completed trades:
# without an upper bound, enabling it would push a reminder for every trade
# ever completed, all at once.
REMIND_UNTIL_DAYS = int(os.getenv("GRADE_REMIND_UNTIL_DAYS", "7"))
# Per-cycle ceiling. Logged when it bites — a silent truncation reads as
# "everyone was reminded" when they were not.
MAX_PER_CYCLE = int(os.getenv("GRADE_REMIND_MAX_PER_CYCLE", "200"))


# Each row is ONE person who still owes ONE rating.
#
# `GREATEST(seller_confirmed_at, buyer_confirmed_at)` is the completion moment,
# used in preference to `updated_at` — which any later touch of the row would
# move, silently resetting the clock or pushing a trade out of the window.
#
# The two NOT EXISTS clauses are the whole design: the first stops reminding
# someone who already rated (including a re-grade, since member_grades is
# unique per (offer_id, rater_id)), the second stops a second reminder ever.
# Compared as ::text on both sides so this holds whether
# notification_history.user_id is uuid or text.
_PENDING_SQL = """
    WITH completed AS (
        SELECT o.id            AS offer_id,
               o.buyer_id,
               o.seller_id,
               l.listing_title,
               GREATEST(o.seller_confirmed_at, o.buyer_confirmed_at) AS completed_at
        FROM public.p2p_offers o
        LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id
        WHERE o.status = 'completed'
          AND o.seller_confirmed_at IS NOT NULL
          AND o.buyer_confirmed_at IS NOT NULL
          AND GREATEST(o.seller_confirmed_at, o.buyer_confirmed_at)
              <= now() - make_interval(hours => $1)
          AND GREATEST(o.seller_confirmed_at, o.buyer_confirmed_at)
              >  now() - make_interval(days => $2)
    )
    SELECT c.offer_id,
           c.listing_title,
           c.completed_at,
           party.party_id,
           party.other_role
    FROM completed c
    CROSS JOIN LATERAL (
        VALUES (c.buyer_id, 'seller'), (c.seller_id, 'buyer')
    ) AS party(party_id, other_role)
    WHERE party.party_id IS NOT NULL
      AND NOT EXISTS (
            SELECT 1 FROM public.member_grades g
             WHERE g.offer_id = c.offer_id
               AND g.rater_id = party.party_id
      )
      AND NOT EXISTS (
            SELECT 1 FROM public.notification_history nh
             WHERE nh.user_id::text = party.party_id::text
               AND nh.data->>'kind' = 'p2p_grade_reminder'
               AND nh.data->>'offer_id' = c.offer_id::text
      )
    ORDER BY c.completed_at ASC
    LIMIT $3
"""


@with_async_retry(max_retries=2, base_delay=1.0, max_delay=30.0)
async def run_once():
    """Send at most one rating reminder per party per completed trade."""
    if not DSN:
        logger.error("DB_DSN not set in environment")
        record_run("grade_reminder_worker", "error")
        return

    # `init=_init_conn` is REQUIRED, not decoration. It registers the jsonb
    # codec every pooled API connection carries; `app/push.py` deliberately
    # passes a DICT to `$5::jsonb` on that assumption. A pool without it made
    # every deal notification die with "expected str, got dict" while the cycle
    # still reported success (2026-08-12, deal_discovery_worker) — and here it
    # would ALSO break idempotency, since the reminder's own record is the
    # `data->>'kind'` this worker reads back.
    from app.db import _init_conn

    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=2, init=_init_conn)

    status = "ok"
    sent = 0
    failed = 0
    pending: list = []
    try:
        from app.lib.notify import notify_user

        async with pool.acquire() as conn:
            pending = await conn.fetch(
                _PENDING_SQL, REMIND_AFTER_HOURS, REMIND_UNTIL_DAYS, MAX_PER_CYCLE,
            )

            if not pending:
                logger.info("No unrated trades in the reminder window")
                return

            if len(pending) == MAX_PER_CYCLE:
                logger.warning(
                    "Hit the per-cycle ceiling of %d reminders — the remainder "
                    "waits for the next run rather than being dropped (the "
                    "query re-finds anyone not yet notified)",
                    MAX_PER_CYCLE,
                )

            for row in pending:
                offer_id = str(row["offer_id"])
                party_id = str(row["party_id"])
                title_ = row["listing_title"] or "your trade"
                try:
                    # category="account", matching every other trade
                    # notification: this is a fact about a trade the member is
                    # party to, not a discovery alert, and it must not wear the
                    # deal-alert badge that reads as "act on this for profit".
                    #
                    # urgent=False, UNLIKE the transactional pushes. Those must
                    # reach a member already at their daily cap; a reminder is
                    # exactly what the cap exists to hold back. Capped-out means
                    # skipped, and skipped is correct here — we ask once, then
                    # stop.
                    await notify_user(
                        conn,
                        party_id,
                        "Rate your trade",
                        f"How did the exchange of \"{title_}\" go? "
                        f"Rating the {row['other_role']} helps other members "
                        "trade safely.",
                        category="account",
                        data={"kind": "p2p_grade_reminder", "offer_id": offer_id},
                        deep_link=f"/offers?offerId={offer_id}",
                        urgent=False,
                    )
                    sent += 1
                except Exception as exc:  # noqa: BLE001 — one bad row must not stop the rest
                    failed += 1
                    # error, not warning: warn is stripped in release builds and
                    # a reminder that never sent is invisible by nature
                    # (learning_prod_logger_strips_info_warn).
                    logger.error(
                        "Reminder failed for user=%s offer=%s: %r",
                        party_id[:8], offer_id, exc,
                    )

        logger.info(
            "Grade reminder cycle complete: candidates=%d sent=%d failed=%d",
            len(pending), sent, failed,
        )
        if failed and sent == 0:
            status = "error"

    finally:
        await pool.close()
        record_run("grade_reminder_worker", status)


async def main():
    try:
        await run_once()
    except Exception as e:
        record_run(
            "grade_reminder_worker", "error",
            error_repr=f"{type(e).__name__}: {e!s}"[:500],
        )
        log_dead_letter("grade_reminder_worker", {}, e)
        logger.exception("grade_reminder_worker crashed: %r", e)


if __name__ == "__main__":
    asyncio.run(main())
