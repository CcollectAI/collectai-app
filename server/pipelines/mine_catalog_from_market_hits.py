#!/usr/bin/env python3
"""Mine catalogue rows out of the marketplace hits we already ingest.

WHY THIS EXISTS
---------------
The watches catalogue was grown by hand — a curated Python list in
`import_watches.py`. That caps out at a few dozen references per sitting while
the real market has thousands, and 2,631 distinct real listing titles for
`watches` were already sitting unused in `market_hits`.

`project_2026_07_25_catalog_price_crosswalk` states the rule this follows:

    "when two namespaces don't overlap, check whether one of them can simply be
     GENERATED from the other's source before writing a matcher. Fuzzy matching
     is the fallback, not the first move."

So this generates catalogue rows from the source that already produces the
market data, rather than trying to match two vocabularies after the fact.

WHAT IT DOES NOT DO — READ BEFORE PROMISING ANYTHING
----------------------------------------------------
**Mined rows are NOT priceable.** eBay is ~100% active listings and 0 sold
comps (`ebay_caller.py` sold_comps() is stubbed pending Marketplace Insights
access), and `valuation_worker` excludes `is_listing IS TRUE`. Rows mined from
those hits land in exactly the same unpriced state as the hand-seeded ones.
This widens the catalogue; it does not close the 62,000-row pricing gap, which
is one stubbed function and an API approval.

PRECISION IS THE WHOLE PROBLEM
------------------------------
A marketplace title is not a catalogue entry. A naive "first alphanumeric token
with digits" rule scored ~80%: it read `40MM-`, `660FT` and `36MM-` — a case
size, a depth rating and another case size — as reference numbers. Tightened to
~90%, it still produced `47.3` (a case dimension) and `1-21` (an STP movement
code).

90% sounds fine until you multiply: ~96 wrong rows out of 964, indistinguishable
from real ones once inserted. docs/TAXONOMY.md records the same trap — a bare
`Binder` filter matched 36 rows of which 34 were real cards — and the discipline
that caught it: read EVERY match per category, never trust the total.

Hence two confidence tiers:
  * `high`   — the token matches that BRAND's known reference grammar
               (Hamilton H+8 digits, Longines L+9, Omega five dotted groups,
               Seiko 3-4 letters + 3-4 digits, Patek 4-5 digits + suffix, ...).
               Only these are promoted by default.
  * `medium` — a generic reference-shaped token. Written to the report for
               review and NOT promoted unless --include-medium is passed.

USAGE
-----
    python -m pipelines.mine_catalog_from_market_hits --category watches
    python -m pipelines.mine_catalog_from_market_hits --category watches --promote
    python -m pipelines.mine_catalog_from_market_hits --category watches --promote --include-medium
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402

from pipelines.import_common import CatalogItem, slugify, logger  # noqa: E402

# ---------------------------------------------------------------------------
# Per-brand reference grammars — the difference between 90% and ~99%
# ---------------------------------------------------------------------------
# Each pattern must match the WHOLE token. Anchored deliberately: a substring
# match would accept "40MM" inside a longer string and put a case size in the
# catalogue.
BRAND_REF_PATTERNS: dict[str, re.Pattern] = {
    "Hamilton": re.compile(r"^H\d{6,9}$", re.I),
    "Longines": re.compile(r"^L\d[\d.]{6,14}$", re.I),
    "Tissot": re.compile(r"^T\d{3}[\d.]{6,16}$", re.I),
    "Omega": re.compile(r"^\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3}$"),
    "Seiko": re.compile(r"^S[A-Z]{2,3}\d{3,4}[A-Z]?\d?$", re.I),
    "Grand Seiko": re.compile(r"^S[A-Z]{2,4}\d{3,4}[A-Z]?$", re.I),
    "Citizen": re.compile(r"^[A-Z]{2}\d{4}-\d{2}[A-Z]$", re.I),
    "Tudor": re.compile(r"^M?\d{5}[A-Z]?(-\d{4})?$", re.I),
    "Rolex": re.compile(r"^\d{5,6}[A-Z]{0,3}$"),
    "Panerai": re.compile(r"^PAM\d{5}$", re.I),
    "Patek Philippe": re.compile(r"^\d{4,5}[A-Z]?(/\d{1,4}[A-Z]?)?(-\d{3})?$", re.I),
    "Vacheron Constantin": re.compile(r"^\d{4,5}[A-Z]?/[\dA-Z\-]{3,12}$", re.I),
    "Jaeger-LeCoultre": re.compile(r"^Q?\d{6,7}$", re.I),
    "Cartier": re.compile(r"^W[A-Z0-9]{6,9}$", re.I),
    "IWC": re.compile(r"^IW\d{6}$", re.I),
    "Breitling": re.compile(r"^[A-Z]{1,2}\d{5}[A-Z0-9/]{0,8}$", re.I),
    "TAG Heuer": re.compile(r"^[A-Z]{3}\d{3,4}[A-Z]?(\.[A-Z]{2}\d{4})?$", re.I),
    "Zenith": re.compile(r"^\d{2}\.[A-Z0-9]{4,6}\.[\d.]{3,12}$", re.I),
    "Oris": re.compile(r"^01\s?\d{3}\s?\d{4}\s?\d{4}", re.I),
    "Nomos": re.compile(r"^\d{3,4}$"),
    "Junghans": re.compile(r"^0?\d{2}/\d{4}(\.\d{2})?$"),
    "Casio": re.compile(r"^[A-Z]{1,3}-?\d{3,5}[A-Z0-9\-]{0,8}$", re.I),
    "G-Shock": re.compile(r"^[A-Z]{2,3}-?\d{4}[A-Z0-9\-]{0,8}$", re.I),
    "Timex": re.compile(r"^TW\d[A-Z0-9]{6,9}$", re.I),
    "Sinn": re.compile(r"^\d{3}\.?\d{0,4}$"),
    "A. Lange & Sohne": re.compile(r"^\d{3}\.\d{3}$"),
    "Montblanc": re.compile(r"^\d{6}$"),
    "Bell & Ross": re.compile(r"^BR[A-Z0-9\-]{4,12}$", re.I),
    "Hublot": re.compile(r"^\d{3}\.[A-Z]{2}\.[\dA-Z.]{4,14}$", re.I),
    "Vostok": re.compile(r"^\d{6}$"),
    "Zodiac": re.compile(r"^ZO\d{4}$", re.I),
    # Added 2026-08-13 after reading the medium-confidence tier per brand. These
    # were all producing correct references that only missed 'high' because no
    # grammar existed for the house — not because the extraction was wrong.
    # Widening the grammar is the precise fix; blanket-promoting 'medium' would
    # have taken the junk with it (Doxa "200T" is a model family, Seiko
    # "SART013/SPB537" is two references joined by a slash).
    "Orient Star": re.compile(r"^R[EK]-?[A-Z]{2}\d{4}[A-Z]$", re.I),
    "Orient": re.compile(r"^R[AENK]-?[A-Z]{2}\d{4}[A-Z]$", re.I),
    "Bulova": re.compile(r"^(\d{2}[A-Z]\d{3}|C\d{6})$", re.I),
    "Certina": re.compile(r"^C\d{3}[\d.]{8,14}$", re.I),
    "Doxa": re.compile(r"^\d{3}\.\d{2}\.\d{3}\.\d{2}$"),
    "Steinhart": re.compile(r"^10\d-\d{4}$"),
    "Mido": re.compile(r"^M\d{3}[\d.]{6,14}$", re.I),
    "Rado": re.compile(r"^R\d{8}$", re.I),
    "Frederique Constant": re.compile(r"^FC-\d{3}[A-Z0-9]{2,8}$", re.I),
    "Alpina": re.compile(r"^AL-\d{3}[A-Z0-9]{2,8}$", re.I),
}

# Widenings of grammars that were too tight on the first pass. Kept separate so
# the diff shows WHY each changed.
BRAND_REF_PATTERNS.update({
    # OCW-T2600, GMW-B5000EH-1JR, ECB-2200 — the original ^[A-Z]{1,3}-?\d{3,5}
    # could not see a letter inside the numeric block.
    "Casio": re.compile(r"^[A-Z]{2,4}-?[A-Z]?\d{3,5}[A-Z0-9\-]{0,10}$", re.I),
    "G-Shock": re.compile(r"^[A-Z]{2,4}-?[A-Z]?\d{3,5}[A-Z0-9\-]{0,10}$", re.I),
    # SRPF79K1 / SRPE33K1: 4 letters then only TWO digits then a K1 suffix.
    "Seiko": re.compile(r"^S[A-Z]{2,3}\d{2,4}[A-Z]?\d?$", re.I),
    "Grand Seiko": re.compile(r"^S[A-Z]{2,4}\d{2,4}[A-Z]?\d?$", re.I),
    # 174.8.90.S and 344.2.37.S alongside the Q-prefixed form.
    "Jaeger-LeCoultre": re.compile(r"^(Q?\d{6,7}|\d{3}\.\d\.\d{2}\.[A-Z]|Q\d{3}[A-Z]\d{3})$", re.I),
})

# Generic fallback: reference-SHAPED, but unverified against a brand grammar.
GENERIC_REF = re.compile(r"^[A-Z0-9][A-Z0-9./\-]{3,24}$", re.I)

# Tokens that look like references and are not. Every one of these was observed
# in the real data during the 2026-08-12 precision pass.
NOT_A_REF = re.compile(
    r"(?:MM|FT|ATM|BAR|CM|G|KG)[-.]?$"       # 40MM-, 660FT, 10ATM
    r"|^\d{2,4}M[-.]?$"                       # 200M, 150M — WATER RESISTANCE.
                                              # Claimed by 9 brands at once in the
                                              # real data, which is what exposed it:
                                              # a token 9 maisons "share" is not a
                                              # reference. Anchored so Tudor's
                                              # M-PREFIXED refs (M28500) survive.
    r"|^(?:19|20)\d0S[-.]?$"                  # 1960S — a decade, not a model
    r"|^(?:19|20)\d\d[-.]?$"                  # a year
    r"|^\d{1,3}[-.]?$"                        # 300, 42
    r"|^[A-Z]{1,2}[-.]?$",                    # stray initials
    re.I,
)


def norm_ref(ref: str) -> str:
    """Punctuation-insensitive reference identity.

    `DW-5600`, `DW5600` and `DW 5600` are one watch written three ways; a
    listing title picks whichever the seller felt like. Comparing raw strings
    puts all three in the catalogue as separate products.
    """
    return re.sub(r"[^A-Z0-9]", "", (ref or "").upper())


def extract(title: str, brand: str) -> tuple[str | None, str]:
    """Return (reference, confidence) for one listing title.

    confidence: 'high' when the token matches the brand's own grammar,
    'medium' when it is merely reference-shaped, '' when nothing qualifies.
    """
    rest = title[len(brand):] if title.lower().startswith(brand.lower()) else title
    tokens = [t.strip(",.;:()[]") for t in rest.split()]
    pattern = BRAND_REF_PATTERNS.get(brand)

    if pattern:
        for t in tokens:
            # A reference always carries digits. Without this, the Cartier
            # grammar ^W[A-Z0-9]{6,9}$ matches the literal word "WATCHES" —
            # observed in "CARTIER Pasha C Meridian GMT Watches W31078M7", where
            # it beat the real reference to the first position. Found by reading
            # the per-brand sample, not the total (docs/TAXONOMY.md).
            if sum(ch.isdigit() for ch in t) < 2:
                continue
            if pattern.match(t):
                return t.upper(), "high"

    for t in tokens:
        if not GENERIC_REF.match(t):
            continue
        if NOT_A_REF.search(t):
            continue
        if sum(ch.isdigit() for ch in t) < 3:
            continue
        stripped = t.strip("-.")
        if stripped.isdigit() and len(stripped) < 5:
            continue
        return stripped.upper(), "medium"

    return None, ""


async def mine(category: str, promote: bool, include_medium: bool, limit: int | None) -> int:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        logger.error("DB_DSN_DIRECT/DB_DSN not set")
        return 1
    conn = await asyncpg.connect(dsn, timeout=60)
    try:
        brands = sorted(
            (r["brand"] for r in await conn.fetch(
                "SELECT DISTINCT brand FROM category_items WHERE category=$1 AND brand IS NOT NULL",
                category)),
            key=len, reverse=True)
        titles = [r["title"] for r in await conn.fetch(
            "SELECT DISTINCT title FROM market_hits WHERE category=$1 AND title IS NOT NULL",
            category)]
        # Existing references, NORMALISED. Two ways they appear:
        #   * hand-curated rows put the reference in trailing parens
        #     "A. Lange & Sohne 1815 Chronograph (414.031)"
        #   * rows this miner already wrote are "Brand REF" with no parens, so
        #     a paren-only check would not see them and the next run would try
        #     to add them again.
        # Normalisation strips punctuation so DW-5600, DW5600 and DW 5600
        # collapse to one — they are the same watch listed three ways.
        existing_refs: set[str] = set()
        existing_keys: set[str] = set()
        for r in await conn.fetch(
                "SELECT item_key, title, brand FROM category_items WHERE category=$1", category):
            existing_keys.add(r["item_key"])
            title = r["title"] or ""
            m = re.search(r"\(([^)]+)\)\s*$", title)
            if m:
                existing_refs.add(norm_ref(m.group(1)))
            brand = r["brand"] or ""
            if brand and title.lower().startswith(brand.lower()):
                tail = title[len(brand):].strip()
                # A mined row's whole tail IS the reference.
                if tail and " " not in tail:
                    existing_refs.add(norm_ref(tail))
    finally:
        await conn.close()

    # Keyed on the NORMALISED reference so DW-5600 and DW5600 cannot both land.
    found: dict[tuple[str, str], tuple[str, str, str]] = {}
    cross_brand: dict[str, set[str]] = defaultdict(set)
    for title in titles:
        t = (title or "").strip()
        brand = next((b for b in brands if t.lower().startswith(b.lower())), None)
        if not brand:
            continue
        ref, conf = extract(t, brand)
        if not ref:
            continue
        nref = norm_ref(ref)
        if nref in existing_refs:
            continue
        cross_brand[nref].add(brand)
        found.setdefault((brand, nref), (ref, t, conf))

    # One reference claimed by two brands is a mis-attribution, not two
    # products — "Casio DW-5600" and "G-Shock DW5600" are the same watch. Drop
    # both rather than guess which brand string is right.
    # A mined reference that is a SUBSTRING of one already in the catalogue is a
    # partial extraction, not a new product: "Casio GA-110" against three
    # catalogued GA-110 collabs, "Breitling A13317" against A13317101B1A1,
    # "Bell & Ross BR03-92" against three specific BR0392-* refs. 32 of the
    # first 592 promoted were this shape. They pass the exact-match and
    # cross-brand checks because the STRINGS genuinely differ — only the
    # containment test sees them.
    partial = {n for n in list(found and {k[1] for k in found})
               if any(n != e and n in e for e in existing_refs)}
    if partial:
        print(f"\n  ! {len(partial)} reference(s) are partials of an existing row — skipped:")
        for n in list(partial)[:6]:
            print(f"      {n}")
        found = {k: v for k, v in found.items() if k[1] not in partial}

    contested = {n for n, bs in cross_brand.items() if len(bs) > 1}
    if contested:
        print(f"\n  ! {len(contested)} reference(s) claimed by >1 brand — skipped as ambiguous:")
        for n in list(contested)[:6]:
            print(f"      {n:<18} claimed by {sorted(cross_brand[n])}")
        found = {k: v for k, v in found.items() if k[1] not in contested}

    by_conf: dict[str, list] = defaultdict(list)
    for (brand, nref), (ref, title, conf) in found.items():
        by_conf[conf].append((brand, ref, title))

    print(f"\n=== mined {category} ===")
    print(f"  distinct market_hits titles : {len(titles)}")
    print(f"  new (brand, reference)      : {len(found)}")
    print(f"    high confidence           : {len(by_conf['high'])}")
    print(f"    medium (review needed)    : {len(by_conf['medium'])}")

    print("\n  per brand (high confidence):")
    per_brand: dict[str, int] = defaultdict(int)
    for b, _, _ in by_conf["high"]:
        per_brand[b] += 1
    for b, n in sorted(per_brand.items(), key=lambda kv: -kv[1])[:20]:
        print(f"    {b:<24} {n}")

    tiers = ["high"] + (["medium"] if include_medium else [])
    selected = [x for tier in tiers for x in by_conf[tier]]
    if limit:
        selected = selected[:limit]

    print(f"\n  sample of what would be written ({min(10, len(selected))} of {len(selected)}):")
    for brand, ref, title in selected[:10]:
        print(f"    {brand:<20} {ref:<20} <- {title[:48]}")

    if not promote:
        print("\n  DRY RUN — pass --promote to write. Review the per-brand counts first.")
        return 0

    items: list[CatalogItem] = []
    for brand, ref, title in selected:
        key = slugify(f"{brand}-{ref}")
        if key in existing_keys:
            continue
        existing_keys.add(key)
        items.append(CatalogItem(
            category=category,
            item_key=key,
            # The listing title is the marketing copy of ONE seller, so it is
            # not used verbatim. Brand + reference is the catalogue identity.
            title=f"{brand} {ref}",
            brand=brand,
            notes="",
            attributes_json={"mined_from": "market_hits", "mined_batch": "2026_08_12",
                             "source_title": title[:200]},
        ))

    from pipelines.import_common import SupabaseIngest  # local: needs env
    ingest = SupabaseIngest()
    written = ingest.upsert_catalog(items)
    print(f"\n  promoted {written} row(s) into category_items")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--category", required=True)
    ap.add_argument("--promote", action="store_true", help="write to category_items")
    ap.add_argument("--include-medium", action="store_true",
                    help="also promote medium-confidence refs (review them first)")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    return asyncio.run(mine(a.category, a.promote, a.include_medium, a.limit))


if __name__ == "__main__":
    sys.exit(main())
