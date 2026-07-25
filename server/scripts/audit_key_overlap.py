#!/usr/bin/env python3
"""
ADVISORY audit: text-key joins whose two sides share NO values.

Why this exists
---------------
On 2026-07-25 every query joining `items.canonical_key = price_predictions.item_ref`
was found to match zero rows -- for every user, always, since the column was
introduced. `canonical_key` holds a BARE catalog key (`sm10-sm10-101`);
`item_ref` is ALWAYS namespaced (`pokemon:sm10-sm10-101`). Measured: 0 bare
refs out of 1,696,074 rows in a 30-day window. 44 comparison sites in 13 files.

Portfolio value, category health, category stats, timeseries, deep-dives,
insights, both exports and valuation-on-add were all silently empty because of
it, for roughly four months.

**Every structural audit passed.** That is the point of this script:

  * orphan-table audit  -> "does anything write this table?"     yes, 3.1M rows
  * column-drift audit  -> "same column name on both sides?"     yes
  * endpoint E2E        -> "does the route respond?"             yes, HTTP 200
  * watchdog / PG logs  -> "what is erroring?"                   nothing

An empty join is a *valid* result. It raises nothing, logs nothing, and is
byte-identical to a user who simply owns nothing. No structural check can see
it, because the schema, the names and the SQL are all correct. Only comparing
the VALUES reveals it.

So this asks the one question none of the others do:

    do the two sides of this join actually contain any of the same strings?

Method
------
For each declared pair, sample up to --sample distinct non-null values from each
side and measure overlap. Reported as:

    DEAD     0% overlap                  -> almost certainly a format mismatch
    THIN     >0% but under --warn-pct    -> partial keyspace divergence
    OK       above the threshold

Sampling, not a full join: on partitioned multi-million-row tables an exact
overlap count is minutes of IO. A format mismatch shows up at n=200.

`expect_partial` marks pairs where incomplete overlap is a known data-coverage
fact rather than a bug -- e.g. TCG predictions are keyed by TCGplayer product id
while the catalog uses set-slugs, so those categories legitimately sit at 0%
until an id crosswalk exists. Those are reported but never counted as findings.

ADVISORY ONLY: exits 0 unless --strict. Not in the bake preflight chain --
a blocking gate here would wedge deploys on a data-coverage backlog.

Usage:
    python3 scripts/audit_key_overlap.py                # report, exit 0
    python3 scripts/audit_key_overlap.py --strict       # exit 1 on a DEAD pair
    python3 scripts/audit_key_overlap.py --json
    python3 scripts/audit_key_overlap.py --discover     # list undeclared candidates

Adding a join? Add it here. `--discover` greps the server SQL for text-column
comparisons that are not declared below and prints them.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:
    print("asyncpg not installed", file=sys.stderr)
    sys.exit(0)


# Sampling bounds. The sampled side is always the smaller table.
SMALL_TABLE_ROWS = 200_000   # below this, scan outright instead of stratifying
MAX_PREFIXES = 8             # cap the per-prefix scans on a large table

# ---------------------------------------------------------------------------
# Declared text-key joins. (left_table, left_col, right_table, right_col)
# ---------------------------------------------------------------------------
PAIRS = [
    {
        "left": ("items", "canonical_ref"),
        "right": ("price_predictions", "item_ref"),
        "note": "THE 2026-07-25 bug. Was canonical_key (bare) vs item_ref (namespaced) -> 0 overlap.",
        "expect_partial": True,  # TCG categories key by TCGplayer id, not catalog slug
    },
    {
        "left": ("items", "canonical_ref"),
        "right": ("price_prediction_daily", "item_ref"),
        "note": "Drives write_quick_valuation (value shown right after add).",
        "expect_partial": True,
    },
    {
        "left": ("items", "canonical_key"),
        "right": ("category_items", "item_key"),
        "note": "BARE on both sides by design. v_category_summaries_v1 depends on this.",
        "expect_partial": True,
    },
    {
        "left": ("watchlist_items", "item_id"),
        "right": ("category_items", "item_key"),
        "note": "Watchlist rows added from a catalog screen carry the catalog key.",
        "expect_partial": True,
    },
    {
        "left": ("market_hits", "item_ref"),
        "right": ("price_predictions", "item_ref"),
        "note": "Both namespaced; valuation reads market_hits by item_ref.",
        "expect_partial": True,
    },
    {
        "left": ("catalog_price_refs", "price_ref"),
        "right": ("price_predictions", "item_ref"),
        "note": (
            "The catalog->price crosswalk MUST point at refs that actually exist. "
            "If this goes DEAD the crosswalk is stale (predictions rolled out of the "
            "30d window or changed key format) and every yugioh item silently loses "
            "its price again. Rebuild with pipelines/build_catalog_price_crosswalk.py."
        ),
        "expect_partial": True,  # crosswalk spans all time; predictions are windowed
    },
    {
        "left": ("events", "canonical_key"),
        "right": ("event_follows_v1", "canonical_key"),
        "note": (
            "intelligence_router engagement_score joins follows on canonical_key. "
            "LATENT: events.canonical_key is NULL on all 1,981 rows (no writer) and "
            "event_follows_v1 is empty, so the follower term is structurally always 0 "
            "behind COALESCE(...,0). Harmless while both are empty; becomes a real "
            "undercount the moment follows are written. Found by --discover 2026-07-25."
        ),
        "expect_partial": True,
    },
]


def _env() -> dict:
    env = dict(os.environ)
    for candidate in ("/opt/collectors/.env", str(Path(__file__).resolve().parents[2] / ".env")):
        p = Path(candidate)
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v.strip().strip('"').strip("'"))
    return env


async def _approx_rows(conn, table: str) -> float:
    """Approximate row count, PARTITION-AWARE.

    `reltuples` on a partitioned parent is 0 — the parent holds no rows itself.
    Reading it naively made `market_hits` (~3M rows across partitions) look like
    an empty table, so it was classified small, sampled with an unordered LIMIT,
    and the audit reported a healthy join as DEAD. Sum the leaf partitions.
    """
    row = await conn.fetchrow(
        "SELECT relkind::text AS k, reltuples::float8 AS n "
        "FROM pg_class WHERE oid = ($1)::regclass", f"public.{table}"
    )
    if not row:
        return 0.0
    if row["k"] != "p":
        return float(row["n"] or 0)
    total = await conn.fetchval(
        """
        SELECT COALESCE(sum(c.reltuples), 0)::float8
        FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
        WHERE i.inhparent = ($1)::regclass
        """,
        f"public.{table}",
    )
    return float(total or 0)


async def _sample(conn, table: str, col: str, n: int) -> set[str]:
    """Distinct values, STRATIFIED by `prefix:` when the keyspace is namespaced.

    A plain `LIMIT n` with no ORDER BY returns whatever is physically first,
    which on a clustered table is one contiguous run. That produced a false DEAD
    on market_hits.item_ref -> price_predictions.item_ref: the first 1000
    distinct values were all `action_figures:*`, a category with no predictions
    at all, so the probe matched nothing while the join was in fact healthy.
    Spreading the sample across prefixes is what makes a FORMAT mismatch (the
    thing this audit exists to catch) distinguishable from a single category
    that happens to lack coverage.
    """
    # Small enough to scan outright — take everything, no stratification needed.
    # This is the common and most important case: the sampled side is always the
    # SMALLER table (see run()), and `items` is tiny.
    if await _approx_rows(conn, table) <= SMALL_TABLE_ROWS:
        rows = await conn.fetch(
            f'SELECT DISTINCT "{col}"::text AS v FROM public."{table}" '
            f'WHERE "{col}" IS NOT NULL LIMIT $1', n)
        return {r["v"] for r in rows}

    # Pick the prefixes that DOMINATE the table, not the first ones physically.
    # `SELECT DISTINCT ... LIMIT 8` returns whatever is at the head of the heap,
    # which on market_hits is `action_figures:*` — a category with no price
    # predictions — so the audit reported a healthy join as DEAD twice before
    # this ordering was added. Ordering by frequency samples the categories that
    # actually carry the data.
    prefixes = [
        r["p"] for r in await conn.fetch(
            f'SELECT split_part("{col}"::text, \':\', 1) AS p, count(*) AS n '
            f'FROM public."{table}" WHERE "{col}" IS NOT NULL '
            f'GROUP BY 1 ORDER BY n DESC LIMIT $1',
            MAX_PREFIXES,
        )
    ]
    if len(prefixes) <= 1:
        rows = await conn.fetch(
            f'SELECT DISTINCT "{col}"::text AS v FROM public."{table}" '
            f'WHERE "{col}" IS NOT NULL LIMIT $1', n)
        return {r["v"] for r in rows}

    per = max(1, n // len(prefixes))
    vals: set[str] = set()
    for p in prefixes:
        # `LIKE 'p:%'`, NOT a `>= 'p:' AND < 'p;'` range. The range trick is only
        # valid under C collation: this database uses a locale-aware collation
        # where punctuation does not order by ASCII, so `< 'p;'` excluded every
        # row and the whole audit silently reported 0/0. Correctness first —
        # this scans, which is why it only runs for genuinely large tables and
        # with a capped prefix count.
        rows = await conn.fetch(
            f'SELECT DISTINCT "{col}"::text AS v FROM public."{table}" '
            f'WHERE "{col}"::text LIKE $1 LIMIT $2', f"{p}:%", per)
        vals |= {r["v"] for r in rows}
    return vals


async def _probe(conn, table: str, col: str, values: list[str]) -> int:
    """How many of `values` actually exist in table.col — an index lookup.

    This is a SEMI-JOIN, not an intersection of two independent samples. The
    naive version (sample both sides, intersect) is worthless whenever the sides
    differ in size: 5 sampled items against 1,500 rows drawn arbitrarily from
    1.7M predictions will miss every genuine match and report a false DEAD.
    Probing the large side for the small side's values is both exact for the
    sample and cheap.
    """
    row = await conn.fetchval(
        f'SELECT count(DISTINCT "{col}"::text) FROM public."{table}" '
        f'WHERE "{col}"::text = ANY($1::text[])',
        values,
    )
    return int(row or 0)


async def run(args) -> int:
    env = _env()
    dsn = env.get("DB_DSN_DIRECT") or env.get("DB_DSN")
    if not dsn:
        print("DB_DSN_DIRECT not set — skipping (advisory)", file=sys.stderr)
        return 0

    conn = await asyncpg.connect(dsn)
    await conn.execute("SET statement_timeout = '240s'")

    findings, report = [], []
    for pair in PAIRS:
        lt, lc = pair["left"]
        rt, rc = pair["right"]
        label = f"{lt}.{lc} = {rt}.{rc}"
        try:
            # Sample the SMALLER side, probe the larger. Direction matters for
            # accuracy, not semantics — see _probe.
            if await _approx_rows(conn, lt) <= await _approx_rows(conn, rt):
                src, src_col, dst, dst_col = lt, lc, rt, rc
            else:
                src, src_col, dst, dst_col = rt, rc, lt, lc
            sampled = await _sample(conn, src, src_col, args.sample)
            hits = await _probe(conn, dst, dst_col, list(sampled)) if sampled else 0
        except Exception as exc:  # missing table/column is itself worth reporting
            report.append({"pair": label, "status": "ERROR", "detail": str(exc)[:160]})
            continue

        if not sampled:
            status, pct = "EMPTY", None
        else:
            pct = 100.0 * hits / len(sampled)
            status = "DEAD" if hits == 0 else ("THIN" if pct < args.warn_pct else "OK")

        entry = {
            "pair": label, "status": status, "overlap_pct": pct,
            "direction": f"{src}.{src_col} -> {dst}.{dst_col}",
            "sampled": len(sampled), "matched": hits,
            "expect_partial": pair.get("expect_partial", False),
            "note": pair["note"],
        }
        report.append(entry)
        if status == "DEAD" and not pair.get("expect_partial"):
            findings.append(entry)

    await conn.close()

    if args.json:
        print(json.dumps({"report": report, "findings": findings}, indent=1))
    else:
        print("=" * 76)
        print(f"  Key-overlap audit — {len(PAIRS)} declared joins, sample={args.sample}")
        print("=" * 76)
        for e in report:
            if e["status"] == "ERROR":
                print(f"  ERROR  {e['pair']}\n         {e['detail']}")
                continue
            pct = "  n/a " if e["overlap_pct"] is None else f"{e['overlap_pct']:5.1f}%"
            tag = " (partial expected)" if e["expect_partial"] else ""
            print(f"  {e['status']:5s} {pct}  {e['pair']}{tag}")
            print(f"         {e['matched']}/{e['sampled']} matched via {e['direction']}")
            print(f"         {e['note']}")
        print("-" * 76)
        if findings:
            print(f"  {len(findings)} DEAD join(s) with no expected-partial exemption.")
            print("  A DEAD join returns [] forever and raises nothing. Check the key FORMATS.")
        else:
            print("  No unexplained dead joins.")
        print("=" * 76)

    if args.strict and findings:
        return 1
    return 0


def discover() -> int:
    """Print text-column comparisons in server SQL that are not declared above."""
    root = Path(__file__).resolve().parents[1]
    declared = {
        f"{p['left'][1]}={p['right'][1]}" for p in PAIRS
    } | {
        f"{p['right'][1]}={p['left'][1]}" for p in PAIRS
    }
    rx = re.compile(r"\b(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)\b")
    seen: set[str] = set()
    for path in list(root.rglob("*.py")):
        if "/tests/" in str(path) or "/scripts/" in str(path):
            continue
        try:
            text = path.read_text()
        except Exception:
            continue
        for m in rx.finditer(text):
            _, lcol, _, rcol = m.groups()
            if lcol == rcol:
                continue  # same column name on both sides — the drift audit covers that
            key = f"{lcol}={rcol}"
            if key in declared or key in seen:
                continue
            # Only key-ish columns are interesting
            if not any(t in lcol or t in rcol for t in ("key", "ref", "_id", "code", "slug")):
                continue
            seen.add(key)
            print(f"  {lcol:26s} = {rcol:26s}  {path.relative_to(root)}")
    if not seen:
        print("  no undeclared key comparisons found")
    print("\n  Declared pairs live in PAIRS at the top of this file.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=2000, help="distinct values per side")
    ap.add_argument("--warn-pct", type=float, default=1.0, help="below this = THIN")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--discover", action="store_true")
    args = ap.parse_args()
    if args.discover:
        return discover()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
