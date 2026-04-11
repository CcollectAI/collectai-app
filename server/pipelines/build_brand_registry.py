#!/usr/bin/env python3
"""
Build a canonical brand registry from the catalog vocabulary.

For each category, picks the most-frequent canonical form for each
brand-like field (brand, manufacturer, house, publisher, distributor, etc.).
Maps lowercase variants to the canonical form.

Output: server/data/_vocab/brand_registry.json
    {
      "watches": {
        "rolex": "Rolex",
        "rolex sa": "Rolex",
        "omega": "Omega",
        "omega sa": "Omega",
        ...
      },
      ...
    }

Usage:
    python -m pipelines.build_brand_registry
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VOCAB_DIR = DATA_DIR / "_vocab"
VOCAB_PATH = VOCAB_DIR / "attribute_vocab.json"
REGISTRY_PATH = VOCAB_DIR / "brand_registry.json"

# Fields that represent the "brand" concept across categories
BRAND_FIELDS = [
    "brand", "manufacturer", "house", "publisher", "distributor",
    "label", "agency", "artist", "release_label",
]


def _normalize_for_dedup(name: str) -> str:
    """Lowercase + strip common suffixes to find duplicates."""
    n = name.lower().strip()
    # Strip common corporate suffixes
    for suffix in [" inc", " ltd", " corp", " sa", " ag", " gmbh", " co", " sas"]:
        if n.endswith(suffix) or n.endswith(suffix + "."):
            n = n[: -len(suffix)].strip()
    return n.rstrip(".,")


def main():
    if not VOCAB_PATH.exists():
        print(f"ERROR: vocab not found at {VOCAB_PATH}")
        print("Run: python -m pipelines.build_attribute_vocab first")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  BUILDING BRAND REGISTRY")
    print(f"{'='*60}\n")

    vocab = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))

    registry: dict[str, dict[str, str]] = {}

    for category, fields in vocab.items():
        # Collect all brand-like values across the brand fields for this category
        candidates: dict[str, dict[str, int]] = defaultdict(dict)

        for field in BRAND_FIELDS:
            if field not in fields:
                continue
            for value, count in fields[field].items():
                if not value or len(value) > 80:
                    continue
                key = _normalize_for_dedup(value)
                if not key:
                    continue
                candidates[key][value] = candidates[key].get(value, 0) + count

        if not candidates:
            continue

        # For each normalized key, pick the highest-count canonical form
        cat_registry: dict[str, str] = {}
        for norm_key, variants in candidates.items():
            best = max(variants.items(), key=lambda x: x[1])
            canonical = best[0]
            # Map every variant (lowercased) to this canonical
            for variant in variants:
                cat_registry[variant.lower()] = canonical
            # Also map the dedup key
            cat_registry[norm_key] = canonical

        if cat_registry:
            registry[category] = cat_registry

    # Stats
    total_brands = sum(len(set(r.values())) for r in registry.values())
    total_mappings = sum(len(r) for r in registry.values())
    print(f"Categories with brands: {len(registry)}")
    print(f"Unique canonical brands: {total_brands}")
    print(f"Total mappings (variants → canonical): {total_mappings}")

    # Per-category sample
    print(f"\nTop categories by canonical brand count:")
    by_count = sorted(
        registry.items(),
        key=lambda x: -len(set(x[1].values()))
    )
    for cat, mapping in by_count[:10]:
        n = len(set(mapping.values()))
        print(f"  {cat:25s}  {n:4d} canonical brands  ({len(mapping)} total mappings)")

    # Write
    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWritten: {REGISTRY_PATH.relative_to(DATA_DIR.parent)}")
    print(f"Size: {REGISTRY_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
