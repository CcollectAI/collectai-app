#!/usr/bin/env python3
"""
Train attribute completeness baseline per category.

For each category, computes the "expected" attribute keys (i.e., the ones
present in ≥X% of catalog items) and saves them as a target schema.

This drives:
1. **Scan completeness scoring** — when QuickScan returns attributes, we
   compare them to the expected schema and report a coverage % to the user.
2. **Better OpenAI prompts** — the expected schema becomes the canonical
   list of fields to ask for in the system prompt for each category.

Usage:
    python -m pipelines.train_attribute_completeness
    # → writes server/data/_vocab/attribute_schema.json

Output schema:
    {
      "watches": {
        "expected_fields": ["brand", "model_name", "reference_number", "case_material", "movement"],
        "core_fields": ["brand", "model_name", "reference_number"],
        "total_items": 503
      },
      ...
    }
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VOCAB_DIR = DATA_DIR / "_vocab"
VOCAB_PATH = VOCAB_DIR / "attribute_vocab.json"
SCHEMA_PATH = VOCAB_DIR / "attribute_schema.json"

# Field is "expected" if present in ≥ this fraction of catalog items
EXPECTED_THRESHOLD = 0.30
# Field is "core" if present in ≥ this fraction
CORE_THRESHOLD = 0.80


def main():
    if not VOCAB_PATH.exists():
        print(f"ERROR: vocab not found at {VOCAB_PATH}")
        print(f"Run: python -m pipelines.build_attribute_vocab first")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  ATTRIBUTE COMPLETENESS SCHEMA")
    print(f"{'='*60}\n")

    vocab = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))

    schema: dict[str, Any] = {}
    for category, fields in vocab.items():
        # For each field, count how many distinct items have it
        # (sum of value counts approximates row count if a field is single-valued)
        field_counts: dict[str, int] = {}
        max_count = 0
        for field, values in fields.items():
            total = sum(values.values())
            field_counts[field] = total
            if total > max_count:
                max_count = total

        if max_count == 0:
            continue

        # Sort by count descending
        sorted_fields = sorted(field_counts.items(), key=lambda x: -x[1])

        expected = [
            f for f, c in sorted_fields
            if c / max_count >= EXPECTED_THRESHOLD
        ]
        core = [
            f for f, c in sorted_fields
            if c / max_count >= CORE_THRESHOLD
        ]

        schema[category] = {
            "expected_fields": expected,
            "core_fields": core,
            "field_coverage": {
                f: round(c / max_count, 3)
                for f, c in sorted_fields
            },
            "total_items_with_attrs": max_count,
        }

    # Stats summary
    print(f"Categories analyzed: {len(schema)}")
    print(f"\nTop categories by core field count:")
    by_core = sorted(schema.items(), key=lambda x: -len(x[1]["core_fields"]))
    for cat, info in by_core[:15]:
        print(
            f"  {cat:25s}  "
            f"core={len(info['core_fields'])}  "
            f"expected={len(info['expected_fields'])}  "
            f"items={info['total_items_with_attrs']:,}"
        )
        if info['core_fields']:
            print(f"  {'':25s}  core: {', '.join(info['core_fields'][:6])}")

    # Write schema
    SCHEMA_PATH.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWritten: {SCHEMA_PATH.relative_to(DATA_DIR.parent)}")
    print(f"Size: {SCHEMA_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
