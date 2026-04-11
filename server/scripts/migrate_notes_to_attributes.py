#!/usr/bin/env python3
"""
Migrate catalog seed SQL files: parse free-text `notes` into structured
`attributes_json`.

Reads each `server/data/<category>/catalog_seed.sql`, parses the notes
column, and writes a new `catalog_seed_v2.sql` next to it that includes
attributes_json.

Optionally with --apply, executes UPDATE statements against the live DB
to backfill attributes_json on existing rows. Without --apply, runs in
dry-run mode and prints stats.

Usage:
    # Local-only: parse SQL files, write v2 versions, no DB
    python -m scripts.migrate_notes_to_attributes

    # Run on a single category
    python -m scripts.migrate_notes_to_attributes --category watches

    # Apply to live DB (requires DB_DSN)
    python -m scripts.migrate_notes_to_attributes --apply
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Make pipelines importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.notes_parser import parse_notes  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Match a single INSERT row tuple for category_items.
# Captures category, set_code, item_key, title, brand, rarity, notes.
_ROW_RE = re.compile(
    r"\(\s*'([^']*)'\s*,\s*"     # category
    r"'((?:[^']|'')*)'\s*,\s*"    # set_code
    r"'((?:[^']|'')*)'\s*,\s*"    # item_key
    r"'((?:[^']|'')*)'\s*,\s*"    # title
    r"'((?:[^']|'')*)'\s*,\s*"    # brand
    r"'((?:[^']|'')*)'\s*,\s*"    # rarity
    r"'((?:[^']|'')*)'\s*\)",     # notes
    re.DOTALL,
)


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def _unescape(s: str) -> str:
    return s.replace("''", "'")


def parse_seed_file(path: Path) -> tuple[list[dict], int]:
    """
    Parse a catalog_seed.sql file. Returns (rows, total_with_notes).

    Each row is {category, set_code, item_key, title, brand, rarity, notes}.
    """
    text = path.read_text(encoding="utf-8")
    rows = []
    total_with_notes = 0
    for m in _ROW_RE.finditer(text):
        category, set_code, item_key, title, brand, rarity, notes = (
            _unescape(m.group(i)) for i in range(1, 8)
        )
        if notes.strip():
            total_with_notes += 1
        rows.append({
            "category": category,
            "set_code": set_code,
            "item_key": item_key,
            "title": title,
            "brand": brand,
            "rarity": rarity,
            "notes": notes,
        })
    return rows, total_with_notes


def write_v2_seed(path: Path, rows: list[dict], stats: dict) -> Path:
    """
    Write a v2 seed SQL file with attributes_json populated.
    Returns the output path.
    """
    out = path.parent / "catalog_seed_v2.sql"
    lines: list[str] = []
    lines.append(f"-- Auto-generated v2 catalog seed for {path.parent.name}")
    lines.append(f"-- Source: {path.name}")
    lines.append(f"-- Items: {len(rows)} | with notes: {stats['with_notes']} | parsed: {stats['parsed']}")
    lines.append("")
    lines.append("INSERT INTO public.category_items (")
    lines.append("  category, set_code, item_key, title, brand, rarity, notes, attributes_json")
    lines.append(") VALUES")

    value_lines = []
    for row in rows:
        attrs = parse_notes(row["category"], row["notes"], row["brand"])
        attrs_sql = _sql_escape(json.dumps(attrs)) if attrs else "{}"
        value_lines.append(
            f"  ('{_sql_escape(row['category'])}', "
            f"'{_sql_escape(row['set_code'])}', "
            f"'{_sql_escape(row['item_key'])}', "
            f"'{_sql_escape(row['title'])}', "
            f"'{_sql_escape(row['brand'])}', "
            f"'{_sql_escape(row['rarity'])}', "
            f"'{_sql_escape(row['notes'])}', "
            f"'{attrs_sql}'::jsonb)"
        )
    lines.append(",\n".join(value_lines))
    lines.append("ON CONFLICT (category, item_key) DO UPDATE")
    lines.append("  SET attributes_json = EXCLUDED.attributes_json")
    lines.append("  WHERE category_items.attributes_json = '{}'::jsonb;")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def process_category(category_dir: Path) -> dict:
    """Process one category directory. Returns stats dict."""
    seed_path = category_dir / "catalog_seed.sql"
    if not seed_path.exists():
        return {"category": category_dir.name, "skipped": True}

    rows, with_notes = parse_seed_file(seed_path)
    if not rows:
        return {"category": category_dir.name, "skipped": True}

    parsed_count = 0
    total_attrs = 0
    sample_keys: set[str] = set()
    for row in rows:
        attrs = parse_notes(row["category"], row["notes"], row["brand"])
        if attrs:
            parsed_count += 1
            total_attrs += len(attrs)
            sample_keys.update(attrs.keys())

    stats = {
        "category": category_dir.name,
        "rows": len(rows),
        "with_notes": with_notes,
        "parsed": parsed_count,
        "total_attrs": total_attrs,
        "avg_attrs": round(total_attrs / parsed_count, 1) if parsed_count else 0,
        "sample_keys": sorted(sample_keys)[:8],
    }

    out_path = write_v2_seed(seed_path, rows, stats)
    stats["output"] = str(out_path.relative_to(category_dir.parent.parent))
    return stats


def _apply_to_db(rows: list[dict]) -> int:
    """
    Apply parsed attributes to live DB. Reads DATABASE_URL from environment.
    Returns the number of rows updated.

    Only updates rows where attributes_json is currently empty ('{}').
    """
    import os
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DATABASE_URL or DB_DSN not set in environment")
        return 0

    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        return 0

    updated = 0
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = False
        with conn.cursor() as cur:
            for row in rows:
                attrs = parse_notes(row["category"], row["notes"], row["brand"])
                if not attrs:
                    continue
                cur.execute(
                    """
                    UPDATE category_items
                    SET attributes_json = %s::jsonb
                    WHERE category = %s
                      AND item_key = %s
                      AND (attributes_json IS NULL OR attributes_json = '{}'::jsonb)
                    """,
                    (Json(attrs), row["category"], row["item_key"]),
                )
                if cur.rowcount > 0:
                    updated += cur.rowcount
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  DB error: {e}")
        return updated
    return updated


def main():
    parser = argparse.ArgumentParser(description="Migrate catalog notes → attributes_json")
    parser.add_argument("--category", help="Process only this category")
    parser.add_argument("--apply", action="store_true", help="Execute against live DB (requires DATABASE_URL)")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-category output")
    args = parser.parse_args()

    categories: list[Path] = []
    if args.category:
        d = DATA_DIR / args.category
        if not d.exists():
            print(f"ERROR: category '{args.category}' not found at {d}")
            sys.exit(1)
        categories.append(d)
    else:
        categories = sorted([d for d in DATA_DIR.iterdir() if d.is_dir()])

    print(f"\n{'='*70}")
    print(f"  CATALOG NOTES → ATTRIBUTES MIGRATION")
    print(f"{'='*70}")
    print(f"  Categories to process: {len(categories)}\n")

    all_stats: list[dict] = []
    total_db_updated = 0
    for cat_dir in categories:
        try:
            stats = process_category(cat_dir)
            all_stats.append(stats)
            if not args.quiet and not stats.get("skipped"):
                pct = round(100 * stats["parsed"] / stats["with_notes"], 1) if stats["with_notes"] else 0
                print(
                    f"  {stats['category']:25s}  "
                    f"rows={stats['rows']:5d}  "
                    f"with_notes={stats['with_notes']:5d}  "
                    f"parsed={stats['parsed']:5d}  ({pct}%)  "
                    f"avg_attrs={stats['avg_attrs']}"
                )
                if stats["sample_keys"]:
                    print(f"  {'':25s}  sample keys: {', '.join(stats['sample_keys'])}")

            # Apply to live DB if requested
            if args.apply and not stats.get("skipped"):
                seed_path = cat_dir / "catalog_seed.sql"
                if seed_path.exists():
                    rows, _ = parse_seed_file(seed_path)
                    n_updated = _apply_to_db(rows)
                    total_db_updated += n_updated
                    if not args.quiet:
                        print(f"  {'':25s}  → DB rows updated: {n_updated}")
        except Exception as e:
            print(f"  {cat_dir.name:25s}  ERROR: {e}")

    print(f"\n{'='*70}")
    total_rows = sum(s.get("rows", 0) for s in all_stats)
    total_with_notes = sum(s.get("with_notes", 0) for s in all_stats)
    total_parsed = sum(s.get("parsed", 0) for s in all_stats)
    total_attrs = sum(s.get("total_attrs", 0) for s in all_stats)
    print(f"  TOTAL")
    print(f"{'='*70}")
    print(f"  Categories processed: {len([s for s in all_stats if not s.get('skipped')])}")
    print(f"  Total rows:           {total_rows:,}")
    print(f"  Rows with notes:      {total_with_notes:,}")
    print(f"  Rows parsed to attrs: {total_parsed:,}  ({round(100*total_parsed/total_with_notes, 1) if total_with_notes else 0}%)")
    print(f"  Attribute keys added: {total_attrs:,}")
    if args.apply:
        print(f"  DB rows updated:      {total_db_updated:,}")
    print(f"\n  v2 seeds written to: server/data/<category>/catalog_seed_v2.sql")
    if not args.apply:
        print(f"  Run with --apply to push to live DB (requires DATABASE_URL)")
    print()


if __name__ == "__main__":
    main()
