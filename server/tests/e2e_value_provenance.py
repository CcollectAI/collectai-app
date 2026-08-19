"""E2E: what a number on screen is allowed to claim, against a real database.

WHY THIS EXISTS
`v_item_values_v1.value_source` decides whether the app calls a figure a
"Market estimate" or "Your estimate", whether the leaderboard ranks it, and
whether analytics counts it as market value. All of that rests on a CASE whose
branches are chosen by which link of the chain answered — and the chain's order
changed twice on 2026-08-19 (member choice added, then catalogue-first). Unit
tests cannot reach it: the view is `auth.uid()`-scoped and reads
`price_predictions`, which RLS denies to every client.

So this drives real rows through the real view under a real auth context, and
asserts the label follows the value at every branch:

  1. a typed number            -> user_estimate
  2. a scan's number           -> app_estimate  (attrs.value_entry='app')
  3. a catalogue-linked item   -> catalog_model OUTRANKS the estimate
  4. the member says "keep mine" -> their number outranks the model again
  5. /portfolio/items agrees with the view — two implementations, one answer
  6. an estimate NEVER reaches the leaderboard's market-truth total

Run FROM EC2 (the direct DSN does not resolve from a laptop):

    cd /opt/collectors/server
    set -a && . /opt/collectors/.env && set +a
    PYTHONPATH=/opt/collectors/server /opt/collectors/.venv/bin/python \
        tests/e2e_value_provenance.py

Everything it writes, it deletes. The final check asserts that.
"""
import asyncio
import os
import uuid

import asyncpg

OWNER = '4a1d7970-69a6-4575-aff3-8e1c52ae420a'

OK, FAIL = [], []


def chk(name, cond, detail=''):
    (OK if cond else FAIL).append(name)
    print(('  PASS  ' if cond else '  FAIL  ') + name + (' | ' + str(detail) if detail else ''))


async def view_row(c, item_id):
    """The canonical value + provenance, as the app sees it.

    Requires the auth context to be set with `FALSE` (session-scoped). With
    TRUE it is transaction-local, and a view keyed on auth.uid() would then be
    compared against itself under an empty context — agreeing trivially and
    proving nothing (learning_prove_view_equivalence_with_real_auth_context).
    """
    return await c.fetchrow(
        'SELECT value_eur, value_source FROM public.v_item_values_v1 WHERE item_id = $1::uuid',
        item_id)


