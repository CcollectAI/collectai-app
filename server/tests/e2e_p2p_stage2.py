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

    print('1. LISTING + OFFER')
    L = await create_listing(ListingCreate(item_id=ITEM, price=30.0, currency='EUR'), user_id=SELLER)
    await _publish_supply_hook(L.id)
    o = await create_offer(OfferCreate(listing_id=L.id, amount=24.0, currency='EUR', message='Would you take 24?'), user_id=BUYER)
    chk('offer created', o.status=='pending', o.status)
    chk('buyer flagged as buyer', o.i_am_buyer is True)
    chk('cannot grade yet', o.can_grade is False)

    print('2. GUARDS')
    chk('seller cannot offer on own listing', await err(create_offer(OfferCreate(listing_id=L.id, amount=5.0), user_id=SELLER),'OWN_LISTING'))
    chk('duplicate offer blocked', await err(create_offer(OfferCreate(listing_id=L.id, amount=26.0), user_id=BUYER),'OFFER_EXISTS'))
    chk('buyer cannot accept own offer', await err(respond_to_offer(o.id, action='accept', amount=None, user_id=BUYER),'SELLER_ONLY'))
    chk('grading blocked before completion', await err(grade_counterparty(o.id, GradeCreate(verdict='positive'), user_id=BUYER),'TRADE_NOT_COMPLETE'))

    print('3. NEGOTIATE -> ACCEPT')
    ctr = await respond_to_offer(o.id, action='counter', amount=27.0, user_id=SELLER)
    chk('counter recorded', ctr.status=='countered' and ctr.amount==27.0, f'{ctr.status} {ctr.amount}')
    acc = await respond_to_offer(o.id, action='accept', amount=None, user_id=SELLER)
    chk('accepted', acc.status=='accepted')
    res = await c.fetchval('SELECT reserved_offer_id FROM marketplace_listings WHERE id=$1::uuid', L.id)
    chk('listing soft-reserved', str(res)==o.id)
    still = await c.fetchval("SELECT count(*) FROM marketplace_listings WHERE id=$1::uuid AND status='active' AND delisted_at IS NULL", L.id)
    chk('accept does NOT delist (soft reserve)', still==1)

    print('4. TWO-SIDED COMPLETION')
    s1 = await confirm_exchange(o.id, user_id=SELLER)
    chk('seller confirmed', s1.seller_confirmed_at is not None)
    chk('not complete on one side', s1.status!='completed', s1.status)
    chk('grading still blocked', await err(grade_counterparty(o.id, GradeCreate(verdict='positive'), user_id=SELLER),'TRADE_NOT_COMPLETE'))
    chk('cannot double-confirm', await err(confirm_exchange(o.id, user_id=SELLER),'ALREADY_CONFIRMED'))
    s2 = await confirm_exchange(o.id, user_id=BUYER)
    chk('completed on both sides', s2.status=='completed', s2.status)
    chk('can_grade now true', s2.can_grade is True)
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

    await c.execute('DELETE FROM member_grades WHERE offer_id=$1::uuid', o.id)
    await c.execute('DELETE FROM offers WHERE id=$1::uuid', o.id)
    await c.execute('DELETE FROM marketplace_listings WHERE id=$1::uuid', L.id)
    print()
    print(f'RESULT: {len(OK)} passed, {len(FAIL)} failed')
    if FAIL: print('FAILED:', FAIL)
    await c.close()
asyncio.run(main())
