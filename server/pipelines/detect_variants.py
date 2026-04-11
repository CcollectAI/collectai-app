#!/usr/bin/env python3
"""
Detect variant clusters in catalog items.

Items like "Charizard Holo", "Charizard - Holographic", and "Charizard (Holo)"
should be grouped as variants of the same canonical item. This script walks
the catalog and clusters items by normalized title similarity.

Output: server/data/_vocab/variant_clusters.json
    {
      "pokemon": [
        {
          "canonical_key": "charizard-base-set",
          "members": ["pokemon-base-set-charizard-holo", "pokemon-base-charizard-(holo)", ...]
        },
        ...
      ],
      ...
    }

Usage:
    python -m pipelines.detect_variants
    python -m pipelines.detect_variants --category pokemon --threshold 0.85
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VOCAB_DIR = DATA_DIR / "_vocab"
OUTPUT_PATH = VOCAB_DIR / "variant_clusters.json"

# Match the v2 seed row format
_ROW_RE = re.compile(
    r"\(\s*'([^']*)'\s*,\s*"     # category
    r"'((?:[^']|'')*)'\s*,\s*"   # set_code
    r"'((?:[^']|'')*)'\s*,\s*"   # item_key
    r"'((?:[^']|'')*)'\s*,",     # title
    re.DOTALL,
)


def _unescape(s: str) -> str:
    return s.replace("''", "'")


def normalize_title(title: str) -> str:
    """
    Aggressively normalize a title for variant detection.

    "Charizard - Holographic" → "charizard"
    "Charizard (Holo)" → "charizard"
    "CHARIZARD HOLO" → "charizard"
    """
    s = title.lower()
    # Strip parenthetical and bracketed content
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    # Strip "holographic", "holo", "foil", "promo" descriptors
    s = re.sub(r"\b(holographic|holo|foil|promo|reverse|shiny)\b", " ", s)
    # Collapse non-alphanumeric to spaces
    s = re.sub(r"[^a-z0-9]+", " ", s)
    # Collapse whitespace, strip
    s = re.sub(r"\s+", " ", s).strip()
    return s


def cluster_category(category_dir: Path) -> list[dict]:
    """
    Walk a category's seed file, group items by normalized title.
    Returns clusters with ≥ 2 members (singletons aren't variants).
    """
    seed = category_dir / "catalog_seed_v2.sql"
    if not seed.exists():
        seed = category_dir / "catalog_seed.sql"
    if not seed.exists():
        return []

    text = seed.read_text(encoding="utf-8")
    groups: dict[str, list[dict]] = defaultdict(list)

    for m in _ROW_RE.finditer(text):
        category = _unescape(m.group(1))
        item_key = _unescape(m.group(3))
        title = _unescape(m.group(4))
        norm = normalize_title(title)
        if not norm:
            continue
        groups[norm].append({
            "item_key": item_key,
            "title": title,
        })

    clusters = []
    for norm, members in groups.items():
        if len(members) < 2:
            continue
        # Pick the shortest title as canonical (often the cleanest form)
        canonical = min(members, key=lambda m: len(m["title"]))
        clusters.append({
            "canonical_key": canonical["item_key"],
            "canonical_title": canonical["title"],
            "normalized": norm,
            "member_count": len(members),
            "members": [m["item_key"] for m in members],
        })

    # Sort by member count desc
    clusters.sort(key=lambda c: -c["member_count"])
    return clusters


def main():
    parser = argparse.ArgumentParser(description="Detect variant clusters")
    parser.add_argument("--category", help="Process a single category")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  VARIANT CLUSTER DETECTION")
    print(f"{'='*60}\n")

    categories: list[Path] = []
    if args.category:
        d = DATA_DIR / args.category
        if not d.exists():
            print(f"ERROR: category '{args.category}' not found")
            sys.exit(1)
        categories = [d]
    else:
        categories = sorted([
            d for d in DATA_DIR.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ])

    all_clusters: dict[str, list[dict]] = {}
    total_clusters = 0
    total_members = 0

    for cat_dir in categories:
        clusters = cluster_category(cat_dir)
        if clusters:
            all_clusters[cat_dir.name] = clusters
            n_clusters = len(clusters)
            n_members = sum(c["member_count"] for c in clusters)
            total_clusters += n_clusters
            total_members += n_members
            print(
                f"  {cat_dir.name:25s}  "
                f"clusters={n_clusters:5d}  "
                f"members={n_members:6d}  "
                f"avg_size={round(n_members / n_clusters, 1)}"
            )

    print(f"\n{'='*60}")
    print(f"  Categories with variants: {len(all_clusters)}")
    print(f"  Total clusters:           {total_clusters}")
    print(f"  Total clustered items:    {total_members}")

    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(all_clusters, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n  Written: {OUTPUT_PATH.relative_to(DATA_DIR.parent)}")
    print(f"  Size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
