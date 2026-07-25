#!/usr/bin/env python3
"""
Production watchdog — one JSON report of what users actually did, what is
healthy, and what is silently broken.

Why this exists
---------------
The 2026-07-24/25 audit found ~14 features that were fully built and silently
dead. Every one had the same shape: a writer and a reader that were never
connected, plus a construct that turns "not connected" into an empty result
instead of an error (bare `except: pass`, Pydantic/Zod dropping undeclared
fields, a CHECK constraint narrower than the code, a LEFT JOIN yielding NULL).
Nothing ever went red, so a dead feature was indistinguishable from an unused
one. This report exists to make that distinction mechanical and daily.

It answers three questions:
  1. ACTIVITY  — what did users actually do in the window?
  2. HEALTHY   — which loops are demonstrably working (writer AND reader)?
  3. BUGS      — what is silently failing right now?

Each finding carries a `link` (Supabase dashboard / GitHub source) and a
`verify` string you can paste to confirm it yourself. Nothing here mutates
anything: it is read-only by construction.

Usage:
    python3 scripts/watchdog.py                     # JSON to stdout
    python3 scripts/watchdog.py --out /tmp/wd.json  # write to a file
    python3 scripts/watchdog.py --hours 168         # 7-day window
    python3 scripts/watchdog.py --summary           # human-readable digest
    python3 scripts/watchdog.py --telegram          # page if severity>=high
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import asyncpg
except ImportError:
    print(json.dumps({"error": "asyncpg not installed"}))
    sys.exit(0)

PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF") or (
    re.sub(r"^https://([a-z0-9]+)\.supabase\.co.*$", r"\1", os.getenv("SUPABASE_URL", ""))
    if os.getenv("SUPABASE_URL") else ""
)
REPO = "https://github.com/CcollectAI/collectai-app/blob/main"
SERVER_ROOT = Path(__file__).resolve().parents[1]

# Known orphan-table backlog as of 2026-07-25. The watchdog pages only when this
# GROWS — the existing 12 are unfinished/unwired features tracked separately, and
# a daily alarm on a known backlog trains you to ignore the channel.
ORPHAN_HIGH_BASELINE = 12


def tbl_link(table: str) -> str:
    """Supabase table-editor deep link."""
    if not PROJECT_REF:
        return ""
    return "https://supabase.com/dashboard/project/%s/editor?schema=public&table=%s" % (PROJECT_REF, table)


def sql_link() -> str:
    return "https://supabase.com/dashboard/project/%s/sql/new" % PROJECT_REF if PROJECT_REF else ""


def src_link(path: str, line: int | None = None) -> str:
    return "%s/%s%s" % (REPO, path, "#L%d" % line if line else "")


# ---------------------------------------------------------------------------
# 1. ACTIVITY — what users did
# ---------------------------------------------------------------------------

async def collect_activity(c, hours: int) -> dict:
    since = "now() - interval '%d hours'" % hours
    out: dict = {"window_hours": hours}

    async def scalar(sql, default=0):
        try:
            return await c.fetchval(sql)
        except Exception:
            return default

    out["users"] = {
        "total": await scalar("SELECT COUNT(*) FROM auth.users"),
        "with_a_profile_name": await scalar(
            "SELECT COUNT(*) FROM profiles WHERE COALESCE(NULLIF(display_name,''), NULLIF(username,'')) IS NOT NULL"),
        "signed_up_in_window": await scalar("SELECT COUNT(*) FROM auth.users WHERE created_at > %s" % since),
        "link": tbl_link("profiles"),
    }

    # Demand signals are the richest record of intent. 26 types after the
    # 2026-07-25 constraint fix; before it, 18 of them were rejected outright.
    signals = []
    try:
        rows = await c.fetch(
            "SELECT signal_type, COUNT(*) n, MAX(created_at) last FROM demand_signals "
            "WHERE created_at > %s GROUP BY 1 ORDER BY n DESC" % since)
        signals = [{"type": r["signal_type"], "count": r["n"], "last": str(r["last"])} for r in rows]
    except Exception:
        pass
    out["demand_signals"] = {
        "in_window": signals,
        "total_all_time": await scalar("SELECT COUNT(*) FROM demand_signals"),
        "distinct_types_all_time": await scalar("SELECT COUNT(DISTINCT signal_type) FROM demand_signals"),
        "link": tbl_link("demand_signals"),
    }

    out["collection"] = {
        "items_total": await scalar("SELECT COUNT(*) FROM items"),
        "items_added_in_window": await scalar("SELECT COUNT(*) FROM items WHERE created_at > %s" % since),
        "items_with_canonical_key": await scalar("SELECT COUNT(*) FROM items WHERE canonical_key IS NOT NULL"),
        "items_with_purchase_price": await scalar("SELECT COUNT(*) FROM items WHERE purchase_price IS NOT NULL"),
        "link": tbl_link("items"),
    }

    out["engagement"] = {
        "watchlist_items": await scalar("SELECT COUNT(*) FROM watchlist_items"),
        "category_follows": await scalar("SELECT COUNT(*) FROM user_category_follows"),
        "chat_messages_in_window": await scalar("SELECT COUNT(*) FROM chat_messages_v1 WHERE created_at > %s" % since),
        "price_alerts": await scalar("SELECT COUNT(*) FROM user_price_alerts"),
        "pushes_sent_in_window": await scalar("SELECT COUNT(*) FROM notification_history WHERE created_at > %s" % since),
    }

    # Product-gap signal: searches that returned nothing.
    try:
        rows = await c.fetch(
            "SELECT COALESCE(query_text, item_key, '(none)') q, COUNT(*) n FROM demand_signals "
            "WHERE signal_type='no_results_search' AND created_at > %s GROUP BY 1 ORDER BY n DESC LIMIT 10" % since)
        out["searches_with_no_results"] = [{"query": r["q"], "count": r["n"]} for r in rows]
    except Exception:
        out["searches_with_no_results"] = []

    return out


# ---------------------------------------------------------------------------
# 2/3. HEALTH + BUGS
# ---------------------------------------------------------------------------

async def collect_findings(c, hours: int) -> tuple[list, list]:
    since = "now() - interval '%d hours'" % hours
    healthy: list = []
    bugs: list = []

    def bug(sev, title, detail, link="", verify="", fix=""):
        bugs.append({"severity": sev, "title": title, "detail": detail,
                     "link": link, "verify": verify, "suggested_fix": fix})

    # --- CHECK constraints narrower than the code (bit twice on 2026-07-25) ---
    try:
        dm = (SERVER_ROOT / "app" / "features" / "data_moat.py").read_text(errors="ignore")
        m = re.search(r"valid_types\s*=\s*\{(.*?)\n\s*\}", dm, re.S)
        code_types = set(re.findall(r'"([a-z_]+)"', m.group(1))) if m else set()
        d = await c.fetchval(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='demand_signals_signal_type_check'")
        db_types = set(re.findall(r"'([a-z_]+)'::text", d or ""))
        missing = sorted(code_types - db_types)
        if missing:
            bug("high", "demand_signals CHECK is narrower than data_moat.valid_types",
                "Postgres rejects these signal types on every insert and record_demand_signal() "
                "swallows the failure: %s" % ", ".join(missing),
                src_link("server/app/features/data_moat.py"),
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='demand_signals_signal_type_check';",
                "ALTER TABLE demand_signals DROP CONSTRAINT demand_signals_signal_type_check; then re-add including the missing values")
        elif code_types:
            healthy.append({"check": "demand_signals CHECK mirrors data_moat.valid_types",
                            "detail": "%d types allowed, matches code" % len(db_types)})
    except Exception as e:
        bug("info", "constraint-vs-code check could not run", str(e)[:200])

    # --- tables the code reads that nothing writes ---
    try:
        rows = await c.fetch("""
            SELECT c.relname tbl, (SELECT COUNT(*) FROM pg_policy p WHERE p.polrelid=c.oid) pols
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity
              AND NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid)
        """)
        for r in rows:
            if r["tbl"] in ("subscription_events",):   # server-only by design
                continue
            bug("medium", "RLS enabled with no policy: %s" % r["tbl"],
                "Users can neither read nor write this table; any feature on it is silently empty.",
                tbl_link(r["tbl"]),
                "SELECT relrowsecurity FROM pg_class WHERE relname='%s';" % r["tbl"])
    except Exception:
        pass

    # --- worker health ---
    try:
        rows = await c.fetch("""
            SELECT worker_name,
                   COUNT(*) FILTER (WHERE status='ok') ok,
                   COUNT(*) FILTER (WHERE status<>'ok') err,
                   MAX(started_at) last_run
            FROM worker_runs WHERE started_at > %s
            GROUP BY worker_name ORDER BY err DESC, worker_name""" % since)
        for r in rows:
            total = r["ok"] + r["err"]
            if r["err"] and total and r["err"] / total >= 0.5:
                bug("high", "worker failing: %s" % r["worker_name"],
                    "%d errors / %d runs in %dh" % (r["err"], total, hours),
                    tbl_link("worker_runs"),
                    "SELECT status, metadata, started_at FROM worker_runs WHERE worker_name='%s' ORDER BY started_at DESC LIMIT 5;" % r["worker_name"])
            elif r["ok"]:
                healthy.append({"check": "worker %s" % r["worker_name"],
                                "detail": "%d ok / %d err" % (r["ok"], r["err"])})
    except Exception:
        pass

    # --- pg_cron health ---
    try:
        rows = await c.fetch("""
            SELECT j.jobname,
                   COUNT(d.*) FILTER (WHERE d.status='succeeded') ok,
                   COUNT(d.*) FILTER (WHERE d.status<>'succeeded') bad
            FROM cron.job j
            LEFT JOIN cron.job_run_details d ON d.jobid=j.jobid AND d.start_time > %s
            WHERE j.active GROUP BY j.jobname""" % since)
        for r in rows:
            tot = r["ok"] + r["bad"]
            if r["bad"] and tot and r["bad"] / tot >= 0.5:
                bug("high", "cron job failing: %s" % r["jobname"],
                    "%d failures / %d runs" % (r["bad"], tot), sql_link(),
                    "SELECT status, return_message, start_time FROM cron.job_run_details d JOIN cron.job j USING (jobid) WHERE j.jobname='%s' ORDER BY start_time DESC LIMIT 5;" % r["jobname"])
    except Exception:
        pass

    # --- ingest freshness: the pipeline that feeds every price ---
    try:
        newest = await c.fetchval("SELECT MAX(seen_at) FROM market_hits")
        age_h = await c.fetchval("SELECT EXTRACT(EPOCH FROM (now() - MAX(seen_at)))/3600 FROM market_hits")
        if age_h is not None and age_h > 6:
            bug("high", "market_hits ingest stalled",
                "newest row is %.1f h old (%s)" % (age_h, newest), tbl_link("market_hits"),
                "SELECT MAX(seen_at) FROM market_hits;")
        else:
            healthy.append({"check": "market_hits ingest", "detail": "newest row %.1f h old" % (age_h or 0)})
    except Exception:
        pass

    # --- partition runway: writes fail (or land in _default) without next month ---
    try:
        for parent in ("market_hits", "price_predictions", "price_history"):
            parts = await c.fetch(
                "SELECT inhrelid::regclass::text p FROM pg_inherits WHERE inhparent=$1::regclass", "public." + parent)
            months = sorted(re.search(r"y(\d{4})m(\d{2})", r["p"]).group(0)
                            for r in parts if re.search(r"y(\d{4})m(\d{2})", r["p"]))
            nxt = (datetime.now(timezone.utc).replace(day=1))
            nxt = nxt.replace(year=nxt.year + 1, month=1) if nxt.month == 12 else nxt.replace(month=nxt.month + 1)
            want = "y%04dm%02d" % (nxt.year, nxt.month)
            if want not in months:
                bug("medium", "no partition for next month on %s" % parent,
                    "missing %s — rows will fall into the _default partition, which retention cannot drop" % want,
                    sql_link(), "SELECT inhrelid::regclass FROM pg_inherits WHERE inhparent='public.%s'::regclass;" % parent)
            else:
                healthy.append({"check": "%s partition runway" % parent, "detail": "%s exists" % want})
    except Exception:
        pass

    # --- dead text-key joins (the 2026-07-25 four-month bug) ---
    # An empty join is a VALID result: it raises nothing, logs nothing, and is
    # byte-identical to a user who owns nothing. No structural check can see it.
    # This is the only check that compares the VALUES on each side.
    try:
        import subprocess, json as _json
        r = subprocess.run(
            ["/opt/collectors/.venv/bin/python",
             str(SERVER_ROOT / "scripts" / "audit_key_overlap.py"), "--json", "--sample", "400"],
            capture_output=True, timeout=600, cwd=str(SERVER_ROOT))
        rep = _json.loads(r.stdout.decode() or "{}")
        dead = [e for e in rep.get("report", [])
                if e.get("status") == "DEAD" and not e.get("expect_partial")]
        for e in dead:
            bug("high", "dead key join: %s" % e["pair"],
                "The two sides of this join share NO values, so every query using it returns "
                "[] forever without erroring. Check the key FORMATS, not the schema.",
                src_link("server/scripts/audit_key_overlap.py"),
                "python3 scripts/audit_key_overlap.py --sample 400",
                "Compare sample values on each side; a namespaced-vs-bare mismatch is the usual cause")
        if not dead and rep.get("report"):
            healthy.append({"check": "text-key joins",
                            "detail": "%d declared joins, no unexplained dead ones" % len(rep["report"])})
    except Exception as e:
        bug("info", "key-overlap audit could not run", str(e)[:200])

    # --- orphan tables: read by code, written by nothing ---
    # Advisory backlog, so this reports a COUNT and only escalates when it grows.
    # A dead-feature backlog you can't see is how 12 of these accumulated.
    try:
        import subprocess, json as _json
        r = subprocess.run(
            ["/opt/collectors/.venv/bin/python",
             str(SERVER_ROOT / "scripts" / "audit_orphan_tables.py"), "--json"],
            capture_output=True, timeout=600, cwd=str(SERVER_ROOT))
        f = _json.loads(r.stdout.decode() or "{}").get("findings", [])
        high = [x for x in f if x.get("severity") == "HIGH" or x.get("confidence") == "HIGH"]
        if len(high) > ORPHAN_HIGH_BASELINE:
            bug("medium", "orphan-table HIGH findings rose to %d (baseline %d)"
                % (len(high), ORPHAN_HIGH_BASELINE),
                "Tables read by code that nothing writes — each is a feature that cannot populate: %s"
                % ", ".join(sorted(x.get("table", "?") for x in high)[:12]),
                src_link("server/scripts/audit_orphan_tables.py"),
                "python3 scripts/audit_orphan_tables.py",
                "Repoint the reader to the real table, or finish/remove the feature")
        else:
            healthy.append({"check": "orphan tables",
                            "detail": "%d HIGH (baseline %d)" % (len(high), ORPHAN_HIGH_BASELINE)})
    except Exception as e:
        bug("info", "orphan-table audit could not run", str(e)[:200])

    # --- mv_supply_trend: adding a refresh cron ZEROES it ---
    # Its definition filters snapshot_at > now() - 90 days, and supply_snapshots
    # stopped being written 2026-05-04 (DEAL_DISCOVERY_ENABLED=false). The stale
    # matview is currently the ONLY thing keeping scan scarcity alive. Warn as
    # the 90-day horizon approaches so nobody "fixes" it by adding a refresh.
    try:
        row = await c.fetchrow("""
            SELECT (SELECT count(*) FROM public.mv_supply_trend) AS rows,
                   (SELECT max(snapshot_at) FROM public.supply_snapshots) AS last_write
        """)
        if row and row["rows"] and row["last_write"]:
            age_days = (datetime.now(timezone.utc) - row["last_write"]).days
            if age_days > 75:
                bug("medium", "mv_supply_trend is %d days from going empty" % max(0, 90 - age_days),
                    "supply_snapshots last written %d days ago; the matview filters to a 90-day "
                    "window. DO NOT add a refresh cron — refreshing it now returns 0 rows and kills "
                    "scan scarcity. Re-enable the writer (DEAL_DISCOVERY_ENABLED) or retire the feature."
                    % age_days,
                    src_link("server/workers/deal_discovery_worker.py"),
                    "SELECT max(snapshot_at) FROM supply_snapshots;",
                    "Re-enable the supply_snapshots writer, or drop mv_supply_trend and its readers")
            else:
                healthy.append({"check": "mv_supply_trend",
                                "detail": "%d rows, source %d days old" % (row["rows"], age_days)})
    except Exception:
        pass

    # --- pricing coverage canary ---
    # The end-to-end assertion the four-month bug needed: can a catalog item
    # actually reach a price? Coverage silently collapsing to ~0 is exactly what
    # nobody noticed. Thresholds are deliberately far below current levels so
    # this pages on a COLLAPSE, not on normal drift.
    try:
        canaries = [("mtg", 80.0), ("pokemon", 80.0), ("yugioh", 60.0)]
        for cat, floor in canaries:
            total = await c.fetchval(
                "SELECT count(*) FROM category_items WHERE category=$1", cat)
            if not total:
                continue
            priced = await c.fetchval(
                """
                SELECT count(*) FROM category_items ci
                WHERE ci.category = $1
                  AND (EXISTS (SELECT 1 FROM price_predictions p
                               WHERE p.item_ref = ci.category||':'||ci.item_key
                                 AND p.generated_at >= now() - interval '30 days')
                       OR EXISTS (SELECT 1 FROM catalog_price_refs x
                                  WHERE x.category = ci.category AND x.item_key = ci.item_key))
                """, cat)
            pct = 100.0 * priced / total
            if pct < floor:
                bug("high", "pricing coverage collapsed for %s: %.1f%%" % (cat, pct),
                    "%d of %d catalog rows can reach a price (floor %.0f%%). Users in this "
                    "category will see 0.00 everywhere while every endpoint still returns 200."
                    % (priced, total, floor),
                    src_link("server/pipelines/build_catalog_price_crosswalk.py"),
                    "python3 scripts/audit_key_overlap.py",
                    "Rebuild the crosswalk, or check whether items.canonical_ref resolution broke")
            else:
                healthy.append({"check": "pricing coverage %s" % cat,
                                "detail": "%.1f%% of %d catalog rows priceable" % (pct, total)})
    except Exception as e:
        bug("info", "pricing coverage canary could not run", str(e)[:200])

    # --- schema.lock staleness: a restart with a stale lock hard-downs the API ---
    try:
        import subprocess
        r = subprocess.run(["/opt/collectors/.venv/bin/python", "/opt/collectors/scripts/preflight_schema_lock.py"],
                           capture_output=True, timeout=180)
        if r.returncode != 0:
            bug("high", "schema.lock is stale",
                "preflight_schema_lock FAILS — the next bake restart will hard-down the API. "
                "Any DDL stales it, not just partition drops.",
                src_link("scripts/regen_schema_lock.py"),
                "/opt/collectors/.venv/bin/python /opt/collectors/scripts/preflight_schema_lock.py",
                "python3 /opt/collectors/scripts/regen_schema_lock.py")
        else:
            healthy.append({"check": "schema.lock", "detail": "matches live schema"})
    except Exception:
        pass

    return healthy, bugs


# ---------------------------------------------------------------------------
# LOGS — the application journal, where silent failures leave their only trace
# ---------------------------------------------------------------------------

# Noise that is expected and would otherwise drown the signal.
_LOG_IGNORE = re.compile(
    r"Found credentials|urllib3|botocore|httpx|Connected to DB pool|"
    r"Starting worker|cycle complete|GET /healthz", re.I)

# Collapse variable parts so the same message groups into one bucket.
_NORMALISE = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "<uuid>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\S*"), "<ts>"),
    (re.compile(r"\b\d+\.\d+\b"), "<float>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"'[^']{40,}'"), "'<long>'"),
]


def collect_logs(hours: int, limit: int = 12) -> dict:
    """Bucket the bake journal by severity and recurring message.

    Reads systemd's journal for collectai-bake.service. This is where the
    swallowed failures surface: `[data_moat] Failed to record demand signal`
    was visible here for weeks while the feature looked merely 'unused'.
    """
    import subprocess
    out: dict = {"source": "journalctl -u collectai-bake.service",
                 "window_hours": hours, "errors": [], "warnings": [], "tracebacks": 0}
    try:
        r = subprocess.run(
            ["sudo", "journalctl", "-u", "collectai-bake.service",
             "--since", "%d hours ago" % hours, "--no-pager", "-o", "cat"],
            capture_output=True, text=True, timeout=180)
        lines = (r.stdout or "").splitlines()
    except Exception as e:
        out["error"] = str(e)[:200]
        return out

    out["lines_scanned"] = len(lines)
    out["tracebacks"] = sum(1 for ln in lines if "Traceback (most recent call last)" in ln)

    buckets: dict[str, dict] = {}
    for ln in lines:
        if not ln.strip() or _LOG_IGNORE.search(ln):
            continue
        low = ln.lower()
        if "error" in low or "exception" in low or "failed" in low or "critical" in low:
            sev = "error"
        elif "warn" in low:
            sev = "warning"
        else:
            continue
        key = ln
        for rx, rep in _NORMALISE:
            key = rx.sub(rep, key)
        key = key[:180]
        b = buckets.setdefault(key, {"severity": sev, "count": 0, "sample": ln[:300]})
        b["count"] += 1

    ranked = sorted(buckets.items(), key=lambda kv: -kv[1]["count"])
    for pattern, b in ranked:
        entry = {"pattern": pattern, "count": b["count"], "sample": b["sample"]}
        if b["severity"] == "error" and len(out["errors"]) < limit:
            out["errors"].append(entry)
        elif b["severity"] == "warning" and len(out["warnings"]) < limit:
            out["warnings"].append(entry)

    out["distinct_error_patterns"] = sum(1 for _, b in ranked if b["severity"] == "error")
    out["distinct_warning_patterns"] = sum(1 for _, b in ranked if b["severity"] == "warning")
    out["how_to_read_more"] = (
        "ssh collectai 'sudo journalctl -u collectai-bake.service --since \"%dh ago\" --no-pager | grep -i error'" % hours)
    out["supabase_postgres_logs"] = (
        "https://supabase.com/dashboard/project/%s/logs/postgres-logs" % PROJECT_REF if PROJECT_REF else "")
    return out


# ---------------------------------------------------------------------------
# SUPABASE LOGS — Postgres / API / Auth, via the Management API
# ---------------------------------------------------------------------------

def _sb_token() -> str:
    """Management API PAT. The CLI stores one at ~/.supabase/access-token;
    SUPABASE_ACCESS_TOKEN in .env is NOT the same thing (it 401s)."""
    for p in (Path.home() / ".supabase" / "access-token",
              Path("/home/ubuntu/.supabase/access-token")):
        try:
            t = p.read_text().strip()
            if t.startswith("sbp_"):
                return t
        except Exception:
            continue
    t = os.getenv("SUPABASE_ACCESS_TOKEN", "")
    return t if t.startswith("sbp_") else ""


def collect_supabase_logs(hours: int) -> dict:
    """Pull Postgres errors, API status codes and auth failures from Logflare.

    This is the layer nothing else sees. The EC2 journal only shows what the
    bake service logs; anything the DB rejects, or any request that fails at
    PostgREST/GoTrue, never reaches it. On 2026-07-25 this surfaced 597
    catalog-ingest constraint violations per DAY that were invisible everywhere
    else.
    """
    import subprocess, urllib.parse
    from datetime import timedelta
    out: dict = {"available": False}
    tok = _sb_token()
    if not tok or not PROJECT_REF:
        out["error"] = ("no Supabase Management PAT found (looked in "
                        "~/.supabase/access-token and $SUPABASE_ACCESS_TOKEN). "
                        "Create one at https://supabase.com/dashboard/account/tokens")
        return out

    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def query(sql: str):
        url = ("https://api.supabase.com/v1/projects/%s/analytics/endpoints/logs.all"
               "?sql=%s&iso_timestamp_start=%s&iso_timestamp_end=%s"
               % (PROJECT_REF, urllib.parse.quote(sql), start, end))
        try:
            r = subprocess.run(["curl", "-s", "--max-time", "45",
                                "-H", "Authorization: Bearer %s" % tok, url],
                               capture_output=True, text=True, timeout=60)
            return (json.loads(r.stdout or "{}") or {}).get("result") or []
        except Exception:
            return []

    out["available"] = True
    out["window"] = {"start": start, "end": end}

    out["postgres_errors"] = [
        {"message": (r.get("msg") or "")[:220], "count": r.get("n")}
        for r in query(
            'select event_message as msg, count(*) as n from postgres_logs '
            'cross join unnest(metadata) m cross join unnest(m.parsed) p '
            'where p.error_severity = "ERROR" group by msg order by n desc limit 10')
    ]
    out["api_status_codes"] = [
        {"code": r.get("code"), "count": r.get("n")}
        for r in query(
            'select cast(r.status_code as string) as code, count(*) as n from edge_logs '
            'cross join unnest(metadata) m cross join unnest(m.response) r '
            'group by code order by n desc')
    ]
    out["api_failing_paths"] = [
        {"path": r.get("path"), "code": r.get("code"), "count": r.get("n")}
        for r in query(
            'select rq.path as path, cast(rs.status_code as string) as code, count(*) as n '
            'from edge_logs cross join unnest(metadata) m '
            'cross join unnest(m.request) rq cross join unnest(m.response) rs '
            'where rs.status_code >= 400 group by path, code order by n desc limit 10')
    ]
    errs = sum(e["count"] or 0 for e in out["postgres_errors"])
    codes = {c["code"]: c["count"] for c in out["api_status_codes"]}
    out["totals"] = {
        "postgres_errors": errs,
        "api_5xx": sum(v for k, v in codes.items() if str(k).startswith("5")),
        "api_4xx": sum(v for k, v in codes.items() if str(k).startswith("4")),
        "api_ok": sum(v for k, v in codes.items() if str(k).startswith("2")),
    }
    out["links"] = {
        "postgres_logs": "https://supabase.com/dashboard/project/%s/logs/postgres-logs" % PROJECT_REF,
        "api_logs": "https://supabase.com/dashboard/project/%s/logs/edge-logs" % PROJECT_REF,
        "auth_logs": "https://supabase.com/dashboard/project/%s/logs/auth-logs" % PROJECT_REF,
    }
    return out


# ---------------------------------------------------------------------------
# PAYING CUSTOMERS — what the people who pay actually use
# ---------------------------------------------------------------------------

async def collect_plan_usage(c, hours: int) -> dict:
    since = "now() - interval '%d hours'" % hours
    out: dict = {}
    try:
        rows = await c.fetch(
            "SELECT plan, status, COUNT(*) n FROM subscriptions GROUP BY 1,2 ORDER BY n DESC")
        out["subscriptions"] = [{"plan": r["plan"], "status": r["status"], "count": r["n"]} for r in rows]
        out["paying_users"] = await c.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE plan <> 'free' AND status='active'")
    except Exception:
        out["subscriptions"], out["paying_users"] = [], 0

    # What paying users DO vs what free users do — the gap tells you which
    # paid features justify the price and which are never touched.
    try:
        rows = await c.fetch("""
            SELECT COALESCE(s.plan,'free') AS plan, d.signal_type, COUNT(*) n
            FROM demand_signals d
            LEFT JOIN subscriptions s ON s.user_id = d.user_id AND s.status='active'
            WHERE d.created_at > %s
            GROUP BY 1,2 ORDER BY n DESC LIMIT 25""" % since)
        out["signals_by_plan"] = [
            {"plan": r["plan"], "signal": r["signal_type"], "count": r["n"]} for r in rows]
    except Exception:
        out["signals_by_plan"] = []

    # Pro-only surfaces with zero usage are either undiscoverable or broken.
    try:
        rows = await c.fetch("""
            SELECT COALESCE(s.plan,'free') AS plan,
                   COUNT(DISTINCT i.user_id) users_adding,
                   COUNT(*) items
            FROM items i
            LEFT JOIN subscriptions s ON s.user_id = i.user_id AND s.status='active'
            GROUP BY 1 ORDER BY items DESC""")
        out["collection_by_plan"] = [
            {"plan": r["plan"], "users_adding": r["users_adding"], "items": r["items"]} for r in rows]
    except Exception:
        out["collection_by_plan"] = []
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--out")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--telegram", action="store_true", help="page when a high-severity bug is present")
    ap.add_argument("--digest", action="store_true",
                    help="always send the full summary to Telegram, even when green")
    args = ap.parse_args()

    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print(json.dumps({"error": "no DSN"})); return 0

    c = await asyncpg.connect(dsn, timeout=60)
    try:
        activity = await collect_activity(c, args.hours)
        healthy, bugs = await collect_findings(c, args.hours)
        logs = collect_logs(args.hours)
        sblogs = collect_supabase_logs(args.hours)
        plans = await collect_plan_usage(c, args.hours)
    finally:
        await c.close()

    for e in (sblogs.get("postgres_errors") or [])[:5]:
        if (e.get("count") or 0) >= 20:
            bugs.append({"severity": "high", "title": "Postgres rejecting writes repeatedly",
                         "detail": "%dx in %dh: %s" % (e["count"], args.hours, e["message"][:170]),
                         "link": (sblogs.get("links") or {}).get("postgres_logs", ""),
                         "verify": "Supabase > Logs > Postgres, filter error_severity=ERROR",
                         "suggested_fix": ""})
    if (sblogs.get("totals") or {}).get("api_5xx", 0) >= 10:
        bugs.append({"severity": "high", "title": "API returning 5xx",
                     "detail": "%d 5xx responses in %dh" % (sblogs["totals"]["api_5xx"], args.hours),
                     "link": (sblogs.get("links") or {}).get("api_logs", ""),
                     "verify": "Supabase > Logs > API", "suggested_fix": ""})

    # A single error repeating hundreds of times is a real incident, not noise.
    for e in logs.get("errors", []):
        if e["count"] >= 25:
            bugs.append({"severity": "high", "title": "recurring error in the bake journal",
                         "detail": "%d occurrences: %s" % (e["count"], e["sample"][:160]),
                         "link": "", "verify": logs.get("how_to_read_more", ""), "suggested_fix": ""})

    sev_rank = {"high": 0, "medium": 1, "info": 2}
    bugs.sort(key=lambda b: sev_rank.get(b["severity"], 3))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": args.hours,
        "dashboard": {"supabase_tables": tbl_link("items"), "sql_editor": sql_link(), "repo": REPO},
        "activity": activity,
        "logs": logs,
        "supabase_logs": sblogs,
        "paying_customers": plans,
        "what_went_well": healthy,
        "bugs": bugs,
        "counts": {"healthy": len(healthy),
                   "bugs_high": sum(1 for b in bugs if b["severity"] == "high"),
                   "bugs_medium": sum(1 for b in bugs if b["severity"] == "medium")},
    }

    blob = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(blob)
        print("wrote %s (%d bugs, %d healthy)" % (args.out, len(bugs), len(healthy)))
    if args.summary or not args.out:
        if args.summary:
            a = report["activity"]
            print("=" * 68)
            print("WATCHDOG — last %dh — %s" % (args.hours, report["generated_at"][:19]))
            print("=" * 68)
            print("users %s (%s named) | items %s (+%s) | signals %s types"
                  % (a["users"]["total"], a["users"]["with_a_profile_name"],
                     a["collection"]["items_total"], a["collection"]["items_added_in_window"],
                     a["demand_signals"]["distinct_types_all_time"]))
            for s in a["demand_signals"]["in_window"][:8]:
                print("   %-30s %d" % (s["type"], s["count"]))
            lg = report["logs"]
            print("\nLOGS  %s lines | %d distinct error patterns, %d warning | %d tracebacks"
                  % (lg.get("lines_scanned", "?"), lg.get("distinct_error_patterns", 0),
                     lg.get("distinct_warning_patterns", 0), lg.get("tracebacks", 0)))
            for e in lg.get("errors", [])[:6]:
                print("   %5dx %s" % (e["count"], e["sample"][:110]))

            print("\nHEALTHY: %d checks" % len(healthy))
            print("BUGS: %d high, %d medium" % (report["counts"]["bugs_high"], report["counts"]["bugs_medium"]))
            for b in bugs:
                print("\n  [%s] %s" % (b["severity"].upper(), b["title"]))
                print("      %s" % b["detail"])
                if b["link"]: print("      link:   %s" % b["link"])
                if b["verify"]: print("      verify: %s" % b["verify"])
        else:
            print(blob)

    if args.digest:
        # Daily digest: always send, even when everything is green — a silent
        # watchdog is indistinguishable from a broken one, which is the exact
        # failure mode this whole report exists to catch.
        try:
            sys.path.insert(0, str(SERVER_ROOT))
            from app.lib.telegram_ops import send_ops_alert
            a = report["activity"]; lg = report["logs"]; cnt = report["counts"]

            def esc(s):
                return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            def a_href(url, text):
                return '<a href="%s">%s</a>' % (url, esc(text)) if url else esc(text)

            # Day-over-day: an absolute number means little; the delta is the
            # thing you actually react to.
            prev = {}
            try:
                yday = sorted(Path("/opt/collectors/logs").glob("watchdog-*.json"))[-2:]
                if len(yday) == 2:
                    prev = json.loads(yday[0].read_text())
            except Exception:
                pass

            def delta(cur, path, fmt="%+d"):
                try:
                    p = prev
                    for k in path:
                        p = p[k]
                    d = cur - p
                    return " (%s)" % (fmt % d) if d else ""
                except Exception:
                    return ""

            green = (cnt["bugs_high"] == 0 and cnt["bugs_medium"] == 0)
            title = ("✅ <b>Sparrow watchdog</b>" if green
                     else "⚠️ <b>Sparrow watchdog</b> — %d high, %d medium"
                          % (cnt["bugs_high"], cnt["bugs_medium"]))

            body = "last %dh · %s" % (args.hours, report["generated_at"][:16].replace("T", " "))

            body += "\n\n<b>\U0001f465 Users &amp; collection</b>"
            body += "\n<b>{:,}</b> users{} · {:,} with a name".format(
                a["users"]["total"], delta(a["users"]["total"], ["activity", "users", "total"]),
                a["users"]["with_a_profile_name"])
            body += "\n<b>{:,}</b> items{} · {:,} priced · {:,} with cost basis".format(
                a["collection"]["items_total"],
                delta(a["collection"]["items_total"], ["activity", "collection", "items_total"]),
                a["collection"]["items_with_canonical_key"],
                a["collection"]["items_with_purchase_price"])
            body += "\n" + a_href(a["collection"]["link"], "open items table")

            body += "\n\n<b>\U0001f4c8 What users did</b>"
            sig = a["demand_signals"]["in_window"]
            if sig:
                for s in sig[:8]:
                    body += "\n  {} — <b>{:,}</b>".format(esc(s["type"]), s["count"])
            else:
                # Empty window is normal pre-launch — say so, so it doesn't
                # read as a failure.
                body += "\n  none in this window (%s signals all-time, %s types)" % (
                    a["demand_signals"]["total_all_time"], a["demand_signals"]["distinct_types_all_time"])
            gaps = a.get("searches_with_no_results") or []
            if gaps:
                body += "\n  <i>searches with no results:</i> " + ", ".join(
                    "%s (%d)" % (esc(g["query"])[:24], g["count"]) for g in gaps[:4])
            body += "\n" + a_href(a["demand_signals"]["link"], "open demand_signals")

            # Paying customers. The interesting number is not how many pay --
            # it is whether they DO anything. A paid plan with an empty
            # collection is a refund waiting to happen.
            pc = report.get("paying_customers") or {}
            if pc.get("subscriptions"):
                body += "\n\n<b>\U0001f4b3 Paying customers</b>"
                body += "\n" + " · ".join(
                    "%s %d" % (esc(s["plan"]), s["count"]) for s in pc["subscriptions"])
                by_plan = {p["plan"]: p for p in (pc.get("collection_by_plan") or [])}
                paid_items = sum(v["items"] for k, v in by_plan.items() if k != "free")
                if pc.get("paying_users") and paid_items == 0:
                    body += ("\n⚠️ <b>%d paying user(s) have added 0 items</b> — "
                             "they are paying and not using it" % pc["paying_users"])
                else:
                    for k, v in by_plan.items():
                        body += "\n  %s: %d items from %d user(s)" % (esc(k), v["items"], v["users_adding"])

            # Supabase logs: the layer the EC2 journal cannot see. Anything the
            # DB rejects or PostgREST/GoTrue fails never reaches the journal.
            sb = report.get("supabase_logs") or {}
            if sb.get("available"):
                t = sb.get("totals") or {}
                ok, e4, e5 = t.get("api_ok", 0), t.get("api_4xx", 0), t.get("api_5xx", 0)
                tot = ok + e4 + e5
                rate = (100.0 * (e4 + e5) / tot) if tot else 0.0
                body += "\n\n<b>\U0001f6f0 Supabase (API + DB)</b>"
                body += "\n<b>{:,}</b> requests".format(tot)
                body += "\n  {:,} succeeded".format(ok)
                body += "\n  <b>{:,}</b> client errors (4xx)".format(e4)
                body += "\n  <b>{:,}</b> server errors (5xx)".format(e5)
                body += "\n  <b>{:.1f}%</b> of all requests failed".format(rate)
                paths = (sb.get("api_failing_paths") or [])[:3]
                if paths:
                    body += "\n\n<b>Failing endpoints</b>"
                    for p in paths:
                        body += "\n  <b>{:,}</b> failed with {} — {}".format(
                            p["count"] or 0, esc(p["code"]), esc(p["path"]))
                body += "\n\n<b>{:,}</b> Postgres errors".format(t.get("postgres_errors", 0) or 0)
                for e in (sb.get("postgres_errors") or [])[:3]:
                    body += "\n  <b>{:,}</b> — {}".format(e["count"] or 0, esc(e["message"][:100]))
                links = sb.get("links") or {}
                body += "\n" + " · ".join(x for x in [
                    a_href(links.get("postgres_logs", ""), "pg logs"),
                    a_href(links.get("api_logs", ""), "api logs"),
                    a_href(links.get("auth_logs", ""), "auth logs")] if x)
            else:
                body += "\n\n<b>\U0001f6f0 Supabase logs</b>\n<i>%s</i>" % esc(
                    (sb.get("error") or "unavailable")[:180])

            body += "\n\n<b>\U0001f4dc App journal (EC2)</b>"
            body += "\n{:,} lines · {:,} error patterns · {:,} tracebacks".format(
                lg.get("lines_scanned", 0) or 0, lg.get("distinct_error_patterns", 0) or 0,
                lg.get("tracebacks", 0) or 0)
            for e in lg.get("errors", [])[:2]:
                body += "\n  <b>{:,}</b> — {}".format(e["count"] or 0, esc(e["sample"][:100]))

            body += "\n\n<b>✅ Healthy: %d checks</b>" % cnt["healthy"]
            if green:
                body += "\n<b>No issues found.</b>"
            else:
                # Collapse repeated titles (several Postgres rejections share
                # one) so the list reads as distinct problems, not repetition.
                seen: dict = {}
                for b in bugs:
                    seen.setdefault(b["title"], []).append(b)
                body += "\n\n<b>⚠️ Issues — worst first</b>"
                for i, (title, group) in enumerate(list(seen.items())[:6], 1):
                    b = group[0]
                    body += "\n\n<b>%d. [%s] %s</b>" % (i, esc(b["severity"]), esc(title))
                    for g in group[:3]:
                        body += "\n%s" % esc(g["detail"][:150])
                    if b.get("link"):
                        body += "\n" + a_href(b["link"], "inspect")
                    if b.get("verify"):
                        body += "\n<code>%s</code>" % esc(b["verify"][:150])
                body += "\n\n<b>\U0001f3af Start with #1.</b>"

            body += "\n\n<b>\U0001f517 Dashboards</b>\n%s · %s" % (
                a_href(sql_link(), "SQL editor"),
                a_href(lg.get("supabase_postgres_logs", ""), "Postgres logs"))
            if args.out:
                body += "\nfull JSON: <code>%s</code>" % esc(args.out)

            # Green days go through silently; only real findings buzz.
            await send_ops_alert(body[:3800], title=title, silent=green)
            print("digest sent to telegram")
        except Exception as e:
            print("telegram digest failed: %s" % e, file=sys.stderr)

    if args.telegram and report["counts"]["bugs_high"]:
        try:
            sys.path.insert(0, str(SERVER_ROOT))
            from app.lib.telegram_ops import send_ops_alert
            lines = ["\U0001f6a8 Watchdog: %d high-severity finding(s)" % report["counts"]["bugs_high"]]
            for b in bugs:
                if b["severity"] == "high":
                    lines.append("• %s — %s" % (b["title"], b["detail"][:120]))
            await send_ops_alert("\n".join(lines))
        except Exception as e:
            print("telegram page failed: %s" % e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
