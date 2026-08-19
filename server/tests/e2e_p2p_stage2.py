import asyncio, os, asyncpg
from app.features.p2p_listing_router import create_listing, ListingCreate, _publish_supply_hook
from app.features.p2p_offers_router import (
    create_offer, list_offers, respond_to_offer, confirm_exchange,
    grade_counterparty, member_reputation, OfferCreate, GradeCreate,
)
SELLER='4a1d7970-69a6-4575-aff3-8e1c52ae420a'
BUYER='7c9e1a44-0000-4000-8000-00000000b002'
ITEM='8b439f25-a812-46aa-a918-28a50e081143'
OK,FAIL=[],[]
def chk(n,c,d=''):
    (OK if c else FAIL).append(n); print(('  PASS  ' if c else '  FAIL  ')+n+(' | '+str(d) if d else ''))
async def err(coro, code):
    try:
        await coro; return False
    except Exception as e:
        return code in str(getattr(e,'detail',e)) or code in str(e)

async def main():
    from app.db import connect_pool; await connect_pool()
    c = await asyncpg.connect(os.getenv('DB_DSN_DIRECT') or os.getenv('DB_DSN'))
    await c.execute("INSERT INTO auth.users (id, email) VALUES ($1::uuid,'e2e-buyer@test.local') ON CONFLICT DO NOTHING", BUYER)

    # NOTIFICATIONS. Asserted per step, because "both parties know what is
    # happening" is the difference between a marketplace and a form. Nothing
    # checked this until 2026-08-09, and nothing SENT them either: the only
    # notify_user call in the offers router was the DAC7 threshold notice, while
    # the listing screen told buyers "the seller will be notified".
    async def notif_count(uid):
        return await c.fetchval(
            "SELECT count(*) FROM notification_history WHERE user_id=$1::uuid", uid)
    async def latest_notif(uid):
        return await c.fetchrow(
            "SELECT title, body, type FROM notification_history WHERE user_id=$1::uuid "
            "ORDER BY created_at DESC LIMIT 1", uid)
    n_seller0, n_buyer0 = await notif_count(SELLER), await notif_count(BUYER)

    print('1. LISTING + OFFER')
    L = await create_listing(ListingCreate(item_id=ITEM, price=30.0, currency='EUR'), user_id=SELLER)
    await _publish_supply_hook(L.id)
    o = await create_offer(OfferCreate(listing_id=L.id, amount=24.0, currency='EUR', message='Would you take 24?'), user_id=BUYER)
    chk('offer created', o.status=='pending', o.status)
    chk('buyer flagged as buyer', o.i_am_buyer is True)
    chk('cannot grade yet', o.can_grade is False)
    chk('SELLER notified of the new offer', await notif_count(SELLER) == n_seller0 + 1,
        await latest_notif(SELLER))

    print('2. GUARDS')
    chk('seller cannot offer on own listing', await err(create_offer(OfferCreate(listing_id=L.id, amount=5.0), user_id=SELLER),'OWN_LISTING'))
    chk('duplicate offer blocked', await err(create_offer(OfferCreate(listing_id=L.id, amount=26.0), user_id=BUYER),'OFFER_EXISTS'))
    chk('buyer cannot accept own offer', await err(respond_to_offer(o.id, action='accept', amount=None, user_id=BUYER),'SELLER_ONLY'))
    chk('grading blocked before completion', await err(grade_counterparty(o.id, GradeCreate(verdict='positive'), user_id=BUYER),'TRADE_NOT_COMPLETE'))

    print('3. NEGOTIATE -> ACCEPT')
    ctr = await respond_to_offer(o.id, action='counter', amount=27.0, user_id=SELLER)
    chk('counter recorded', ctr.status=='countered' and ctr.amount==27.0, f'{ctr.status} {ctr.amount}')
    chk('BUYER notified of the counter', await notif_count(BUYER) == n_buyer0 + 1,
        await latest_notif(BUYER))
    # A COUNTER IS THE BUYER'S TO ANSWER (changed 2026-08-15, see
    # P2P_MARKETPLACE_SPEC.md "The buyer answers a counter"). This test still
    # had the SELLER accepting their own counter and had not been run since, so
    # it failed with BUYER_ONLY — the test pinned the old contract, the server
    # was right. Assert the guard too, so the direction cannot silently flip
    # back.
    chk('seller cannot accept their OWN counter',
        await err(respond_to_offer(o.id, action='accept', amount=None, user_id=SELLER), 'BUYER_ONLY'))
    acc = await respond_to_offer(o.id, action='accept', amount=None, user_id=BUYER)
    chk('buyer accepts the counter', acc.status=='accepted', acc.status)
    chk('SELLER notified of the acceptance', await notif_count(SELLER) >= n_seller0 + 2,
        await latest_notif(SELLER))
    res = await c.fetchval('SELECT reserved_offer_id FROM marketplace_listings WHERE id=$1::uuid', L.id)
    chk('listing soft-reserved', str(res)==o.id)
    still = await c.fetchval("SELECT count(*) FROM marketplace_listings WHERE id=$1::uuid AND status='active' AND delisted_at IS NULL", L.id)
    chk('accept does NOT delist (soft reserve)', still==1)

    print('4. TWO-SIDED COMPLETION')
    s1 = await confirm_exchange(o.id, user_id=SELLER)
    chk('seller confirmed', s1.seller_confirmed_at is not None)
    chk('not complete on one side', s1.status!='completed', s1.status)
    # +2, not +3: the buyer gets the counter and the seller's confirmation. The
    # acceptance notice now goes to the SELLER, because the buyer is the one who
    # accepted it — see the notification fix in p2p_offers_router.py.
    chk('BUYER told the seller confirmed', await notif_count(BUYER) == n_buyer0 + 2,
        await latest_notif(BUYER))
    chk('grading still blocked', await err(grade_counterparty(o.id, GradeCreate(verdict='positive'), user_id=SELLER),'TRADE_NOT_COMPLETE'))
    chk('cannot double-confirm', await err(confirm_exchange(o.id, user_id=SELLER),'ALREADY_CONFIRMED'))
    s2 = await confirm_exchange(o.id, user_id=BUYER)
    chk('completed on both sides', s2.status=='completed', s2.status)
    chk('can_grade now true', s2.can_grade is True)
    chk('BOTH told the trade completed',
        await notif_count(SELLER) == n_seller0 + 3 and await notif_count(BUYER) == n_buyer0 + 3,
        f'seller {await notif_count(SELLER)} (was {n_seller0}), buyer {await notif_count(BUYER)} (was {n_buyer0})')
    # SETTLEMENT — the object must move, not just the paperwork.
    seller_item = await c.fetchrow(
        'select archived, for_sale, quantity from items where id=$1::uuid', ITEM)
    chk('seller item retired (archived, no longer for sale)',
        seller_item is not None and seller_item['archived'] is True
        and seller_item['for_sale'] is not True,
        dict(seller_item) if seller_item else None)
    bought = await c.fetchrow(
        """select name, category, canonical_key, condition, image_url, source,
                  purchase_price, purchase_price_eur, purchased_at, purchase_date,
                  acquired_from, description
             from items where user_id=$1::uuid and acquired_from=$2""",
        BUYER, f'sparrow:offer:{o.id}')
    chk('buyer got their own item', bought is not None)
    if bought:
        chk('buyer item carries the AGREED price as cost basis',
            float(bought['purchase_price_eur']) == 27.0, bought['purchase_price_eur'])
        chk('paired-column trigger derived purchase_date from purchased_at',
            bought['purchase_date'] is not None and bought['purchased_at'] is not None,
            f"{bought['purchase_date']} / {bought['purchased_at']}")
        chk('buyer item is catalogue-identified (prices + set completion work)',
            bought['canonical_key'] is not None or bought['category'] is not None,
            f"{bought['canonical_key']} / {bought['category']}")
        # The listing in this run has photo_catalogue_consent unset, so the
        # seller's photograph must NOT have been copied.
        chk('seller photo NOT copied without consent', bought['image_url'] is None,
            bought['image_url'])
        chk('buyer item marked source=marketplace', bought['source'] == 'marketplace',
            bought['source'])
    # The seller's PRIVATE data must not have travelled.
    leaked = await c.fetchval(
        """select count(*) from items where user_id=$1::uuid and acquired_from=$2
             and (purchase_notes is not null or cost_basis is not null)""",
        BUYER, f'sparrow:offer:{o.id}')
    chk('seller purchase notes / cost basis NOT leaked to the buyer', leaked == 0, leaked)
    resv = await c.fetchval(
        'select reserved_offer_id from marketplace_listings where id=$1::uuid', L.id)
    chk('soft reservation released on completion', resv is None, resv)

    dac7 = await c.fetchrow(
        'SELECT sales_count, gross_eur FROM dac7_seller_year WHERE user_id=$1::uuid '
        'AND year=EXTRACT(YEAR FROM now())::int', SELLER)
    chk('DAC7 accrued the AGREED amount on completion',
        dac7 is not None and dac7['sales_count'] == 1 and float(dac7['gross_eur']) == 27.0,
        None if dac7 is None else f"{dac7['sales_count']} x {float(dac7['gross_eur'])}")
    # STRENGTHENED 2026-08-08. This asserted `count(*) == 0` for ALL sparrow rows,
    # which was right when written and became wrong when _sold_comp_hook landed
    # (spec §1g): completion now DELETES the buyable row and INSERTS a sold comp,
    # so one row legitimately remains. The old assertion failed on correct code —
    # a stale test reporting a bug that is not there, which costs exactly as much
    # trust as one that hides a bug that is.
    #
    # Now checks both halves of the closed loop, which is strictly stronger than
    # what it replaced.
    buyable = await c.fetchval(
        "SELECT count(*) FROM market_hits WHERE provider='sparrow' AND listing_id=$1 "
        "AND is_listing IS TRUE AND url IS NOT NULL", L.id)
    chk('buyable row removed on completion', buyable==0, buyable)
    comp = await c.fetchrow(
        "SELECT price, source, is_listing FROM market_hits "
        "WHERE provider='sparrow' AND listing_id=$1 AND is_listing IS FALSE", L.id)
    chk('sold comp written at the AGREED price', comp is not None and float(comp['price'])==27.0,
        None if comp is None else float(comp['price']))
    chk('sold comp tagged sparrow_p2p (separable from scraped supply)',
        comp is not None and comp['source']=='sparrow_p2p')

    print('5. MUTUAL GRADING')
    await grade_counterparty(o.id, GradeCreate(verdict='positive', note='Fast and honest'), user_id=BUYER)
    await grade_counterparty(o.id, GradeCreate(verdict='positive'), user_id=SELLER)
    rep = await member_reputation(SELLER, _user_id=BUYER)
    chk('seller has a grade', rep.total_grades>=1, f'{rep.positive_grades}/{rep.total_grades}')
    chk('pct hidden below 3 grades', rep.positive_pct is None if rep.total_grades<3 else True, rep.positive_pct)
    chk('completed trade counted', rep.completed_trades>=1, rep.completed_trades)
    n = await c.fetchval('SELECT count(*) FROM member_grades WHERE offer_id=$1::uuid', o.id)
    await grade_counterparty(o.id, GradeCreate(verdict='negative', note='changed mind'), user_id=BUYER)
    n2 = await c.fetchval('SELECT count(*) FROM member_grades WHERE offer_id=$1::uuid', o.id)
    chk('re-grade edits, does not double-vote', n==n2==2, f'{n} -> {n2}')

    # CLEANUP. `offers` is the deal-desk table and was DROPPED with Deal Desk on
    # 2026-08-09, so the old `DELETE FROM offers` raised UndefinedTableError here
    # and every run since left its offer, listing, market_hits and DAC7 row behind
    # (prod had 6 stray p2p_offers rows). P2P offers live in `p2p_offers`.
    await c.execute('DELETE FROM member_grades WHERE offer_id=$1::uuid', o.id)
    await c.execute('DELETE FROM p2p_offers WHERE id=$1::uuid', o.id)
    await c.execute('DELETE FROM market_hits WHERE provider=$1 AND listing_id=$2', 'sparrow', L.id)
    await c.execute('DELETE FROM marketplace_listings WHERE id=$1::uuid', L.id)
    # Completion accrues DAC7 against the SELLER, so a test trade must not leave a
    # compliance counter behind claiming a real sale happened.
    await c.execute(
        'DELETE FROM dac7_seller_year WHERE user_id=$1::uuid AND year=EXTRACT(YEAR FROM now())::int',
        SELLER)
    await c.execute(
        "DELETE FROM notification_history WHERE data->>'offer_id' = $1", o.id)
    # Settlement side effects: the buyer's new item, and the seller's item state.
    await c.execute("DELETE FROM items WHERE user_id=$1::uuid AND acquired_from=$2",
                    BUYER, f'sparrow:offer:{o.id}')
    await c.execute(
        "UPDATE items SET archived = FALSE, for_sale = FALSE WHERE id=$1::uuid", ITEM)
    leftover = await c.fetchval('SELECT count(*) FROM p2p_offers WHERE id=$1::uuid', o.id)
    chk('cleanup removed the test offer', leftover == 0, leftover)
    print()
    print(f'RESULT: {len(OK)} passed, {len(FAIL)} failed')
    if FAIL: print('FAILED:', FAIL)
    await c.close()
asyncio.run(main())