async def main():
    dsn = os.getenv('DB_DSN_DIRECT') or os.getenv('DB_DSN')
    c = await asyncpg.connect(dsn)
    await c.execute("SELECT set_config('request.jwt.claim.sub', $1, FALSE)", OWNER)

    typed_id = str(uuid.uuid4())
    scan_id = str(uuid.uuid4())
    catalog_id = str(uuid.uuid4())
    ids = [typed_id, scan_id, catalog_id]

    try:
        # A catalogue key that genuinely HAS a live model price, rather than one
        # invented for the test — the whole point is to prove the real join.
        ref = await c.fetchval(
            'SELECT item_ref FROM public.price_predictions '
            'WHERE q50 IS NOT NULL ORDER BY generated_at DESC LIMIT 1')
        model_price = await c.fetchval(
            'SELECT q50 FROM public.price_predictions WHERE item_ref = $1 '
            'ORDER BY generated_at DESC LIMIT 1', ref)
        chk('found a catalogue ref with a live model price', ref is not None, f'{ref} = {model_price}')

        print('1. SEED three items')
        await c.execute(
            "INSERT INTO items (id, user_id, name, title, category, estimated_value, source) "
            "VALUES ($1::uuid,$2::uuid,'E2E typed','E2E typed','lego',42.00,'manual')",
            typed_id, OWNER)
        await c.execute(
            "INSERT INTO items (id, user_id, name, title, category, estimated_value, attrs, source) "
            "VALUES ($1::uuid,$2::uuid,'E2E scan','E2E scan','lego',99.00,"
            "'{\"value_entry\":\"app\"}'::jsonb,'manual')",
            scan_id, OWNER)
        # `canonical_ref` is TRIGGER-DERIVED (`trg_items_canonical_ref`) from
        # `category || ':' || canonical_key` — setting it directly is silently
        # overwritten, which is what the first run of this test did. Seed the
        # two halves the trigger reads and let it build the ref.
        cat, _, key = ref.partition(':')
        await c.execute(
            "INSERT INTO items (id, user_id, name, title, category, estimated_value, "
            "canonical_key, source) "
            "VALUES ($1::uuid,$2::uuid,'E2E catalogued','E2E catalogued',$3,7.00,$4,'manual')",
            catalog_id, OWNER, cat, key)
        got_ref = await c.fetchval(
            'SELECT canonical_ref FROM items WHERE id = $1::uuid', catalog_id)
        chk('the trigger resolved the catalogue ref', got_ref == ref, f'{got_ref} vs {ref}')

        print('2. THE LABEL FOLLOWS THE VALUE')
        r = await view_row(c, typed_id)
        chk('a typed number reports as user_estimate',
            r and r['value_source'] == 'user_estimate' and round(r['value_eur'], 2) == 42.00,
            dict(r) if r else None)

        r = await view_row(c, scan_id)
        chk("a scan's number reports as app_estimate, not as the member's",
            r and r['value_source'] == 'app_estimate' and round(r['value_eur'], 2) == 99.00,
            dict(r) if r else None)

        r = await view_row(c, catalog_id)
        chk('a catalogue-linked item takes the MODEL price, not the estimate',
            r and r['value_source'] == 'catalog_model'
            and round(float(r['value_eur']), 4) == round(float(model_price), 4),
            dict(r) if r else None)

        print('3. THE MEMBER CAN OVERRIDE THE MODEL')
        await c.execute(
            "UPDATE items SET attrs = COALESCE(attrs,'{}'::jsonb) || "
            "'{\"value_choice\":\"mine\"}'::jsonb WHERE id = $1::uuid", catalog_id)
        r = await view_row(c, catalog_id)
        chk('"keep mine" outranks the model, and says so',
            r and r['value_source'] == 'user_estimate' and round(r['value_eur'], 2) == 7.00,
            dict(r) if r else None)

        await c.execute(
            "UPDATE items SET attrs = attrs - 'value_choice' WHERE id = $1::uuid", catalog_id)
        r = await view_row(c, catalog_id)
        chk('withdrawing the choice returns the model price',
            r and r['value_source'] == 'catalog_model', dict(r) if r else None)

        print('4. THE SERVER ENDPOINT AGREES WITH THE VIEW')
        # /portfolio/items retypes the chain (the view is auth.uid()-scoped and
        # the pool has no auth context), so the two CAN drift. This is the only
        # place that proves they do not.
        from app.db import connect_pool
        await connect_pool()
        from app.routes.portfolio_router import portfolio_items
        resp = await portfolio_items(user_id=OWNER)
        # str() on both sides: asyncpg hands back UUID objects and the seeded
        # ids are strings, so a raw dict lookup misses every row — the first
        # run reported "endpoint=None" for all three and looked like the
        # endpoint had dropped them.
        by_id = {str(i['id']): i for i in resp['items']}
        for label, iid in (('typed', typed_id), ('scan', scan_id), ('catalogued', catalog_id)):
            v = await view_row(c, iid)
            e = by_id.get(iid)
            chk(f'endpoint and view agree on the {label} item',
                e is not None and e['value_source'] == v['value_source']
                and round(float(e['current_value']), 2) == round(float(v['value_eur']), 2),
                f"endpoint={e and (e['current_value'], e['value_source'])} "
                f"view={(round(v['value_eur'],2), v['value_source'])}")

        print('5. AN ESTIMATE NEVER REACHES THE PUBLIC BOARD')
        # The leaderboard sums market-backed links only. Both estimate items
        # must contribute exactly nothing.
        board_total = await c.fetchval(
            """
            SELECT COALESCE(SUM(COALESCE(
                (SELECT pp.q50 FROM public.price_predictions pp
                  WHERE pp.item_ref = i.canonical_ref
               ORDER BY pp.generated_at DESC LIMIT 1),
                (SELECT qp.q50_eur FROM public.quick_predictions qp
                  WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
                0)), 0)::float8
              FROM public.items i WHERE i.id = ANY($1::uuid[])
            """,
            [typed_id, scan_id])
        chk('two estimate-backed items contribute 0.00 to the board', board_total == 0,
            board_total)

    finally:
        print('6. CLEANUP')
        await c.execute('DELETE FROM items WHERE id = ANY($1::uuid[])', ids)
        left = await c.fetchval('SELECT count(*) FROM items WHERE id = ANY($1::uuid[])', ids)
        chk('cleanup removed every seeded item', left == 0, left)
        print()
        print(f'RESULT: {len(OK)} passed, {len(FAIL)} failed')
        if FAIL:
            print('FAILED:', FAIL)
        await c.close()

    raise SystemExit(1 if FAIL else 0)


asyncio.run(main())
