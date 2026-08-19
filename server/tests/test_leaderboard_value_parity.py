"""The category leaderboard's value column must be the MARKET-BACKED SUBSET of
the canonical item value.

CHANGED 2026-08-19 - read this before "restoring" the old equality
------------------------------------------------------------------
This test used to assert the board equalled `v_item_values_v1` item for item.
It must not, any more. The board is the one number in the app that ranks
members against each other in public, and the canonical chain ends in two
member-supplied columns:

  * `items.estimated_value` - typed by the member, or by a CSV import
  * `items.predicted_price_eur` - despite the name, its ONLY writer is
    add-manual's "Estimated value" text field

Ranking on those means anyone can top a category by typing a bigger number
into their own item. So the board stops after the two comp/model links, and
this test pins the exact relationship instead of equality:

    value_source is market-backed  ->  board value == canonical value
    value_source is an estimate    ->  board value == 0

checkable precisely because `v_item_values_v1` gained `value_source` the same
day.


WHAT WENT WRONG (2026-08-16, found 2026-08-17)
----------------------------------------------
`GET /social/leaderboard/category/{id}?metric=value` computed its own COALESCE
chain in SQL. It was written from `portfolio_router.py` and looked right, but it
dropped ONE step — `price_predictions.q50` joined on `items.canonical_ref`. The
board therefore ranked members by a number no other screen in the app agreed
with:

    user b4271bd3   leaderboard  EUR    78.90   portfolio  EUR   185.15
    user 7db74bd9   leaderboard  EUR     0.00   portfolio  EUR    35.37

8 of 74 live items differed. Nothing failed: a leaderboard with plausible
numbers on it looks exactly like a correct one, and a member who is ranked too
low never sees the row that would tell them.

WHY A TEST AND NOT A REUSED VIEW
--------------------------------
`public.v_item_values_v1` is the canonical definition, and the obvious fix is to
select from it. It cannot be done: the view ends `WHERE user_id = auth.uid()`,
so it answers "what is MY collection worth" and returns nothing when aggregating
across members. The chain therefore HAS to be duplicated in the router, and a
duplicated definition is one that drifts — so this test pins the duplicate to
the original instead of pretending it will stay in step.

`npm run check:item-value-source` does not cover this. It checks the FE provider
and `mapItemRow`; SQL living inside a Python string is invisible to a JS
checker.

WHY THE auth CONTEXT IS SET WITH FALSE
--------------------------------------
`set_config(..., FALSE)` is session-scoped. Passing TRUE makes it transaction-
local, which for a view keyed on `auth.uid()` means comparing the view against
itself under the same empty context — the two sides agree trivially and the test
passes while proving nothing.

Run FROM EC2:
    cd /opt/collectors/server
    set -a && . /opt/collectors/.env && set +a
    PYTHONPATH=/opt/collectors/server /opt/collectors/.venv/bin/python \
        tests/test_leaderboard_value_parity.py
"""
import asyncio
import os
import re
import sys

import asyncpg

# The chain as the router computes it. Kept as one string so the test fails if
# somebody edits the router without editing here — which is the point.
ROUTER_VALUE_EXPR = """
    COALESCE(
        (SELECT pp.q50 FROM public.price_predictions pp
          WHERE pp.item_ref = i.canonical_ref ORDER BY pp.generated_at DESC LIMIT 1),
        (SELECT qp.q50_eur FROM public.quick_predictions qp
          WHERE qp.item_id = i.id ORDER BY qp.created_at DESC LIMIT 1),
        0
    )::float8
"""

# `v_item_values_v1.value_source` values that rest on market data. Must match
# MARKET_SOURCES in src/components/ValueSourceChip.tsx - the FE decides what to
# LABEL a market estimate and this decides what to RANK on; the two disagreeing
# would mean the app calls a number market-backed on one screen and refuses to
# rank it on another.
MARKET_SOURCES = ('catalog_daily', 'quick_scan', 'catalog_model')

ROUTER_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "features", "social_router.py")


