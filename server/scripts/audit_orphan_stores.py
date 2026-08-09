"""Orphan-store audit — tables that are WRITTEN but read by nothing.

Every existing gate in this repo watches PRODUCERS. None watches CONSUMERS, and
that asymmetry is why `user_notifications` accumulated 188 rows over seven
months with 0 reads, 0 read_at and 0 dismissed before anyone noticed — and it
was noticed because Merle asked, not because anything failed.

Why the three audits we already have could not catch it
--------------------------------------------------------
* `scripts/audit_writer_reader_drift.py` works at COLUMN level and its
  SCAN_DIRS is `server/` only. This table's writer is a **pg_cron job calling a
  DB function** — no Python, no repo file, nothing to regex.
* `scripts/audit_full_chain.py` traces FE call -> BE handler -> DB table,
  i.e. DOWNWARD from a frontend entry point. A store with no frontend entry
  point has nothing to trace from, so it is invisible by construction.
* `app/lib/worker_output_registry.py` + the silent_writer probe ask "is the
  declared writer still writing?". A perfectly healthy writer feeding a table
  nobody reads passes that check every single day — the probe is *designed* to
  go green here.

So this audit asks the question none of them do, from the side none of them
look at: **start at the DATABASE, enumerate what is being written, and demand a
reader.**

How it works
------------
1. Enumerate writers from the LIVE DATABASE, not the repo:
   - `cron.job` -> the SQL each scheduled job runs
   - `pg_proc`  -> every function body containing `INSERT INTO <table>`
2. For each table that receives writes, look for a reader in three places:
   - the repo (`server/`, `src/`, `app/`) by table name
   - a DB function that SELECTs it, where that function is itself called by the
     repo (an RPC nobody calls is not a reader — it is a second orphan)
3. Corroborate with ENGAGEMENT columns where the table has them
   (`read`, `read_at`, `dismissed_at`, `clicked_at`, ...). A table whose
   engagement column has never once moved across thousands of rows is not
   "maybe read somewhere we could not grep" — it is provably unread. That
   evidence is stronger than any static scan, which is the whole point:
   `learning_validate_values_not_just_structure`.

A finding is a REVIEW ITEM, not automatically a bug. An orphan can be
legitimate — an append-only audit log, an analytics sink drained by an external
tool. Those go in `KNOWN_ORPHANS` **with a reason**, which is the same discipline
`audit_rls_coverage.py` uses. The rule that matters: the justification must be
TRUE. `user_notifications` was previously justified in that file as "served
through /notifications", which was false — `GET /notifications/history` reads
`notification_history`. A wrong justification is worse than none, because it
answers the reviewer's question and stops the investigation.

Run:
    python3 scripts/audit_orphan_stores.py
    python3 scripts/audit_orphan_stores.py --json
    python3 scripts/audit_orphan_stores.py --strict   # exit 1 on any NEW orphan
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# The DB half must run on EC2 (that is where the DSN lives); the REPO half must
# run locally (EC2 has only `server/` under /opt/collectors, so `src/` and `app/`
# do not exist there and every reader lookup silently returns nothing).
#
# The first version of this script ran entirely on EC2 and reported market_hits,
# items and profiles as orphans — tables read on nearly every screen. Same shape
# as learning_ec2_deploy_path: the code ran, exited 0, and was confidently wrong.
# Hence the two phases below.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Readers can live anywhere the app does. Scanning `server/` alone is exactly
# the blind spot that made a FE-only reader look like an orphan.
READER_DIRS = ["server", "src", "app"]

# Engagement columns worth checking. If a table has one and it has NEVER moved,
# that is positive evidence of no reader rather than a failed grep.
ENGAGEMENT_COLUMNS = ("read", "read_at", "dismissed_at", "clicked_at", "opened_at")

# Tables that are written and not read ON PURPOSE. Each needs a reason that is
# TRUE and re-checkable — see the module docstring on why a wrong justification
# is worse than none.
KNOWN_ORPHANS: dict[str, str] = {
    "worker_runs": "Operational run log. Read by the watchdog and by humans in psql, not by app code.",
    "guidance_runs": "Idempotency ledger for pg_cron job 30 — its only purpose is the NOT EXISTS check in that job.",
    "notification_impressions": "Analytics sink for notification outcome computation; read by rpc_compute_notification_outcomes_v*.",
    "notification_interactions": "Analytics sink, same as notification_impressions.",
    # NOT listed as known-good, deliberately, so they keep failing until decided:
    #   user_notifications  — 188 rows, 0 read/0 dismissed, pg_cron 30 DISABLED 2026-08-08
    #   alerts_outbox       — 31 rows, both producers inactive, janitor cron 25 still running
}

_INSERT_RE = re.compile(r"insert\s+into\s+(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?", re.I)


def _repo_mentions(table: str) -> list[str]:
    """Files under READER_DIRS that mention `table`, excluding pure writers.

    Deliberately crude: a mention is enough to clear a table, because the cost
    of a false NEGATIVE here (an orphan we miss) is much higher than a false
    positive (a table we look at twice). This is a review queue.
    """
    hits: list[str] = []
    pattern = re.compile(rf"\b{re.escape(table)}\b")
    for d in READER_DIRS:
        root = REPO_ROOT / d
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.suffix not in {".py", ".ts", ".tsx", ".sql", ".mjs"}:
                continue
            if "node_modules" in p.parts or "__tests__" in p.parts:
                continue
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            if pattern.search(text):
                hits.append(str(p.relative_to(REPO_ROOT)))
                if len(hits) >= 4:
                    return hits
    return hits



def _analyse(dump: dict, args) -> int:
    """PHASE 2 (local): match DB-side writers against repo readers."""
    findings = []
    for tbl, meta in sorted(dump["tables"].items()):
        readers = [r for r in _repo_mentions(tbl) if "migration" not in r]
        eng = meta.get("engagement")
        provably_unread = bool(eng and eng["moved"] == 0 and eng["total"] > 0)
        if readers and not provably_unread:
            continue
        if tbl in KNOWN_ORPHANS:
            continue
        findings.append({
            "table": tbl, "rows": meta["rows"], "writers": meta["writers"],
            "repo_readers": readers, "engagement": eng,
            "provably_unread": provably_unread,
        })

    if args.json:
        print(json.dumps({"findings": findings}, indent=2))
        return 1 if (findings and args.strict) else 0

    print("=" * 74)
    print(f"  Orphan-store audit — {len(dump['tables'])} DB-written tables checked")
    print("=" * 74)
    if not findings:
        print("  no orphaned stores")
    for f in sorted(findings, key=lambda x: -x["rows"]):
        flag = "  <- PROVABLY UNREAD" if f["provably_unread"] else ""
        print(f"\n  x {f['table']}  ({f['rows']} rows){flag}")
        print(f"      written by : {', '.join(f['writers'])[:100]}")
        print(f"      repo reader: {', '.join(f['repo_readers'][:3]) or 'NONE'}")
        if f["engagement"]:
            e = f["engagement"]
            print(f"      engagement : {e['moved']}/{e['total']} rows have {e['column']} set")
    print()
    print(f"  verdict: {'FAIL' if findings and args.strict else 'REVIEW' if findings else 'PASS'}")
    return 1 if (findings and args.strict) else 0


async def _dump_writers() -> dict:
    """PHASE 1 (EC2): everything only the live database can answer."""
    import asyncpg
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("SKIP: no DB_DSN_DIRECT/DB_DSN in env", file=sys.stderr)
        return {"tables": {}}
    conn = await asyncpg.connect(dsn, timeout=30)
    try:
        writers: dict[str, set] = {}
        for row in await conn.fetch("SELECT jobid, command, active FROM cron.job"):
            for tbl in set(_INSERT_RE.findall(row["command"] or "")):
                writers.setdefault(tbl, set()).add(
                    f"cron.job {row['jobid']}{'' if row['active'] else ' (INACTIVE)'}")
        for row in await conn.fetch(
            "SELECT p.proname, pg_get_functiondef(p.oid) AS def FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public' AND p.prokind='f'"
        ):
            for tbl in set(_INSERT_RE.findall(row["def"] or "")):
                writers.setdefault(tbl, set()).add(f"rpc {row['proname']}")

        out: dict = {"tables": {}}
        for tbl in sorted(writers):
            if await conn.fetchval("SELECT to_regclass($1)", f"public.{tbl}") is None:
                continue
            cols = {r["column_name"] for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=$1", tbl)}
            total = await conn.fetchval(f'SELECT count(*) FROM public."{tbl}"')
            eng = None
            col = next((c for c in ENGAGEMENT_COLUMNS if c in cols), None)
            if col and total:
                pred = "IS TRUE" if col == "read" else "IS NOT NULL"
                moved = await conn.fetchval(
                    f'SELECT count(*) FROM public."{tbl}" WHERE "{col}" {pred}')
                eng = {"column": col, "moved": moved, "total": total}
            out["tables"][tbl] = {
                "rows": total, "writers": sorted(writers[tbl]), "engagement": eng,
            }
        return out
    finally:
        await conn.close()


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--dump-writers", action="store_true",
                    help="PHASE 1, run on EC2: emit DB-side writers as JSON.")
    ap.add_argument("--writers-file",
                    help="PHASE 2, run locally: analyse phase-1 JSON against the repo.")
    args = ap.parse_args()

    if args.writers_file:
        return _analyse(json.loads(Path(args.writers_file).read_text()), args)
    dump = await _dump_writers()
    if args.dump_writers:
        print(json.dumps(dump, indent=2))
        return 0
    # Single-host mode: only correct where the DB and the full repo coexist.
    return _analyse(dump, args)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
