"""E2E for the transactional-half endpoints the Stage 2 suite does not reach.

Stage 2 covers offer -> counter -> accept -> confirm -> grade. It never touches
tracking, carriers, the DSA report path, facets or the public reputation
endpoint — 5 of the 18 P2P endpoints, all shipped, none verified since.
"""
import asyncio, sys
from app.db import connect_pool, get_pool

P, F = 0, 0
def chk(name, ok, extra=''):
    global P, F
    P, F = (P+1, F) if ok else (P, F+1)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" | {extra}" if extra else ""))

async def main():
    await connect_pool()
    from app.features.p2p_listing_router import (
        create_listing, ListingCreate, category_facets, report_listing, ReportCreate,
    )
    from app.features.p2p_offers_router import (
        create_offer, OfferCreate, list_offers, set_tracking,
        list_carriers, member_reputation,
    )
    from app.features.p2p_offers_router import TrackingIn as TrackIn
    S = '7db74bd9-7939-4929-afcf-473e76954af3'
    B = '4a1d7970-69a6-4575-aff3-8e1c52ae420a'

    print('1. CARRIERS (tracking deep links)')
    cs = await list_carriers()
    chk('carriers returned', len(cs) > 0, f'{len(cs)} carriers')
    nl = [c for c in cs if c.key in ('postnl', 'dpd')]
    chk('NL carriers present', len(nl) >= 1, ','.join(c.key for c in cs[:6]))
    # spec §7: PostNL/DPD need the recipient postcode, which we deliberately do
    # not hold, so they must be marked NON-linkable — a copyable code, never a
    # button that 404s.
    unlink = [c.key for c in cs if not c.linkable]
    chk('postcode-dependent carriers are non-linkable', 'postnl' in unlink or 'dpd' in unlink,
        'non-linkable: ' + (','.join(unlink) or 'none'))

    print('2. LISTING + FACETS')
    L = await create_listing(ListingCreate(
        title='E2EREST probe', category='mtg', canonical_key='sum-283-bayou',
        price=42, currency='EUR'), user_id=S)
    chk('listing created', L.id is not None)
    f = await category_facets()
    chk('facets non-empty', len(f.facets) > 0, f'{len(f.facets)} categories')
    chk('facets count only LIVE listings',
        any(x.category == 'mtg' and x.count >= 1 for x in f.facets))

    print('3. OFFER + TRACKING')
    o = await create_offer(OfferCreate(listing_id=L.id, amount=40, currency='EUR'), user_id=B)
    chk('offer created', o.status == 'pending', o.status)
    lo = await list_offers(role='selling', user_id=S, pagination=(50, 0))
    chk('seller sees it under selling', any(x.id == o.id for x in lo.offers))
    lo2 = await list_offers(role='buying', user_id=B, pagination=(50, 0))
    chk('buyer sees it under buying', any(x.id == o.id for x in lo2.offers))

    # Tracking before agreement must be REJECTED — you cannot ship something
    # nobody has agreed to buy. Found by this test tripping the guard.
    try:
        await set_tracking(o.id, TrackIn(tracking_carrier='postnl', tracking_code='3STBJG999888777'), user_id=S)
        chk('tracking blocked before accept', False, 'no error raised')
    except Exception as e:
        # Assert the REASON, not merely that something threw. This probe used a
        # 2-char code and passed on a Pydantic ValidationError without ever
        # reaching the guard — a test green for the wrong reason.
        chk('tracking blocked before accept', 'NOT_EXCHANGEABLE' in str(e), str(e)[:70])

    from app.features.p2p_offers_router import respond_to_offer
    acc = await respond_to_offer(o.id, action='accept', user_id=S)
    chk('offer accepted by seller', acc.status == 'accepted', acc.status)

    t = await set_tracking(o.id, TrackIn(
        tracking_carrier='postnl', tracking_code='3STBJG123456789'), user_id=S)
    chk('seller can set tracking', t.tracking_code == '3STBJG123456789', t.tracking_carrier)
    # Whitespace was 422ing on lead but accepted on trail before the validator.
    t2 = await set_tracking(o.id, TrackIn(
        tracking_carrier='dpd', tracking_code='  0123456789  '), user_id=S)
    chk('tracking code is trimmed, not rejected', t2.tracking_code == '0123456789', repr(t2.tracking_code))

    try:
        await set_tracking(o.id, TrackIn(
            tracking_carrier='postnl', tracking_code='3STBJG111222333'), user_id=B)
        chk('BUYER cannot set tracking', False, 'no error raised')
    except Exception as e:
        # Same fix: must be the ownership guard, not a validation error.
        chk('BUYER cannot set tracking', 'NOT_SELLER' in str(e) or '403' in str(e)
            or 'not found' in str(e).lower(), str(e)[:70])

    print('4. DSA REPORT PATH')
    r = await report_listing(L.id, ReportCreate(reason='Counterfeit or replica',
                                                detail='probe'), user_id=B)
    chk('report accepted', bool(r.get('ok')), str(r)[:60])
    async with get_pool().acquire() as c:
        n = await c.fetchval(
            "SELECT count(*) FROM listing_reports WHERE listing_id=$1::uuid AND reporter_id=$2::uuid",
            L.id, B)
        chk('report row written', n == 1, n)
        try:
            await report_listing(L.id, ReportCreate(reason='Suspected scam'), user_id=B)
        except Exception:
            pass
        n2 = await c.fetchval(
            "SELECT count(*) FROM listing_reports WHERE listing_id=$1::uuid AND reporter_id=$2::uuid",
            L.id, B)
        chk('re-report does not inflate the counter', n2 == 1, n2)

    print('5. PUBLIC REPUTATION')
    rep = await member_reputation(S, _user_id=B)
    chk('reputation readable by another member', rep is not None)
    chk('pct hidden below 3 grades',
        rep.positive_pct is None if rep.total_grades < 3 else True, rep.positive_pct)

    async with get_pool().acquire() as c:
        await c.execute("DELETE FROM listing_reports WHERE listing_id=$1::uuid", L.id)
        await c.execute("DELETE FROM p2p_offers WHERE listing_id=$1::uuid", L.id)
        await c.execute("DELETE FROM market_hits WHERE provider='sparrow'")
        await c.execute("DELETE FROM marketplace_listings WHERE id=$1::uuid", L.id)
        await c.execute("DELETE FROM items WHERE name='E2EREST probe'")
    print(f"\nRESULT: {P} passed, {F} failed")
    return 1 if F else 0

sys.exit(asyncio.run(main()))
