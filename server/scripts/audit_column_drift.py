#!/usr/bin/env python3
"""
ADVISORY audit: columns the code writes but never reads, or reads but never
writes -- especially near-identically-named siblings on the same table.

Why this exists
---------------
`audit_orphan_tables.py` catches whole tables that are read and never written.
Three separate bugs on 2026-07-24 lived one level down: the table was fine, but
the writer and the readers disagreed about WHICH COLUMN.

  * add-manual wrote `purchase_price_eur`; the analytics cost-basis series
    (trends_and_deepdive_router), the value-saved banner (value_summary_router)
    and the dossier agent all read `purchase_price`. Result: the Cost Basis
    card could never populate, and the app discarded the acquisition price it
    had just asked the user for.
  * add-manual wrote `purchased_at`; the CSV export reads `purchase_date`.
  * both add paths wrote `title`; every canonical reader keys on `name`. That
    one blanked the Home portfolio (fixed in f9195fe).

None of these throw. A SELECT of an unwritten column returns NULL, and the
readers all have `?? 0` / `|| fallback` defaults, so the feature renders empty
rather than failing. Same silent-degrade shape as every other finding.

Signal
------
For each live table, classify every column reference in code as read or write,
then flag:
  * WRITE-ONLY  columns (written, never read)  -- data going nowhere
  * READ-ONLY   columns (read, never written)  -- feature starved of input
and pair them up when two such columns on the SAME table have similar names.
The pairing is what turns a boring inventory into an actionable finding.

Rows are counted so you can tell "nobody has used it yet" from "actively
diverging": a READ-ONLY column with 0 non-null values on a populated table is
the strong signal.

ADVISORY ONLY: always exits 0.

Usage (two-phase, same rationale as audit_orphan_tables.py -- the code scan
needs the full repo incl. src/+app/, the resolution needs the DB):
    python3 scripts/audit_column_drift.py --scan-only > refs.json   # dev box
    python3 scripts/audit_column_drift.py --refs refs.json          # on EC2
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import re
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[2]
CODE_ROOTS = [REPO / "server" / "app", REPO / "server" / "workers", REPO / "src", REPO / "app"]
CODE_SUFFIXES = {".py", ".ts", ".tsx"}

# Columns that are structurally uninteresting -- flagging them is pure noise.
BORING = {
    "id", "created_at", "updated_at", "deleted_at", "user_id", "owner",
    "inserted_at", "modified_at",
}

# Tables to skip entirely (huge, machine-written, or not user-facing).
SKIP_TABLES = {"market_hits", "price_history", "price_predictions", "demand_signals"}

# A write looks like `col=` / `col:` in an INSERT/UPDATE/object literal, or the
# column appearing in an INSERT column list. Reads are any other mention.
WRITE_CTX = re.compile(
    r"(INSERT\s+INTO[\s\S]{0,400}?\)|UPDATE[\s\S]{0,200}?SET[\s\S]{0,400}?(?:WHERE|$))",
    re.IGNORECASE,
)


def scan_code(columns_by_table: dict[str, set[str]] | None = None):
    """Return (reads, writes) keyed by bare column name -> {'path:line'}.

    Column names are matched bare (not table-qualified) because in practice the
    same name means the same thing across this codebase, and qualifying every
    reference would need a real SQL parser for marginal benefit.
    """
    reads: dict[str, set[str]] = {}
    writes: dict[str, set[str]] = {}
    interesting: set[str] = set()
    if columns_by_table:
        for cols in columns_by_table.values():
            interesting |= cols
    interesting -= BORING

    def add(bucket, name, where):
        bucket.setdefault(name, set()).add(where)

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

            write_spans = [m.span() for m in WRITE_CTX.finditer(text)]

            def in_write_span(pos: int) -> bool:
                return any(a <= pos < b for a, b in write_spans)

            for col in (interesting or set()):
                # word-boundary match, plus the JS object-literal form `col:`
                for m in re.finditer(r"\b%s\b" % re.escape(col), text):
                    pos = m.start()
                    line = "%s:%d" % (rel, text[:pos].count("\n") + 1)
                    after = text[m.end():m.end() + 3]
                    is_assign = after.lstrip().startswith(("=", ":")) and not after.lstrip().startswith("==")
                    if in_write_span(pos) or is_assign:
                        add(writes, col, line)
                    else:
                        add(reads, col, line)
    return reads, writes


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-only", action="store_true")
    ap.add_argument("--refs", metavar="FILE")
    # The scan needs to know which column names exist, which normally needs the
    # DB -- but the scan must run on the dev box (only place with src/+app/).
    # --dump-columns on EC2 produces this file; --columns consumes it locally.
    ap.add_argument("--dump-columns", action="store_true",
                    help="emit {table: [columns]} as JSON and exit (run where the DSN is)")
    ap.add_argument("--columns", metavar="FILE",
                    help="load the column list from --dump-columns instead of querying")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-similarity", type=float, default=0.6,
                    help="name-similarity threshold for pairing drifted siblings")
    args = ap.parse_args()

    # The scan needs to know which column names exist, which needs the DB. In
    # --scan-only mode we accept a column list dumped alongside the refs.
    if args.refs:
        blob = json.loads(Path(args.refs).read_text())
        reads = {k: set(v) for k, v in blob["reads"].items()}
        writes = {k: set(v) for k, v in blob["writes"].items()}
        columns_by_table = {k: set(v) for k, v in blob["columns_by_table"].items()}
    elif args.columns:
        columns_by_table = {k: set(v) for k, v in json.loads(Path(args.columns).read_text()).items()}
        reads, writes = scan_code(columns_by_table)
    else:
        if asyncpg is None:
            print("audit_column_drift: asyncpg needed to enumerate columns. "
                  "Use --dump-columns on the DB host, then --columns here.")
            return 0
        dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
        if not dsn:
            print("audit_column_drift: no DSN - skipping (advisory).")
            return 0
        conn = await asyncpg.connect(dsn)
        rows = await conn.fetch("""
            SELECT c.table_name, c.column_name
              FROM information_schema.columns c
              JOIN pg_class pc ON pc.relname = c.table_name
              JOIN pg_namespace n ON n.oid = pc.relnamespace AND n.nspname = 'public'
             WHERE c.table_schema = 'public' AND pc.relkind IN ('r','p')
        """)
        await conn.close()
        columns_by_table = {}
        for r in rows:
            columns_by_table.setdefault(r["table_name"], set()).add(r["column_name"])
        if args.dump_columns:
            print(json.dumps({k: sorted(v) for k, v in columns_by_table.items()}, indent=2))
            return 0
        reads, writes = scan_code(columns_by_table)

    if args.scan_only:
        print(json.dumps({
            "reads": {k: sorted(v) for k, v in reads.items()},
            "writes": {k: sorted(v) for k, v in writes.items()},
            "columns_by_table": {k: sorted(v) for k, v in columns_by_table.items()},
        }, indent=2))
        return 0

    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if asyncpg is None or not dsn:
        print("audit_column_drift: DB phase needs asyncpg + a DSN - skipping (advisory).")
        return 0

    conn = await asyncpg.connect(dsn)
    findings = []
    try:
        for table, cols in sorted(columns_by_table.items()):
            if table in SKIP_TABLES:
                continue
            usable = sorted(c for c in cols if c not in BORING)
            read_only = [c for c in usable if c in reads and c not in writes]
            write_only = [c for c in usable if c in writes and c not in reads]
            if not read_only or not write_only:
                continue
            try:
                total = await conn.fetchval('SELECT COUNT(*) FROM public."%s"' % table)
            except Exception:
                continue
            if not total:
                continue  # empty table: orphan audit's job, not this one
            for ro in read_only:
                best, score = None, 0.0
                for wo in write_only:
                    s = difflib.SequenceMatcher(None, ro, wo).ratio()
                    if s > score:
                        best, score = wo, s
                if not best or score < args.min_similarity:
                    continue
                try:
                    ro_n = await conn.fetchval('SELECT COUNT(*) FROM public."%s" WHERE "%s" IS NOT NULL' % (table, ro))
                    wo_n = await conn.fetchval('SELECT COUNT(*) FROM public."%s" WHERE "%s" IS NOT NULL' % (table, best))
                except Exception:
                    continue
                # DRIFT means the writer is filling the OTHER column. That
                # requires wo_n > 0, and until 2026-08-26 this line asked only
                # `ro_n == 0`, so a pair where NEITHER column is written
                # reported as HIGH — and the watchdog rendered it with the
                # sentence "a column the code READS is entirely NULL while a
                # similarly-named one IS WRITTEN", which was simply false for
                # that pair.
                #
                # The instance: market_hits.seller_rating (read) /
                # seller_score (written), 0 and 0 non-null out of 3,073,177
                # rows. No INSERT in server/ lists either column; the "reader"
                # is a key in Firecrawl's extraction JSON schema and the
                # "writer" is a field on a Pydantic RESPONSE model. Nothing was
                # drifting, nothing was starved, and it paged HIGH every day
                # from 2026-08-22 — the false-alarm pattern docs/WATCHDOG.md
                # is repeatedly warned about.
                #
                # Both-dead is still worth saying once, so it is reported —
                # just not as drift, and not at HIGH.
                if ro_n == 0 and wo_n > 0:
                    confidence = "HIGH"      # starved reader, live writer
                elif ro_n == 0 and wo_n == 0:
                    confidence = "DEAD_PAIR"  # neither side is written: not drift
                else:
                    confidence = "LOW"
                findings.append({
                    "table": table, "rows": total,
                    "read_only_column": ro, "read_only_nonnull": ro_n,
                    "write_only_column": best, "write_only_nonnull": wo_n,
                    "similarity": round(score, 2),
                    "readers": sorted(reads.get(ro, []))[:3],
                    "writers": sorted(writes.get(best, []))[:3],
                    "confidence": confidence,
                })
    finally:
        await conn.close()

    findings.sort(key=lambda f: (f["confidence"] != "HIGH", -f["similarity"]))

    if args.json:
        print(json.dumps({"findings": findings}, indent=2))
    else:
        print("=" * 74)
        print("COLUMN DRIFT AUDIT (advisory) - readers and writers on different columns")
        print("=" * 74)
        for f in findings:
            print("\n  [%s] %s (%d rows)" % (f["confidence"], f["table"], f["rows"]))
            print("      code READS   %-24s (%d non-null)" % (f["read_only_column"], f["read_only_nonnull"]))
            print("      code WRITES  %-24s (%d non-null)   similarity %.2f"
                  % (f["write_only_column"], f["write_only_nonnull"], f["similarity"]))
            for r in f["readers"]:
                print("        reader: %s" % r)
            for w in f["writers"]:
                print("        writer: %s" % w)
        hi = sum(1 for f in findings if f["confidence"] == "HIGH")
        dead = sum(1 for f in findings if f["confidence"] == "DEAD_PAIR")
        print("\n  %d finding(s): %d HIGH (read column NULL, write column "
              "populated), %d DEAD_PAIR (neither column written - not drift), "
              "%d LOW.\n" % (len(findings), hi, dead, len(findings) - hi - dead))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
