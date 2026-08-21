#!/usr/bin/env python3
"""
ADVISORY audit: tables that are read but never written (or vice versa).

Why this exists
---------------
Every "built but not working" bug found on 2026-07-24 had the same shape: a
reader and a writer that were never connected, plus a construct that turns
"not connected" into an empty result rather than an error --
`except Exception: log`, Pydantic dropping undeclared fields, Zod stripping
undeclared keys, `LEFT JOIN` yielding NULL, `?? 0` defaults. Nothing ever went
red, so a dead feature looked like an empty one. Examples caught:

  * billing_router JOINed `device_tokens` -- a table with zero writers. Every
    sponsored-event push blast reached nobody, for months.
  * `portfolio_values` had no writer, so Home's portfolio change was pinned to
    0.00% regardless of the collection.
  * `user_category_ownership` had no writer, so Collection Completeness could
    never render.

This script mechanizes the sweep that found them.

Method (the naive version does NOT work)
----------------------------------------
A plain regex over source produced ~40 phantom tables (`actually`, `but`, and
`collections` from `import collections`). Four steps are required:

  1. extract candidate identifiers from code,
  2. keep only names that exist in live `pg_class`,
  3. classify each code reference as a read or a write,
  4. before declaring "no writer", check `pg_proc.prosrc` and `pg_trigger` --
     DB functions and triggers are writers too. `event_follows_v1`,
     `activity_feed` and `user_public_profile_v1` all look writer-less in code
     but have DB functions; only checking whether anything *calls* those
     functions settles it.

ADVISORY ONLY: this always exits 0. It is not wired into the bake preflight
chain and must not be -- it reports a backlog, and a blocking gate would wedge
every deploy until that backlog is zero. Flip `--strict` on once the findings
list is empty.

Usage:
    python3 scripts/audit_orphan_tables.py             # report, exit 0
    python3 scripts/audit_orphan_tables.py --strict    # exit 1 on new findings
    python3 scripts/audit_orphan_tables.py --json      # machine-readable
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:
    # Only the DB phase needs the driver. --scan-only must still run on a dev
    # machine that has the full repo but no asyncpg.
    asyncpg = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[2]
CODE_ROOTS = [REPO / "server" / "app", REPO / "server" / "workers", REPO / "src", REPO / "app"]
CODE_SUFFIXES = {".py", ".ts", ".tsx"}

# Deliberately dead / legacy. Each entry needs a reason so this list stays
# honest instead of becoming a place to hide real findings.
ALLOWLIST: dict[str, str] = {
    "alerts": "legacy; superseded by user_price_alerts (20260226_drop_alerts.sql)",
    "model_promotion_log": "write-only ops log, read by hand",
    "device_tokens": "created by a drift-sweep migration in error; query repointed 2026-07-24, table pending drop",
    "user_category_ownership": "superseded 2026-07-24 - v_category_summaries_v1 now joins items.canonical_key",
    "portfolio_values": "superseded 2026-07-24 - getPortfolioSummary now reads /portfolio/overview",
    "supply_snapshots": "writer intentionally killswitched (DEAL_DISCOVERY_ENABLED=false)",
    "event_follows_v1": "2026-07-25 product decision: event following is not a feature we want. "
                        "Readers left in place but deliberately never populated — do not 'fix' by "
                        "wiring a writer. events.canonical_key being NULL is the same decision.",
    "user_challenge_progress": "2026-07-25 product decision: gamification challenges are out of "
                               "scope. `challenges` has 6 seed rows but no progress writer, and "
                               "that is intentional — do not wire one.",
    "images": "FALSE POSITIVE, verified 2026-07-25. The only 'reader' is prose in a docstring: "
              "vision_classifier.py:4 reads 'Classifies collectible items FROM IMAGES using a "
              "3-tier approach'. The PY_READ regex cannot tell SQL from English. No query "
              "touches this table.",
    "taxonomy_registry": "Vestigial, verified 2026-07-25. taxonomy_router falls back to "
                         "_fallback_taxonomy() when the table is empty and GET /taxonomy/current "
                         "returns the full 36-category taxonomy from code. The table would only "
                         "matter for versioned remapping; pipelines/taxonomy_seed.py can seed it "
                         "if that is ever wanted. Nothing is broken.",
}

# Write verbs. A reference is a WRITE if one of these appears near the table
# name; anything else referencing it counts as a READ.
PY_WRITE = re.compile(
    r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|COPY|TRUNCATE|UPSERT|MERGE\s+INTO)\s+"
    r"(?:public\.)?[\"']?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
PY_READ = re.compile(
    r"\b(?:FROM|JOIN)\s+(?:public\.)?[\"']?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
# supabase-js: .from('table') followed (possibly later) by .insert/.update/...
TS_FROM = re.compile(r"\.from\(\s*['\"]([a-z_][a-z0-9_]*)['\"]\s*\)([\s\S]{0,200})")
TS_WRITE_CALL = re.compile(r"\.(insert|update|upsert|delete)\s*\(")


def scan_code() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (reads, writes): table -> set of 'path:line' references."""
    reads: dict[str, set[str]] = {}
    writes: dict[str, set[str]] = {}

    def add(bucket: dict[str, set[str]], name: str, where: str) -> None:
        bucket.setdefault(name.lower(), set()).add(where)

    for root in CODE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in CODE_SUFFIXES or not path.is_file():
                continue
            if "node_modules" in path.parts or "__tests__" in path.parts or "/tests/" in str(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = str(path.relative_to(REPO))

            if path.suffix == ".py":
                for m in PY_WRITE.finditer(text):
                    add(writes, m.group(2), "%s:%d" % (rel, text[: m.start()].count("\n") + 1))
                for m in PY_READ.finditer(text):
                    add(reads, m.group(1), "%s:%d" % (rel, text[: m.start()].count("\n") + 1))
            else:
                for m in TS_FROM.finditer(text):
                    name, tail = m.group(1), m.group(2)
                    line = "%s:%d" % (rel, text[: m.start()].count("\n") + 1)
                    if TS_WRITE_CALL.search(tail):
                        add(writes, name, line)
                    else:
                        add(reads, name, line)
    return reads, writes


async def db_facts(conn) -> tuple[set[str], dict[str, list[str]]]:
    """Live table names, and DB-side writers (functions/triggers) per table."""
    # ONLY real tables ('r' ordinary, 'p' partitioned, 'f' foreign). Views and
    # matviews are deliberately excluded: nothing writes a view, you write its
    # base tables, so "view has no writer" is always a false positive. The
    # first run of this script emitted 41 findings, most of them v_*/mv_*
    # noise. A matview that is never REFRESHed is a real problem, but it is a
    # different check (staleness, not orphanhood) -- see the mv refresh audit.
    rows = await conn.fetch(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind IN ('r','p','f')"
    )
    live = {r[0] for r in rows}

    # Functions whose body writes a table, AND that something actually calls.
    # A function nothing calls is not a writer -- that distinction is what
    # separated the real findings from the false ones during the manual sweep.
    fns = await conn.fetch(
        "SELECT p.proname, p.prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' AND p.prosrc IS NOT NULL"
    )
    called: set[str] = set()
    all_src = " ".join((f["prosrc"] or "") for f in fns)
    trg = await conn.fetch(
        "SELECT p.proname FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid WHERE NOT t.tgisinternal"
    )
    cron_cmds = ""
    try:
        cj = await conn.fetch("SELECT command FROM cron.job WHERE active")
        cron_cmds = " ".join((c[0] or "") for c in cj)
    except Exception:
        pass
    for f in fns:
        n = f["proname"]
        if n in all_src.replace(n, "", 1) or n in cron_cmds:
            called.add(n)
    called |= {t[0] for t in trg}

    db_writers: dict[str, list[str]] = {}
    for f in fns:
        src = f["prosrc"] or ""
        for m in PY_WRITE.finditer(src):
            tbl = m.group(2).lower()
            tag = "fn:%s%s" % (f["proname"], "" if f["proname"] in called else " (UNCALLED)")
            db_writers.setdefault(tbl, [])
            if tag not in db_writers[tbl]:
                db_writers[tbl].append(tag)

    # pg_cron jobs that run raw SQL are writers too. Without this, the rollup
    # tables (market_hits_daily, price_prediction_daily -- millions of rows,
    # populated by cron 39/40) show up as orphans, which is plainly wrong and
    # would train you to ignore the report.
    try:
        cj = await conn.fetch("SELECT jobname, command FROM cron.job WHERE active")
        for j in cj:
            for m in PY_WRITE.finditer(j["command"] or ""):
                tbl = m.group(2).lower()
                tag = "cron:%s" % j["jobname"]
                db_writers.setdefault(tbl, [])
                if tag not in db_writers[tbl]:
                    db_writers[tbl].append(tag)
    except Exception:
        pass
    return live, db_writers


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 when findings exist")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    # Two-phase mode. The code scan needs the FULL repo (server + src + app) but
    # no DB; the DB half needs a DSN but not the frontend source. On EC2 only
    # the backend is deployed, so scanning there would silently miss every
    # frontend-read orphan -- which is exactly how `portfolio_values` and
    # `user_category_ownership` stayed hidden. Scan locally, resolve remotely.
    ap.add_argument("--scan-only", action="store_true",
                    help="emit code references as JSON and exit; no DB needed")
    ap.add_argument("--refs", metavar="FILE",
                    help="load code references from a --scan-only dump instead of scanning")
    args = ap.parse_args()

    if args.refs:
        blob = json.loads(Path(args.refs).read_text())
        reads = {k: set(v) for k, v in blob["reads"].items()}
        writes = {k: set(v) for k, v in blob["writes"].items()}
    else:
        reads, writes = scan_code()

    if args.scan_only:
        print(json.dumps({
            "reads": {k: sorted(v) for k, v in reads.items()},
            "writes": {k: sorted(v) for k, v in writes.items()},
        }, indent=2))
        return 0

    if asyncpg is None:
        print("audit_orphan_tables: asyncpg not installed - run the DB phase where it is "
              "(e.g. --scan-only here, --refs there). Skipping (advisory).")
        return 0

    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("audit_orphan_tables: no DB_DSN_DIRECT/DB_DSN set - skipping (advisory).")
        return 0
    conn = await asyncpg.connect(dsn)
    try:
        live, db_writers = await db_facts(conn)
        findings = []
        for tbl in sorted(live):
            if tbl in ALLOWLIST:
                continue
            r, w = reads.get(tbl, set()), writes.get(tbl, set())
            if not r:
                continue  # nothing reads it -> not a broken feature, just unused
            dbw = db_writers.get(tbl, [])
            live_dbw = [x for x in dbw if "UNCALLED" not in x]
            if w or live_dbw:
                continue
            # Ask whether the table EXISTS before counting it. The table
            # names here are harvested from source, and a name that survives
            # only in a comment (`deal_ratings`, dropped with the Deal Desk on
            # 2026-08-09, still named in a comment in p2p_offers_router.py)
            # produced `SELECT COUNT(*) FROM public."deal_ratings"` every run.
            # The `except` swallowed it locally, but Postgres still logged an
            # ERROR the watchdog then reported as a rejected write — a probe
            # manufacturing the alarm it is meant to detect. `to_regclass`
            # returns NULL instead of raising, and keeps "missing" (None)
            # distinguishable from "empty" (0), which is the rule this repo
            # already applies to `[]` vs `None`.
            n = None
            if await conn.fetchval("SELECT to_regclass($1) IS NOT NULL",
                                   'public."%s"' % tbl):
                try:
                    n = await conn.fetchval('SELECT COUNT(*) FROM public."%s"' % tbl)
                except Exception:
                    n = None
            # Confidence. A table with rows was written by SOMETHING even if
            # this script can't see what (a seed script, a migration, a manual
            # backfill) -- that's worth a look but it is not proof of a dead
            # feature. Zero rows AND no discoverable writer is the real signal,
            # and it is the shape every confirmed bug had.
            findings.append({
                "table": tbl,
                "rows": n,
                "confidence": "HIGH" if n == 0 else "LOW",
                "readers": sorted(r)[:4],
                "reader_count": len(r),
                "uncalled_db_writers": dbw,
            })
        findings.sort(key=lambda f: (f["confidence"] != "HIGH", -f["reader_count"]))
    finally:
        await conn.close()

    if args.json:
        print(json.dumps({"findings": findings}, indent=2))
    else:
        print("=" * 72)
        print("ORPHAN TABLE AUDIT (advisory) - tables READ by code, written by nothing")
        print("=" * 72)
        if not findings:
            print("\n  No findings. Every table the code reads has a writer.\n")
        for f in findings:
            print("\n  [%s] %s  (%s rows)" % (f["confidence"], f["table"], f["rows"]))
            print("    read from %d place(s):" % f["reader_count"])
            for r in f["readers"]:
                print("      %s" % r)
            if f["uncalled_db_writers"]:
                print("    DB writers exist but nothing calls them: %s"
                      % ", ".join(f["uncalled_db_writers"]))
        hi = sum(1 for f in findings if f["confidence"] == "HIGH")
        print("\n  %d finding(s): %d HIGH (0 rows + no writer), %d LOW (has rows,"
              " writer not discoverable). Allowlisted: %d.\n"
              % (len(findings), hi, len(findings) - hi, len(ALLOWLIST)))

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
