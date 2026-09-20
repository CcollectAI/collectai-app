#!/usr/bin/env python3
"""Is a member's reported sale price anchored on the price WE showed them?

WHY: `verified_sales` feeds model retraining, and the number comes from a
member who saw Sparrow's estimate before listing. If they list at our estimate
and sell near it, that price is partly our own model's output coming back as
"ground truth" — the model then confirms itself. `price_feedback.sold_becomes_comp`
("Sold it? Your price becomes the comp") makes the loop explicit, and for many
items a member sale is the only sale price that exists at all.

Nothing had to be built to measure this. `price_ground_truths` already stores
`prediction_q50` (what the model said at the time) and `error_pct`
(actual vs prediction) on every row. Nobody was reading them.

THE CONTROL IS THE POINT. A tight error distribution on member-reported sales
proves nothing on its own — it could just mean the model is good. What matters
is the GAP against sources the member could not anchor to:

    user_verified_sale   a member types the number      <- can anchor
    sparrow_p2p          a completed P2P trade          <- control
    deal_desk            a completed Deal Desk offer    <- control

If member sales cluster inside ±5% of our own prediction far more often than
the independent sources do, that is anchoring, not accuracy.

    DB_DSN_DIRECT=... python3 server/scripts/check_price_anchoring.py
    ... --strict          exit 1 if the anchoring gap exceeds --max-gap

Advisory by default: this is a measurement, and the honest first answer may be
"not enough rows yet to say".
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

ANCHOR_BAND = 0.05          # |error_pct| <= 5% counts as "sold at our number"
MIN_ROWS = 20               # below this, report but never fail
ANCHORED = "user_verified_sale"


async def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when the anchoring gap exceeds --max-gap")
    ap.add_argument("--max-gap", type=float, default=0.25,
                    help="allowed gap in in-band rate vs independent sources")
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args()

    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("check_price_anchoring: no DSN — skipping (advisory).")
        return 0
    try:
        import asyncpg
    except ImportError:
        print("check_price_anchoring: asyncpg not installed — skipping (advisory).")
        return 0

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT source,
                   count(*)                                        AS n,
                   count(*) FILTER (WHERE error_pct IS NOT NULL)   AS n_scored,
                   avg(abs(error_pct))                             AS mean_abs,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(error_pct)) AS median_abs,
                   count(*) FILTER (WHERE abs(error_pct) <= $1)    AS n_in_band
            FROM public.price_ground_truths
            WHERE recorded_at >= now() - ($2 || ' days')::interval
              AND prediction_q50 IS NOT NULL
              AND prediction_q50 > 0
            GROUP BY source
            ORDER BY source
            """,
            ANCHOR_BAND, str(args.days),
        )
    finally:
        await conn.close()

    if not rows:
        print("check_price_anchoring: no scored ground truths yet — nothing to measure.")
        return 0

    print(f"price ground truths scored against our own q50, last {args.days} days")
    print(f"  in-band = the member's price landed within +/-{ANCHOR_BAND:.0%} of what we predicted\n")
    print(f"  {'source':<22}{'n':>6}{'median |err|':>14}{'in-band':>10}")
    print("  " + "-" * 52)

    anchored = None
    control_scored = control_in_band = 0
    for r in rows:
        n = r["n_scored"] or 0
        rate = (r["n_in_band"] / n) if n else 0.0
        med = float(r["median_abs"]) if r["median_abs"] is not None else float("nan")
        print(f"  {r['source']:<22}{n:>6}{med:>13.1%}{rate:>10.1%}")
        if r["source"] == ANCHORED:
            anchored = (n, rate)
        else:
            control_scored += n
            control_in_band += r["n_in_band"] or 0

    if anchored is None:
        print("\n  No member-reported sales scored yet — the anchored stream is empty.")
        return 0
    n_anchored, anchored_rate = anchored
    if control_scored == 0:
        print("\n  No independent ground truths to compare against. A rate on its own\n"
              "  is not evidence: without a control it cannot separate anchoring from\n"
              "  an accurate model.")
        return 0

    control_rate = control_in_band / control_scored
    gap = anchored_rate - control_rate
    print(f"\n  member-reported in-band : {anchored_rate:.1%}  (n={n_anchored})")
    print(f"  independent  in-band    : {control_rate:.1%}  (n={control_scored})")
    print(f"  gap                     : {gap:+.1%}")

    if n_anchored < MIN_ROWS or control_scored < MIN_ROWS:
        print(f"\n  Too few rows to conclude (need {MIN_ROWS} on each side). Reported, not judged.")
        return 0
    if gap > args.max_gap:
        print(f"\n  ANCHORING: member-reported sales land on our own number {gap:.1%} more\n"
              f"  often than independent trades do. Those prices are partly the model's\n"
              f"  own output returning as training data.")
        return 1 if args.strict else 0
    print("\n  No anchoring signal: member-reported sales are no closer to our\n"
          "  prediction than independent trades are.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
