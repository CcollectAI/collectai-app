"""E2E flow test for the P2P marketplace — RUNS AGAINST PROD.

Not a unit test and deliberately not named test_*, so pytest does not collect
it: it creates and deletes real rows. Run it manually on EC2:

    cd /opt/collectors/server && set -a && . /opt/collectors/.env && set +a && \
      PYTHONPATH=/opt/collectors/server /opt/collectors/.venv/bin/python \
      tests/e2e_p2p_flow.py

Covers the Stage 1 flow end to end: list (in USD) -> supply hook converts to
EUR -> buyer browses and filters -> deep link resolves -> DSA report ->
seller marks sold -> supply row removed -> seller keeps history -> buyer sees
"sold" rather than 404.

It has already earned its keep: it caught the seller-history query being
undeployed (the code was correct locally and the box was running the old
file), which a unit test could not have seen.
"""
import asyncio, os, asyncpg
from app.features.p2p_listing_router import (
    create_listing, browse_listings, get_listing, delist, report_listing,
    ListingCreate, ReportCreate, _publish_supply_hook,
)
SELLER = '4a1d7970-69a6-4575-aff3-8e1c52ae420a'
BUYER  = '00000000-0000-0000-0000-0000000000b2'
ITEM   = '8b439f25-a812-46aa-a918-28a50e081143'   # lorcana, canonical-matched
OK, FAIL = [], []
def chk(name, cond, detail=''):
    (OK if cond else FAIL).append(name)
    print(('  PASS  ' if cond else '  FAIL  ') + name + (' | ' + str(detail) if detail else ''))

async def main():
    from app.db import connect_pool
    await connect_pool()
    c = await asyncpg.connect(os.getenv('DB_DSN_DIRECT') or os.getenv('DB_DSN'))

    print('1. SELLER LISTS (USD, cross-currency)')
    out = await create_listing(ListingCreate(item_id=ITEM, price=25.00, currency='USD',
                                             condition_label='Near Mint', ships_from='Netherlands'), user_id=SELLER)
    chk('listing created', out.id is not None, out.id)
    chk('currency preserved as USD', out.currency == 'USD', out.currency)
    await _publish_supply_hook(out.id)

    print('2. CROSS-CURRENCY -> market_hits stores EUR')
    row = await c.fetchrow("SELECT price, currency, price_eur FROM market_hits WHERE provider='sparrow' AND listing_id=$1", out.id)
    chk('supply row written', row is not None)
    if row:
        chk('original currency kept', row['currency'] == 'USD', row['currency'])
        chk('price_eur converted (not equal to USD)', float(row['price_eur']) != 25.00, f"USD 25.00 -> EUR {row['price_eur']}")

    print('3. BUYER SEARCHES / FINDS')
    pub = await browse_listings(category=None, canonical_key=None, mine=False, user_id=BUYER, pagination=(50,0))
    found = [l for l in pub.listings if l.id == out.id]
    chk('appears in public browse', len(found) == 1)
    bycat = await browse_listings(category='lorcana', canonical_key=None, mine=False, user_id=BUYER, pagination=(50,0))
    chk('category filter finds it', any(l.id == out.id for l in bycat.listings))
    if found:
        chk('is_mine false for buyer', found[0].is_mine is False)

    print('4. BUYER OPENS DEEP LINK (Target Hit target)')
    d = await get_listing(out.id, user_id=BUYER)
    chk('deep link resolves', d.id == out.id)
    chk('seller credibility present', d.seller_collection_size >= 0, f'items={d.seller_collection_size} since={str(d.seller_since)[:10]}')
    chk('buyer sees active status', d.status == 'active')

    print('5. BUYER REPORTS (DSA)')
    await report_listing(out.id, ReportCreate(reason='Misleading description'), user_id=BUYER)
    rc = await c.fetchval('SELECT reports_count FROM marketplace_listings WHERE id=$1::uuid', out.id)
    await report_listing(out.id, ReportCreate(reason='Misleading description'), user_id=BUYER)
    rc2 = await c.fetchval('SELECT reports_count FROM marketplace_listings WHERE id=$1::uuid', out.id)
    chk('report recorded', rc == 1, rc)
    chk('duplicate report does not inflate', rc == rc2, f'{rc} -> {rc2}')

    print('6. SELLER MARKS SOLD')
    await delist(out.id, status='sold', user_id=SELLER)
    gone = await c.fetchval("SELECT count(*) FROM market_hits WHERE provider='sparrow' AND listing_id=$1", out.id)
    chk('supply row removed on sale', gone == 0, gone)
    pub2 = await browse_listings(category=None, canonical_key=None, mine=False, user_id=BUYER, pagination=(50,0))
    chk('hidden from public browse', not any(l.id == out.id for l in pub2.listings))

    print('7. SELLER STILL FINDS IT (history)')
    mine = await browse_listings(category=None, canonical_key=None, mine=True, user_id=SELLER, pagination=(50,0))
    m = [l for l in mine.listings if l.id == out.id]
    chk('sold listing visible to seller', len(m) == 1)
    if m:
        chk('status reads sold', m[0].status == 'sold', m[0].status)
    d2 = await get_listing(out.id, user_id=BUYER)
    chk('buyer sees sold, not 404', d2.status == 'sold')

    await c.execute('DELETE FROM listing_reports WHERE listing_id=$1::uuid', out.id)
    await c.execute('DELETE FROM marketplace_listings WHERE id=$1::uuid', out.id)
    print()
    print(f'RESULT: {len(OK)} passed, {len(FAIL)} failed')
    if FAIL: print('FAILED:', FAIL)
    await c.close()
asyncio.run(main())
