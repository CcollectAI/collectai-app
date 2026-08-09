#!/usr/bin/env python3
"""
Build `catalog_price_refs` — the catalog -> price-pipeline identifier crosswalk.

Why this exists
---------------
The catalog and the valuation pipeline key the same card in different
namespaces, and for most TCG categories they do not overlap at all:

  category            catalog item_key              prediction item_ref
  ------------------  ---------------------------   ---------------------------------
  pokemon / mtg       base1-base1-1                 pokemon:base1-base1-1        SAME
  yugioh              sbc1-en122-magical-arm-shield yugioh:10000-ten-thousand-dragon
                      = {set}-{number}-{name}       = {passcode}-{name}
  lorcana/digimon/    azu-abu-tricky-monkey         lorcana:tcgplayer:702699:normal
  one_piece_tcg       = {set}-{...}-{name}          = tcgplayer product id

pokemon and mtg already line up (97%/99% priced). yugioh was at 0.6% and the
three TCGplayer-keyed games at ~0%, purely because nothing translated between
the namespaces. Measured 2026-07-25.

Matchers (deterministic only — no fuzzy scoring)
------------------------------------------------
`name_slug` (yugioh): both sides end in the same card-name slug. The catalog
title slugified equals the prediction ref's trailing name slug. 36,457 / 38,312
= 95.2% match with only 8 names ambiguous across passcodes.

  *** ACCURACY LIMIT — read before trusting these numbers ***
  yugioh predictions are keyed by PASSCODE, i.e. per CARD, while the catalog is
  keyed per PRINTING. Every printing of a card therefore resolves to the same
  price: a scarce 1st-edition SBC1 printing and a common TP8 reprint will show
  an IDENTICAL value. That is wrong for collectors at the high end. It is
  shipped as a first pass because a price beats no price, and it is recorded
  with method='name_slug' + confidence so it can be excluded or refined later.
  Do NOT present these as printing-exact valuations.

Ambiguity is never guessed: if a catalog row's name slug maps to more than one
passcode, it is skipped and counted, not resolved arbitrarily. Guessing here is
how the PriceCharting incident poisoned prices (see the console-guard learning).

Usage:
    python3 pipelines/build_catalog_price_crosswalk.py --dry-run
    python3 pipelines/build_catalog_price_crosswalk.py --apply
    python3 pipelines/build_catalog_price_crosswalk.py --apply --category yugioh
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import logging
import os
import re
import sys
from pathlib import Path

import asyncpg

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [crosswalk] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
NAME_SLUG_CONFIDENCE = 0.75  # per-card, not per-printing — deliberately not 1.0


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


def slugify(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# Matcher: yugioh — catalog set-printing -> passcode-keyed prediction
# ---------------------------------------------------------------------------

_PASSCODE_REF = re.compile(r"^(\d+)-(.+)$")


async def match_name_slug(conn, category: str) -> tuple[list[tuple], dict]:
    """Match on the trailing card-name slug shared by both namespaces."""
    preds = await conn.fetch(
        """
        SELECT DISTINCT item_ref FROM public.price_predictions
        WHERE item_ref LIKE $1
          AND item_ref NOT LIKE $2
          AND generated_at >= now() - ($3 || ' days')::interval
        """,
        f"{category}:%", f"{category}:tcgplayer:%", str(WINDOW_DAYS),
    )

    by_slug: dict[str, set[str]] = collections.defaultdict(set)
    for r in preds:
        tail = r["item_ref"].split(":", 1)[1]
        m = _PASSCODE_REF.match(tail)
        if m:
            by_slug[m.group(2)].add(r["item_ref"])

    rows = await conn.fetch(
        "SELECT item_key, title FROM public.category_items WHERE category = $1", category
    )

    out: list[tuple] = []
    stats = {"catalog": len(rows), "pred_slugs": len(by_slug),
             "matched": 0, "ambiguous": 0, "unmatched": 0}
    for r in rows:
        refs = by_slug.get(slugify(r["title"]))
        if not refs:
            stats["unmatched"] += 1
            continue
        if len(refs) > 1:
            # More than one passcode shares this card name — do not guess.
            stats["ambiguous"] += 1
            continue
        stats["matched"] += 1
        out.append((category, r["item_key"], next(iter(refs)),
                    "name_slug", NAME_SLUG_CONFIDENCE))
    return out, stats


MATCHERS = {
    "yugioh": match_name_slug,
}


async def run(args) -> int:
    env = _env()
    dsn = env.get("DB_DSN_DIRECT") or env.get("DB_DSN")
    if not dsn:
        logger.error("DB_DSN_DIRECT not set")
        return 2

    conn = await asyncpg.connect(dsn)
    await conn.execute("SET statement_timeout = 0")

    categories = [args.category] if args.category else list(MATCHERS)
    total_written = 0
    for cat in categories:
        matcher = MATCHERS.get(cat)
        if not matcher:
            logger.warning("no matcher registered for %s — skipping", cat)
            continue
        pairs, stats = await matcher(conn, cat)
        pct = 100 * stats["matched"] / stats["catalog"] if stats["catalog"] else 0
        logger.info(
            "%s: catalog=%d pred_name_slugs=%d matched=%d (%.1f%%) ambiguous=%d unmatched=%d",
            cat, stats["catalog"], stats["pred_slugs"], stats["matched"], pct,
            stats["ambiguous"], stats["unmatched"],
        )
        if not args.apply:
            for p in pairs[:5]:
                logger.info("   sample %s -> %s", p[1], p[2])
            continue

        # Upsert in batches; last write wins on (category, item_key).
        B = 1000
        for i in range(0, len(pairs), B):
            chunk = pairs[i:i + B]
            await conn.executemany(
                """
                INSERT INTO public.catalog_price_refs
                    (category, item_key, price_ref, method, confidence, updated_at)
                VALUES ($1,$2,$3,$4,$5, now())
                ON CONFLICT (category, item_key) DO UPDATE
                SET price_ref = EXCLUDED.price_ref,
                    method     = EXCLUDED.method,
                    confidence = EXCLUDED.confidence,
                    updated_at = now()
                """,
                chunk,
            )
        total_written += len(pairs)
        logger.info("%s: wrote %d crosswalk rows", cat, len(pairs))

    if args.apply:
        n = await conn.fetchval("SELECT count(*) FROM public.catalog_price_refs")
        logger.info("catalog_price_refs total rows: %d (wrote %d this run)", n, total_written)

        # items.canonical_ref is resolved by trg_items_canonical_ref, which fires
        # on items writes ONLY. Rewriting the crosswalk here does not refire it,
        # so already-stored items would keep a stale ref until someone edited
        # them — the exact silent-drift shape this codebase keeps getting bitten
        # by. Re-touch them so the resolver runs again. Cheap: items is small and
        # this is a no-op UPDATE that only re-runs the BEFORE trigger.
        touched = await conn.execute(
            "UPDATE public.items SET canonical_key = canonical_key WHERE canonical_key IS NOT NULL"
        )
        logger.info("re-resolved items.canonical_ref (%s)", touched)

    await conn.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write rows (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="explicit no-op default")
    ap.add_argument("--category", help="limit to one category")
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
