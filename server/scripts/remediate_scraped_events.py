#!/usr/bin/env python3
"""Retro-apply the ingest sanitiser to events already in the table.

Written 2026-07-27. `EventUpserter._sanitise` cleans events on the way IN,
but 14 `source='newsletter'` rows were stored before it existed — page
chrome like "Site Navigation" and "We use Cookies", plus two real events
wearing markdown.

Deliberately calls the SAME clean_title / clean_location / reject_reason
functions the ingest path uses rather than reimplementing them in SQL. A
SQL copy would be a third implementation of the rule and would drift from
the other two the first time one changed.

Rejected rows are moved to status='rejected', NOT deleted: every read path
filters status='published', so quarantining is sufficient and reversible.
Verified before writing this: 0 event_attendees rows reference any
newsletter event, so nothing cascades.

Usage:
    python scripts/remediate_scraped_events.py --dry-run
    python scripts/remediate_scraped_events.py --apply
    python scripts/remediate_scraped_events.py --apply --source newsletter
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg  # noqa: E402

from app.lib.event_quality import (  # noqa: E402
    clean_location,
    clean_title,
    map_source_to_trust_tier,
    reject_reason,
    score_event,
)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes")
    ap.add_argument("--dry-run", action="store_true", help="default; no writes")
    ap.add_argument("--source", default="newsletter")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("ERROR: DB_DSN_DIRECT not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT id, title, location, description, date::text AS date, "
            "source, source_url, image_url, quality_score, status "
            "FROM events WHERE source = $1",
            args.source,
        )
        print(f"{len(rows)} rows with source={args.source!r}\n")

        repaired = rejected = unchanged = 0
        tier = map_source_to_trust_tier(args.source)

        for r in rows:
            new_title = clean_title(r["title"])
            new_loc = clean_location(r["location"])
            new_desc = r["description"]
            if new_desc and new_desc.strip() == (r["title"] or "").strip():
                new_desc = None
            if new_desc and new_desc.strip() == new_title.strip():
                new_desc = None

            reason = reject_reason(new_title, r["date"])

            if reason:
                rejected += 1
                print(f"  REJECT [{reason:18}] {r['title'][:56]!r}")
                if apply:
                    await conn.execute(
                        "UPDATE events SET status = 'rejected' WHERE id = $1", r["id"]
                    )
                continue

            score, reasons = score_event(
                {
                    "title": new_title,
                    "location": new_loc or "",
                    "date": r["date"],
                    "source_url": r["source_url"] or "",
                    "image_url": r["image_url"] or "",
                    "description": new_desc or "",
                },
                trust_tier=tier,
            )

            changed = (
                new_title != r["title"]
                or new_loc != r["location"]
                or new_desc != r["description"]
                or score != r["quality_score"]
            )
            if not changed:
                unchanged += 1
                continue

            repaired += 1
            print(f"  KEEP   [q {r['quality_score']} -> {score:3}] {r['title'][:44]!r}")
            print(f"           title -> {new_title[:60]!r}")
            if r["location"] != new_loc:
                print(f"           loc   -> {new_loc!r}  (was {(r['location'] or '')[:34]!r})")
            if apply:
                await conn.execute(
                    "UPDATE events SET title=$1, location=$2, description=$3, "
                    "quality_score=$4 WHERE id=$5",
                    new_title, new_loc, new_desc, score, r["id"],
                )

        print(
            f"\n{'APPLIED' if apply else 'DRY-RUN'}: "
            f"{repaired} repaired, {rejected} quarantined, {unchanged} unchanged"
        )
        if not apply:
            print("Re-run with --apply to write.")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
