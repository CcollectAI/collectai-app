"""E2E: the "rate your trade" reminder, against a real database.

WHY THIS EXISTS
`grade_reminder_worker` went live in the bake on 2026-08-19 and has never sent
anything — prod holds no completed trade older than 24h, so every cycle
correctly does nothing. A worker that has only ever run on an empty set is a
worker nobody has tested: the first time it fires for real is the first time
its query, its idempotency guard and its notification path are exercised
together, and the failure mode is spamming both sides of every trade.

So this seeds the state the worker is waiting for, runs it, and asserts:

  1. it sends ONE reminder per party
  2. running again sends NOTHING (idempotency lives in notification_history,
     not in a column, so this is the only place that can prove it)
  3. a party who has already graded is skipped
  4. a trade completed too recently is not touched
  5. the deep link carries the offer, not the bare list

Run FROM EC2 (the direct DSN does not resolve from a laptop —
`[Errno 8] nodename nor servname` is the Darwin tell):

    cd /opt/collectors/server
    set -a && . /opt/collectors/.env && set +a
    PYTHONPATH=/opt/collectors/server /opt/collectors/.venv/bin/python \
        tests/e2e_grade_reminder.py

Everything it writes, it deletes. The final check asserts that.
"""
import asyncio
import os
import uuid

import asyncpg

SELLER = '4a1d7970-69a6-4575-aff3-8e1c52ae420a'
BUYER = '7c9e1a44-0000-4000-8000-00000000b002'
ITEM = '8b439f25-a812-46aa-a918-28a50e081143'

OK, FAIL = [], []


def chk(name, cond, detail=''):
    (OK if cond else FAIL).append(name)
    print(('  PASS  ' if cond else '  FAIL  ') + name + (' | ' + str(detail) if detail else ''))


async def reminders_for(c, offer_id):
    """Reminder rows this worker wrote for one offer, by party.

    Keyed on `data->>'kind'` — the same jsonb the worker reads back to decide
    whether it has already asked. If the codec ever double-encodes that column
    again (2026-08-09), this returns nothing and the test fails loudly rather
    than the worker silently re-sending forever.
    """
    rows = await c.fetch(
        "SELECT user_id::text AS u, deep_link, title FROM notification_history "
        "WHERE data->>'kind' = 'p2p_grade_reminder' AND data->>'offer_id' = $1",
        offer_id,
    )
    return {r['u']: r for r in rows}


