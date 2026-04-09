#!/usr/bin/env python3
"""
Catalog dedup pre-flight audit.

⚠️ KNOWN LIMITATION: this script ONLY audits curated lists from
``get_curated_catalog()``. It does NOT catch duplicates in items that
come from runtime API fetches (Pokemon, MTG, Yu-Gi-Oh, Lorcana — the
4 "API-only" pipelines). For those, the upstream API can return the
same item twice under different set listings. The dedup safety net for
API-driven pipelines is:

  1. **In-memory dedup inside the pipeline's main()** — see
     ``import_pokemon.py`` for the canonical pattern (R46.x). Apply the
     same `seen_keys: set[str]` block before `upsert_catalog(...)` in
     each API-driven pipeline.
  2. **DB unique constraint** ``UNIQUE(category, item_key)`` on
     ``category_items`` — final safety net. Surfaces as a 409 in the
     pipeline log but doesn't break the batch.

If you add a new API-driven pipeline, also add the in-memory dedup AND
extend this script's audit to optionally fetch a sample via that
pipeline's ``--dry-run`` mode.

Imports every ``server/pipelines/import_*.py`` that exposes a
``get_curated_catalog()`` function, normalizes each item's title,
and reports:

  1. Within-pipeline duplicates (same normalized title appears twice
     in one pipeline's curated list — Round 14 dedup should catch
     these but the audit verifies)
  2. Cross-pipeline duplicates (same normalized title shows up in
     two different category pipelines — these are conceptual dupes
     and usually a signal that an item was added to the wrong
     category by mistake)
  3. Pipelines that fail to import (broken module = silent data loss
     during ``import_all``)
  4. Pipelines that have no ``get_curated_catalog`` (API-only ones —
     pokemon, mtg, yugioh — these are expected and listed for
     transparency)

Exit code:
  0 — no duplicates found
  1 — duplicates found (operator should review before baking)
  2 — pipeline import errors (operator should fix before baking)

Usage:
  python3 scripts/catalog_dedup_check.py                # full audit
  python3 scripts/catalog_dedup_check.py --json         # JSON output
  python3 scripts/catalog_dedup_check.py --strict       # exit 1 even on cross-pipeline dupes (default: warn only)
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = REPO_ROOT / "server"
PIPELINES_DIR = SERVER_DIR / "pipelines"

# Make `import pipelines.X` resolvable
sys.path.insert(0, str(SERVER_DIR))


def normalize(title: str) -> str:
    """Lowercase, strip non-alphanumeric, collapse whitespace.

    Catches dupes like 'Charizard VMAX!' vs 'charizard vmax' vs
    'Charizard  VMAX'. Doesn't try to be too smart — over-aggressive
    normalization (e.g. removing year suffixes) creates false positives.
    """
    if not title:
        return ""
    s = title.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def discover_pipelines() -> list[tuple[str, str]]:
    """Return list of (category, module_name) for every import_*.py."""
    out: list[tuple[str, str]] = []
    for path in sorted(PIPELINES_DIR.glob("import_*.py")):
        name = path.stem
        if name in ("import_common", "import_all", "import_books_isbn"):
            continue  # not a category pipeline
        category = name.removeprefix("import_")
        out.append((category, f"pipelines.{name}"))
    return out


def audit_one(category: str, module_name: str) -> dict:
    """Import the pipeline, call get_curated_catalog(), report findings."""
    result: dict = {
        "category": category,
        "module": module_name,
        "status": "ok",
        "item_count": 0,
        "internal_duplicates": [],
        "items": [],
        "error": None,
    }
    try:
        mod = importlib.import_module(module_name)
    except Exception as e:
        result["status"] = "import_error"
        result["error"] = f"{type(e).__name__}: {e}"
        return result

    fn = getattr(mod, "get_curated_catalog", None)
    if fn is None:
        result["status"] = "api_only"  # legitimate — pokemon, mtg via runtime API
        return result

    try:
        items = fn()
    except Exception as e:
        result["status"] = "call_error"
        result["error"] = f"{type(e).__name__}: {e}"
        return result

    if not isinstance(items, list):
        result["status"] = "bad_return"
        result["error"] = f"expected list, got {type(items).__name__}"
        return result

    title_seen: dict[str, int] = defaultdict(int)
    key_seen: dict[str, int] = defaultdict(int)
    titles: list[str] = []
    for item in items:
        # Items can be dicts or CatalogItem dataclasses depending on pipeline vintage
        if isinstance(item, dict):
            title = item.get("title") or item.get("name") or ""
            key = item.get("item_key") or ""
        else:
            title = getattr(item, "title", "") or getattr(item, "name", "")
            key = getattr(item, "item_key", "") or ""
        if not title:
            continue
        norm = normalize(title)
        title_seen[norm] += 1
        if key:
            key_seen[key] += 1
        titles.append(title)

    result["item_count"] = len(titles)
    result["items"] = list(title_seen.keys())  # normalized titles for cross-pipeline check
    # Title collisions = same normalized title, possibly distinct editions (UX warning)
    result["title_collisions"] = sorted(
        [(t, c) for t, c in title_seen.items() if c > 1],
        key=lambda x: -x[1],
    )
    # item_key collisions = real DB-level duplicates (FAIL — bake will collapse but data is wrong)
    result["key_collisions"] = sorted(
        [(k, c) for k, c in key_seen.items() if c > 1],
        key=lambda x: -x[1],
    )
    # Backwards-compat: keep `internal_duplicates` as the SQL-level dupes
    result["internal_duplicates"] = result["key_collisions"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Catalog dedup pre-flight audit")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human output")
    parser.add_argument("--strict", action="store_true", help="exit 1 on cross-pipeline dupes too")
    args = parser.parse_args()

    pipelines = discover_pipelines()
    results = [audit_one(cat, mod) for cat, mod in pipelines]

    # Cross-pipeline duplicates: same normalized title in 2+ category pipelines
    title_to_categories: dict[str, list[str]] = defaultdict(list)
    for r in results:
        if r["status"] != "ok":
            continue
        for norm in r["items"]:
            title_to_categories[norm].append(r["category"])
    cross_pipeline = {
        t: sorted(set(cats)) for t, cats in title_to_categories.items()
        if len(set(cats)) >= 2
    }

    summary = {
        "total_pipelines": len(results),
        "ok_pipelines": sum(1 for r in results if r["status"] == "ok"),
        "api_only_pipelines": sum(1 for r in results if r["status"] == "api_only"),
        "broken_pipelines": [
            {"category": r["category"], "status": r["status"], "error": r["error"]}
            for r in results if r["status"] in ("import_error", "call_error", "bad_return")
        ],
        "total_items": sum(r["item_count"] for r in results),
        "pipelines_with_key_collisions": [
            {
                "category": r["category"],
                "dupe_count": len(r["key_collisions"]),
                "examples": r["key_collisions"][:5],
            }
            for r in results if r.get("key_collisions")
        ],
        "pipelines_with_title_collisions": [
            {
                "category": r["category"],
                "dupe_count": len(r["title_collisions"]),
                "examples": r["title_collisions"][:5],
            }
            for r in results if r.get("title_collisions")
        ],
        # Backwards-compat alias used by older scripts
        "pipelines_with_internal_dupes": [
            {
                "category": r["category"],
                "dupe_count": len(r["key_collisions"]),
                "examples": r["key_collisions"][:5],
            }
            for r in results if r.get("key_collisions")
        ],
        "cross_pipeline_dupes_count": len(cross_pipeline),
        "cross_pipeline_dupes_examples": dict(list(cross_pipeline.items())[:20]),
    }

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print("─" * 70)
        print("  CollectAI catalog dedup audit")
        print("─" * 70)
        print(f"Pipelines scanned:      {summary['total_pipelines']}")
        print(f"  curated (with items): {summary['ok_pipelines']}")
        print(f"  API-only (pokemon/mtg/etc): {summary['api_only_pipelines']}")
        print(f"  broken:               {len(summary['broken_pipelines'])}")
        print(f"Total curated items:    {summary['total_items']:,}")
        print()

        if summary["broken_pipelines"]:
            print("❌ Broken pipelines (FIX BEFORE BAKING):")
            for b in summary["broken_pipelines"]:
                print(f"  • {b['category']:24s} {b['status']:14s} {b['error']}")
            print()

        if summary["pipelines_with_key_collisions"]:
            print("❌ Pipelines with item_key collisions (REAL DB-level duplicates):")
            for p in summary["pipelines_with_key_collisions"]:
                print(f"  • {p['category']:24s} {p['dupe_count']} colliding keys")
                for k, count in p["examples"]:
                    print(f"      ×{count}  {k}")
            print()
        else:
            print("✅ No item_key collisions — all pipelines safe to upsert.")
            print()

        if summary["pipelines_with_title_collisions"]:
            print("ℹ️  Pipelines with title-only collisions (likely intentional editions):")
            for p in summary["pipelines_with_title_collisions"][:10]:
                print(f"  • {p['category']:24s} {p['dupe_count']} title clusters")
            if len(summary["pipelines_with_title_collisions"]) > 10:
                print(f"  ... +{len(summary['pipelines_with_title_collisions']) - 10} more")
            print("  (multiple editions of the same title, e.g. steelbook vs 4K vs Aniplex LE —")
            print("   these are distinct SKUs with unique item_keys, so they bake correctly)")
            print()

        if summary["cross_pipeline_dupes_count"]:
            print(f"⚠️  Cross-pipeline duplicates: {summary['cross_pipeline_dupes_count']}")
            print("   (same normalized title appears in 2+ category pipelines —")
            print("    usually a sign an item was added to the wrong category)")
            for title, cats in list(summary["cross_pipeline_dupes_examples"].items())[:10]:
                print(f"  • '{title}'  ⇒  {', '.join(cats)}")
            if summary["cross_pipeline_dupes_count"] > 10:
                print(f"  ... +{summary['cross_pipeline_dupes_count'] - 10} more")
            print()
        else:
            print("✅ No cross-pipeline duplicates.")
            print()

        print("─" * 70)
        verdict = "PASS" if (
            not summary["broken_pipelines"]
            and not summary["pipelines_with_internal_dupes"]
            and (not args.strict or not summary["cross_pipeline_dupes_count"])
        ) else "FAIL"
        print(f"  Verdict: {verdict}")
        print("─" * 70)

    # Exit code
    if summary["broken_pipelines"]:
        return 2
    if summary["pipelines_with_key_collisions"]:
        return 1
    if args.strict and summary["cross_pipeline_dupes_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
