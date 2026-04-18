#!/usr/bin/env python3
"""Repair category_items.attributes_json type corruption.

Across 140K rows, attributes_json is stored as:
  - 136K JSONB strings (double-stringified: a JSON-string that itself is JSON)
  - 4K  JSONB arrays  (single-element arrays wrapping a JSON-string of the real object)
  -  0  JSONB objects (what the code expects)

This script canonicalises every row to a flat JSONB object. Rows already
object-typed are left alone.

Strategy:
  string  → parse the string; if result is dict, store it directly.
            If the parsed result is itself a string or array, log + skip
            (unexpected nesting; investigate manually).
  array   → unwrap elements. Each element is typically a JSON-string of a
            dict; parse each, shallow-merge into a single object (last writer
            wins on key conflicts, which is rare in practice because the
            array elements represent historical imports of the same item).

Dry-run by default. Pass --apply to commit. Writes a before/after sample
for 5 rows per category so you can eyeball it before committing.

Idempotent: re-running after a successful apply is a no-op.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [repair_attrs] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_maybe_string(val):
    """Parse a value that may be a JSON-string, dict, or list. Return dict or None."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None
        # Recurse once in case of double-string wrapping
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(parsed, dict):
            return parsed
        return None
    return None


def _repair_value(attrs_raw):
    """Return a canonical dict for the given attributes_json value.

    asyncpg by default returns jsonb as the raw JSON *text*, so everything
    arrives as ``str``. We json.loads once to get the python-native shape
    (dict/list/str/etc), then normalise:
      - dict       -> return as-is
      - list       -> shallow-merge dict-like elements (each element may itself
                      be a stringified JSON dict)
      - str        -> parse once more; if the parsed result is a string again,
                      recurse one more time (covers double-stringified rows).
    """
    if attrs_raw is None:
        return None
    if isinstance(attrs_raw, dict):
        return attrs_raw

    # First decode step — asyncpg hands us the raw jsonb text
    if isinstance(attrs_raw, str):
        try:
            decoded = json.loads(attrs_raw)
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        decoded = attrs_raw

    # Decoded can be dict, list, str, int, float, bool, None
    if isinstance(decoded, dict):
        return decoded

    if isinstance(decoded, list):
        merged: dict = {}
        for el in decoded:
            parsed = _parse_maybe_string(el)
            if parsed:
                merged.update(parsed)
        return merged if merged else None

    if isinstance(decoded, str):
        return _parse_maybe_string(decoded)

    return None


async def run(apply: bool, sample_only: bool = False) -> int:
    dsn = os.getenv("DB_DSN")
    if not dsn:
        logger.error("DB_DSN not set")
        return 1

    conn = await asyncpg.connect(dsn)
    try:
        # Type distribution before
        before = await conn.fetch(
            "SELECT jsonb_typeof(attributes_json) AS t, COUNT(*) "
            "FROM public.category_items GROUP BY 1"
        )
        logger.info("Before: %s", {r["t"]: r["count"] for r in before})

        if sample_only:
            rows = await conn.fetch(
                "SELECT id, category, item_key, attributes_json "
                "FROM public.category_items "
                "WHERE jsonb_typeof(attributes_json) <> 'object' "
                "LIMIT 10"
            )
            for r in rows:
                raw = r["attributes_json"]
                repaired = _repair_value(raw)
                logger.info(
                    "%s:%s typeof=%s -> keys=%s",
                    r["category"], r["item_key"],
                    type(raw).__name__,
                    list(repaired.keys()) if repaired else "UNREPAIRABLE",
                )
            return 0

        # Each iteration pulls the next batch of rows that are still NOT objects
        # (i.e., have not yet been repaired or are unrepairable). We track
        # unrepairable IDs in a skip set so the SELECT eventually returns empty.
        BATCH = 500
        skip_ids: set = set()
        total_repaired = 0
        total_unrepairable = 0
        total_unchanged = 0
        scanned = 0

        while True:
            skip_array = list(skip_ids) if skip_ids else [None]
            rows = await conn.fetch(
                "SELECT id, attributes_json FROM public.category_items "
                "WHERE jsonb_typeof(attributes_json) <> 'object' "
                "  AND id <> ALL($1::uuid[]) "
                "ORDER BY id LIMIT $2",
                skip_array if skip_ids else [],
                BATCH,
            )
            if not rows:
                break
            scanned += len(rows)

            updates: list[tuple] = []
            for r in rows:
                repaired = _repair_value(r["attributes_json"])
                if repaired is None:
                    total_unrepairable += 1
                    skip_ids.add(r["id"])
                    continue
                if not repaired:
                    total_unchanged += 1
                    skip_ids.add(r["id"])
                    continue
                updates.append((r["id"], json.dumps(repaired)))

            if apply and updates:
                async with conn.transaction():
                    await conn.executemany(
                        "UPDATE public.category_items SET attributes_json = $2::jsonb "
                        "WHERE id = $1",
                        updates,
                    )
                total_repaired += len(updates)
            elif updates:
                total_repaired += len(updates)

            if scanned % 5000 < BATCH:
                logger.info(
                    "progress: scanned=%d repaired=%d unrepairable=%d empty=%d",
                    scanned, total_repaired, total_unrepairable, total_unchanged,
                )

        logger.info(
            "[%s] repaired=%d unrepairable=%d empty=%d",
            "APPLY" if apply else "DRY-RUN",
            total_repaired, total_unrepairable, total_unchanged,
        )

        after = await conn.fetch(
            "SELECT jsonb_typeof(attributes_json) AS t, COUNT(*) "
            "FROM public.category_items GROUP BY 1"
        )
        logger.info("After: %s", {r["t"]: r["count"] for r in after})
        return 0
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="commit changes (default: dry-run)")
    parser.add_argument("--sample", action="store_true", help="show 10 sample repairs and exit")
    args = parser.parse_args()
    rc = asyncio.run(run(apply=args.apply, sample_only=args.sample))
    sys.exit(rc)


if __name__ == "__main__":
    main()