async def main():
    dsn = os.getenv('DB_DSN_DIRECT') or os.getenv('DB_DSN')
    c = await asyncpg.connect(dsn)
    await c.execute(
        "INSERT INTO auth.users (id, email) VALUES ($1::uuid,'e2e-buyer@test.local') "
        "ON CONFLICT DO NOTHING", BUYER)

    listing_id = str(uuid.uuid4())
    offer_id = str(uuid.uuid4())
    fresh_offer_id = str(uuid.uuid4())
    fresh_listing_id = str(uuid.uuid4())

    try:
        print('1. SEED a trade that completed 30 HOURS AGO')
        for lid in (listing_id, fresh_listing_id):
            await c.execute(
                """
                INSERT INTO marketplace_listings
                    (id, user_id, item_id, marketplace_id, listing_title, price,
                     currency, status, format)
                VALUES ($1::uuid, $2::uuid, $3::uuid, 'sparrow',
                        'E2E reminder listing', 25.0, 'EUR', 'sold', 'fixed_price')
                """,
                lid, SELLER, ITEM)

        # 30h ago: past the 24h wait, inside the 7d window.
        await c.execute(
            """
            INSERT INTO p2p_offers
                (id, listing_id, buyer_id, seller_id, amount, currency, status,
                 seller_confirmed_at, buyer_confirmed_at, created_at, updated_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 25.0, 'EUR', 'completed',
                    now() - interval '30 hours', now() - interval '30 hours',
                    now() - interval '3 days', now())
            """,
            offer_id, listing_id, BUYER, SELLER)

        # 2h ago: inside the wait, must NOT be touched.
        await c.execute(
            """
            INSERT INTO p2p_offers
                (id, listing_id, buyer_id, seller_id, amount, currency, status,
                 seller_confirmed_at, buyer_confirmed_at, created_at, updated_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 25.0, 'EUR', 'completed',
                    now() - interval '2 hours', now() - interval '2 hours',
                    now() - interval '1 day', now())
            """,
            fresh_offer_id, fresh_listing_id, BUYER, SELLER)

        print('2. RUN the worker')
        from workers.grade_reminder_worker import run_once
        await run_once()

        sent = await reminders_for(c, offer_id)
        chk('both parties were reminded', len(sent) == 2, sorted(sent))
        chk('the buyer was reminded', BUYER in sent)
        chk('the seller was reminded', SELLER in sent)
        if sent:
            any_row = next(iter(sent.values()))
            chk('the reminder deep-links to THIS offer, not the list',
                any_row['deep_link'] == f'/offers?offerId={offer_id}',
                any_row['deep_link'])
            chk('the reminder asks rather than reports',
                'rate' in (any_row['title'] or '').lower(), any_row['title'])

        fresh = await reminders_for(c, fresh_offer_id)
        chk('a trade completed 2h ago is NOT reminded yet', len(fresh) == 0, len(fresh))

        print('3. RUN AGAIN — the idempotency guard')
        await run_once()
        sent2 = await reminders_for(c, offer_id)
        chk('a second run sends NOTHING (one reminder per party, ever)',
            len(sent2) == 2, f'{len(sent)} -> {len(sent2)}')

        print('4. A PARTY WHO HAS GRADED is skipped')
        # Delete the buyer's reminder so the worker would re-send it, then grade
        # as the buyer. If the grade check works, it stays absent.
        await c.execute(
            "DELETE FROM notification_history WHERE data->>'kind' = 'p2p_grade_reminder' "
            "AND data->>'offer_id' = $1 AND user_id::text = $2", offer_id, BUYER)
        await c.execute(
            "INSERT INTO member_grades (offer_id, rater_id, ratee_id, verdict) "
            "VALUES ($1::uuid, $2::uuid, $3::uuid, 'positive') "
            "ON CONFLICT (offer_id, rater_id) DO NOTHING",
            offer_id, BUYER, SELLER)
        await run_once()
        after_grade = await reminders_for(c, offer_id)
        chk('a party who already rated is not chased', BUYER not in after_grade,
            sorted(after_grade))
        chk('the party who has NOT rated keeps their single reminder',
            SELLER in after_grade)

    finally:
        print('5. CLEANUP')
        await c.execute("DELETE FROM notification_history WHERE data->>'offer_id' = ANY($1::text[])",
                        [offer_id, fresh_offer_id])
        await c.execute('DELETE FROM member_grades WHERE offer_id = ANY($1::uuid[])',
                        [offer_id, fresh_offer_id])
        await c.execute('DELETE FROM p2p_offers WHERE id = ANY($1::uuid[])',
                        [offer_id, fresh_offer_id])
        await c.execute('DELETE FROM marketplace_listings WHERE id = ANY($1::uuid[])',
                        [listing_id, fresh_listing_id])
        left_offers = await c.fetchval(
            'SELECT count(*) FROM p2p_offers WHERE id = ANY($1::uuid[])',
            [offer_id, fresh_offer_id])
        left_notifs = await c.fetchval(
            "SELECT count(*) FROM notification_history WHERE data->>'offer_id' = ANY($1::text[])",
            [offer_id, fresh_offer_id])
        chk('cleanup removed every seeded row', left_offers == 0 and left_notifs == 0,
            f'offers={left_offers} notifs={left_notifs}')
        print()
        print(f'RESULT: {len(OK)} passed, {len(FAIL)} failed')
        if FAIL:
            print('FAILED:', FAIL)
        await c.close()

    raise SystemExit(1 if FAIL else 0)


asyncio.run(main())
