#!/usr/bin/env python3
"""
Scrape probe — sample each category to measure per-category hit rate.

Runs the same MarketplaceAgent the bake uses. For each category, picks
N random items and attempts `find_sold_comps`. Reports per-category:
  - items_attempted
  - items_with_hits
  - hit_rate_pct

Purpose: predict bootstrap coverage before waiting 30 days. Categories
with <40% hit rate need new adapters / sources.

Usage:
  cd server && python scripts/scrape_probe.py
  cd server && python scripts/scrape_probe.py --per-category 10 --out probe.json

Writes does NOT persist to market_hits — this is a read-only probe.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import asyncpg

PAID_ADAPTERS = ["firecrawl", "scrapedo", "serpapi"]


async def sample_items(conn, per_category: int) -> dict[str, list]:
    """Pick random items per category, weighted toward ones with some seed."""
    rows = await conn.fetch(
        """
        SELECT category, item_key, title FROM (
          SELECT ci.category, ci.item_key, ci.title,
                 row_number() OVER (
                   PARTITION BY ci.category ORDER BY RANDOM()
                 ) AS rn
          FROM category_items ci
          WHERE ci.title IS NOT NULL
        ) t
        WHERE rn <= $1
        ORDER BY category, rn
        """,
        per_category,
    )
    by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append({
            "item_key": r["item_key"],
            "title": r["title"],
        })
    return dict(by_cat)


async def probe_category(agent, category: str, items: list) -> dict:
    """Run find_sold_comps on each item, count hits per item."""
    items_with_hits = 0
    total_hits = 0
    per_item = []
    for it in items:
        t0 = time.monotonic()
        try:
            result = await agent.find_sold_comps(
                query=it["title"], category=category, limit=5,
            )
            hits = getattr(result, "hits", None) or []
            n = len(hits)
            if n > 0:
                items_with_hits += 1
                total_hits += n
            per_item.append({
                "title": it["title"][:60],
                "hits": n,
                "duration_s": round(time.monotonic() - t0, 2),
            })
        except Exception as e:
            per_item.append({
                "title": it["title"][:60],
                "hits": 0,
                "error": f"{type(e).__name__}: {e}"[:200],
                "duration_s": round(time.monotonic() - t0, 2),
            })
        await asyncio.sleep(1)  # small courtesy delay
    return {
        "category": category,
        "items_attempted": len(items),
        "items_with_hits": items_with_hits,
        "total_hits": total_hits,
        "hit_rate_pct": round(100 * items_with_hits / len(items), 1) if items else 0.0,
        "per_item": per_item,
    }


async def main_async(per_category: int, out_file: str | None) -> int:
    dsn = os.environ.get("DB_DSN", "")
    if not dsn:
        print("ERROR: DB_DSN not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        by_cat = await sample_items(conn, per_category)
    finally:
        await conn.close()

    total_items = sum(len(v) for v in by_cat.values())
    print(f"Probing {len(by_cat)} categories × up to {per_category} items "
          f"= {total_items} items total…\n")

    # Lazy import to avoid heavy startup when DB probe fails
    from app.agents.marketplace_agent import MarketplaceAgent
    agent = MarketplaceAgent()

    # Disable paid adapters — mirror the bake scraper
    for adapter_name in PAID_ADAPTERS:
        attr = f"_{adapter_name}_caller"
        if hasattr(agent, attr):
            setattr(agent, attr, None)

    results = []
    t_global = time.monotonic()
    for i, (cat, items) in enumerate(sorted(by_cat.items()), 1):
        t0 = time.monotonic()
        r = await probe_category(agent, cat, items)
        elapsed = time.monotonic() - t0
        print(f"[{i:2d}/{len(by_cat)}] {cat:<22} "
              f"{r['items_with_hits']}/{r['items_attempted']} with hits "
              f"({r['hit_rate_pct']:>5.1f}%)  {elapsed:.0f}s")
        results.append(r)

    try:
        await agent.close()
    except Exception:
        pass

    total_elapsed = time.monotonic() - t_global

    # Summary
    print("\n" + "=" * 72)
    print(f"  Scrape probe — {total_items} items across {len(results)} categories")
    print(f"  Elapsed: {total_elapsed / 60:.1f} min")
    print("=" * 72)
    results.sort(key=lambda r: r["hit_rate_pct"])
    for r in results:
        bar = "█" * int(r["hit_rate_pct"] / 5)
        print(f"  {r['hit_rate_pct']:>5.1f}%  {r['category']:<22}  "
              f"{r['items_with_hits']:>3}/{r['items_attempted']:<3}  "
              f"{bar}")
    print("=" * 72)

    summary = {
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "per_category": per_category,
        "total_items": total_items,
        "elapsed_s": round(total_elapsed, 1),
        "results": results,
    }
    if out_file:
        with open(out_file, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nWrote {out_file}")

    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Per-category scrape probe")
    p.add_argument("--per-category", type=int, default=15,
                   help="items per category (default 15)")
    p.add_argument("--out", type=str, default="/tmp/scrape_probe.json")
    args = p.parse_args()
    return asyncio.run(main_async(args.per_category, args.out))


if __name__ == "__main__":
    sys.exit(main())