def env(k: str) -> str:
    v = os.environ.get(k)
    if v:
        return v
    for line in open("/opt/collectors/.env"):
        m = re.match(r"\s*" + k + r"\s*=\s*(.+)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("missing " + k)


failures: list[str] = []


def chk(name: str, ok: bool, detail: str = "") -> None:
    print(("  PASS  " if ok else "  FAIL  ") + name + (f" | {detail}" if detail else ""))
    if not ok:
        failures.append(f"{name} | {detail}")


async def main() -> int:
    conn = await asyncpg.connect(env("DB_DSN_DIRECT"))
    try:
        # 1. The router still asks for every step. A structural check, because a
        #    dropped step is precisely how this broke and it is cheap to catch
        #    before touching the database at all.
        src = open(ROUTER_PATH).read()
        for needle, label in [
            ("quick_predictions", "quick_predictions.q50_eur"),
            ("price_predictions", "price_predictions.q50"),
            ("canonical_ref", "joined on items.canonical_ref"),
        ]:
            chk(f"router value chain still includes {label}", needle in src)

        # And the member-supplied columns are NOT summed into the board.
        # Scoped to the leaderboard SUM rather than the whole file, because
        # both names legitimately appear elsewhere in it.
        sum_block = ""
        if "AS total_value" in src:
            end = src.index("AS total_value")
            sum_block = src[src.rindex("COALESCE(SUM(", 0, end):end]
        chk("the board SUM was located", bool(sum_block))
        for needle in ("predicted_price_eur", "estimated_value"):
            chk(
                f"board does NOT rank on member-supplied {needle}",
                needle not in sum_block,
                "a member could top a category by typing a bigger number",
            )

        # 2. The chain equals the canonical view, item by item, under a real
        #    auth context for each member who actually holds something.
        users = await conn.fetch(
            """SELECT user_id::text AS u FROM public.items
                WHERE COALESCE(archived, FALSE) = FALSE
             GROUP BY 1 ORDER BY count(*) DESC LIMIT 10"""
        )
        chk("there are members holding items to compare", len(users) > 0, f"{len(users)} member(s)")

        total_items = 0
        total_diff = 0
        for row in users:
            uid = row["u"]
            await conn.execute("SELECT set_config('request.jwt.claim.sub', $1, FALSE)", uid)
            r = await conn.fetchrow(
                f"""
                SELECT count(*) AS n,
                       count(*) FILTER (
                         WHERE src = ANY($2::text[]) AND router IS DISTINCT FROM canonical
                       ) AS n_diff,
                       count(*) FILTER (
                         WHERE NOT (src = ANY($2::text[])) AND router <> 0
                       ) AS n_leaked,
                       count(*) FILTER (WHERE src = ANY($2::text[])) AS n_market,
                       round(sum(router)::numeric, 2)    AS sum_router,
                       round(sum(canonical)::numeric, 2) AS sum_canonical
                  FROM (
                    SELECT i.id,
                           {ROUTER_VALUE_EXPR} AS router,
                           COALESCE(v.value_eur, 0)::float8 AS canonical,
                           COALESCE(v.value_source, 'none') AS src
                      FROM public.items i
                      LEFT JOIN public.v_item_values_v1 v ON v.item_id = i.id
                     WHERE i.user_id = $1::uuid
                       AND COALESCE(i.archived, FALSE) = FALSE
                  ) t
                """,
                uid,
                list(MARKET_SOURCES),
            )
            total_items += r["n"]
            total_diff += r["n_diff"] + r["n_leaked"]
            chk(
                f"member {uid[:8]}: market-backed items agree with the portfolio",
                r["n_diff"] == 0,
                f"{r['n_diff']}/{r['n_market']} market item(s) differ; "
                f"router={r['sum_router']} canonical={r['sum_canonical']}",
            )
            chk(
                f"member {uid[:8]}: no self-reported value reaches the board",
                r["n_leaked"] == 0,
                f"{r['n_leaked']} estimate-backed item(s) contributed a non-zero value",
            )

        chk(
            "no item anywhere breaks the market-backed-subset rule",
            total_diff == 0,
            f"{total_diff}/{total_items} item(s)",
        )
    finally:
        await conn.close()

    print(f"\nRESULT: {'PASS' if not failures else str(len(failures)) + ' FAILED'}")
    for f in failures:
        print(f"  FAILED: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
