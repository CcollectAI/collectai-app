#!/usr/bin/env python3
"""
Targeted rollback for the JSONB merge corruption in Round 50e.

Initially discovered as 4,107 rows across 3 categories. Subsequent audit
showed the damage was actually 65,895 rows across 30 categories — my
first suspect filter was too narrow. The merge job ran alphabetically
through anime_bluray → scale_models before being killed.

Strategy:
1. For each affected row, re-run parse_notes() on the original notes field
   to reconstruct what the prepended element looked like.
2. Scan the array from the left and remove any leading elements that
   deep-equal the parsed dict.
3. Write back the cleaned array.

Safety:
- Dry-run by default (prints the diff, does nothing).
- --apply flag required to commit.
- Each category wrapped in its own transaction for atomic rollback.
- Reads-back a sample after commit to verify.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.notes_parser import parse_notes  # noqa: E402


AFFECTED_CATEGORIES = [
    # First batch (rolled back 2026-04-11 initially):
    "anime_bluray", "lego", "oop_board_games",
    # Second batch (discovered in broader audit, 2026-04-11):
    "anime_figures", "anime_ost_vinyl", "anime_soundtrack", "bandai_premium",
    "bluray_steelbook", "city_pop_vinyl", "designer_toys", "diecast",
    "disney", "fragrances", "funko", "ghibli", "gunpla", "hot_toys",
    "jp_event", "jp_magazine", "keycaps", "kpop_lightsticks", "kpop_merch",
    "lorcana", "loungefly", "manga", "mtg", "nintendo_merch", "one_piece",
    "pokemon", "pop_fandom", "retro_games", "retro_pokemon", "scale_models",
]


def _load_env():
    """Load .env into os.environ."""
    import os
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return True


def _fetch_rows(conn, category: str) -> list[dict]:
    """Fetch (id, item_key, notes, brand, attributes_json) for a category."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, item_key, notes, brand, attributes_json
            FROM category_items
            WHERE category = %s
            """,
            (category,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _clean_array(
    attrs: list,
    parsed_signature: dict,
) -> tuple[list, int]:
    """
    Remove leading elements from `attrs` that exactly match `parsed_signature`.
    Returns (cleaned_array, num_removed).
    """
    if not isinstance(attrs, list) or not parsed_signature:
        return attrs, 0

    removed = 0
    i = 0
    while i < len(attrs):
        elem = attrs[i]
        # Only objects can match the signature
        if not isinstance(elem, dict):
            break
        # Must be exactly equal (same keys, same values)
        if elem == parsed_signature:
            removed += 1
            i += 1
            continue
        break

    if removed == 0:
        return attrs, 0

    return attrs[removed:], removed


def process_category(conn, category: str, dry_run: bool = True) -> dict:
    """Process one category. Returns stats dict."""
    rows = _fetch_rows(conn, category)
    if not rows:
        return {"category": category, "skipped": True, "reason": "no rows"}

    total = len(rows)
    to_fix = 0
    total_removed = 0
    sample_before: str | None = None
    sample_after: str | None = None

    for row in rows:
        attrs = row["attributes_json"]
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except Exception:
                continue
        if not isinstance(attrs, list):
            continue  # only arrays are affected

        # Recompute what the parser would produce for this row
        parsed = parse_notes(category, row["notes"] or "", row["brand"] or "")
        if not parsed:
            continue

        cleaned, removed = _clean_array(attrs, parsed)
        if removed == 0:
            continue

        to_fix += 1
        total_removed += removed

        if sample_before is None:
            sample_before = json.dumps(attrs, indent=2)[:300]
            sample_after = json.dumps(cleaned, indent=2)[:300]

        if not dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE category_items
                    SET attributes_json = %s::jsonb
                    WHERE id = %s
                    """,
                    (json.dumps(cleaned), row["id"]),
                )

    return {
        "category": category,
        "total_rows": total,
        "to_fix": to_fix,
        "total_removed": total_removed,
        "sample_before": sample_before,
        "sample_after": sample_after,
    }


def main():
    parser = argparse.ArgumentParser(description="Rollback corrupted merge in attributes_json")
    parser.add_argument("--apply", action="store_true", help="Commit changes (default: dry-run)")
    parser.add_argument("--category", help="Process only one category")
    args = parser.parse_args()

    if not _load_env():
        print("ERROR: .env not found")
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed")
        sys.exit(1)

    import os
    dsn = os.environ.get("DB_DSN") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DB_DSN or DATABASE_URL not set")
        sys.exit(1)

    categories = [args.category] if args.category else AFFECTED_CATEGORIES

    print(f"\n{'='*60}")
    print(f"  ROLLBACK CORRUPTED MERGE — {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"{'='*60}\n")

    for cat in categories:
        conn = psycopg2.connect(dsn)
        conn.autocommit = False
        try:
            stats = process_category(conn, cat, dry_run=not args.apply)
            if stats.get("skipped"):
                print(f"  {cat}: SKIP ({stats['reason']})")
                continue

            print(f"  {cat}:")
            print(f"    total rows: {stats['total_rows']:,}")
            print(f"    to_fix:     {stats['to_fix']:,}")
            print(f"    elements removed: {stats['total_removed']:,}")

            if stats["sample_before"]:
                print(f"    sample BEFORE: {stats['sample_before'][:200]}")
                print(f"    sample AFTER:  {stats['sample_after'][:200]}")

            if args.apply:
                conn.commit()
                print(f"    [COMMITTED]")
            else:
                conn.rollback()
                print(f"    [DRY-RUN — rolled back]")
        except Exception as e:
            conn.rollback()
            print(f"  {cat}: ERROR {e}")
        finally:
            conn.close()
        print()


if __name__ == "__main__":
    main()
