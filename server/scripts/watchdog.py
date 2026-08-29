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
    python3 scripts/watchdog.py --hours 24          # window; keep <=24, Logflare
                                                    # answers longer ones PARTIALLY
    python3 scripts/watchdog.py --summary           # human-readable digest
    python3 scripts/watchdog.py --telegram          # page if severity>=high
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import re
import socket
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
# GROWS — the remainder are unfinished/unwired features tracked separately, and a
# daily alarm on a known backlog trains you to ignore the channel. Dropped 12->10
# when event_follows_v1 and user_challenge_progress were allowlisted as deliberate
# product decisions; to 9 when quickscan_history fell off after value_summary was
# repointed to predict_sessions; and to 7 when `images` (a docstring false
# positive) and `taxonomy_registry` (works via code fallback) were allowlisted.
# The remaining 7 are two unbuilt feature clusters — sets/set_items/set_registry
# and listings/deal_ratings/offer_evidence(+collections) — awaiting a product call.
ORPHAN_HIGH_BASELINE = 7


def tbl_link(table: str) -> str:
    """Supabase table-editor deep link."""
    if not PROJECT_REF:
        return ""
    return "https://supabase.com/dashboard/project/%s/editor?schema=public&table=%s" % (PROJECT_REF, table)


_TRUNC_NOTE = "\n\n… digest truncated — full JSON on the box."


def _trim_html(body: str, limit: int) -> str:
    """Trim an HTML digest to `limit` chars WITHOUT splitting a tag.

    `body[:3800]` was a raw character cut on MARKUP. When it landed between
    `<code>` and `</code>`, Telegram rejected the entire message:

        400 ... can't parse entities: Can't find end tag corresponding to
        start tag "code"

    and the whole daily report was lost — silently (the send is inside a
    `try/except` that prints to stderr), and preferentially on the days the
    report was LONGEST, i.e. the days with the most bugs. A monitor whose
    delivery fails in proportion to how much it has to say is worse than no
    monitor, which is the same failure this file's own docstring warns about
    for `[]`-vs-`None`.

    Cut on a line boundary, then close whatever tags are still open.
    """
    if len(body) <= limit:
        return body
    budget = limit - len(_TRUNC_NOTE)
    kept: list[str] = []
    used = 0
    for line in body.split("\n"):
        if used + len(line) + 1 > budget:
            break
        kept.append(line)
        used += len(line) + 1
    out = "\n".join(kept)
    # Balance the inline tags this digest emits. `"</code>".count("<code")` is
    # 0 because the char after `<` is `/`, so these counts are open-minus-close.
    for tag in ("code", "b", "a"):
        unclosed = out.count("<%s" % tag) - out.count("</%s>" % tag)
        out += ("</%s>" % tag) * max(0, unclosed)
    return out + _TRUNC_NOTE


def sql_link() -> str:
    return "https://supabase.com/dashboard/project/%s/sql/new" % PROJECT_REF if PROJECT_REF else ""


def src_link(path: str, line: int | None = None) -> str:
    return "%s/%s%s" % (REPO, path, "#L%d" % line if line else "")


def serving_artifact_roots() -> list[Path]:
    """Candidate artifact roots, in the order model_loader tries them.

    Mirrors app/ml/model_loader.py::_artifacts_root so the watchdog inspects
    exactly what serving loads, rather than a path that merely looks right.
    """
    return [Path("/opt/collectors/server/artifacts"),
            Path.cwd() / "artifacts",
            Path(__file__).resolve().parents[1] / "artifacts"]


def serving_model_ages(roots: list[Path], now: datetime | None = None
                       ) -> list[tuple[str, int]]:
    """[(category, age_in_days)] for every resolvable `active` model.json.

    Returns [] when nothing is resolvable — the caller MUST treat that as
    "could not ask", never as "models are fresh". Module-level and
    now-injectable so it can be tested against real fixture trees; the same
    logic inline in the report body could only ever be tested by reading it.
    """
    root = next((r for r in roots if r.is_dir()), None)
    if root is None:
        return []
    now = now or datetime.now(timezone.utc)
    ages: list[tuple[str, int]] = []
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        active = cat_dir / "active"
        target = None
        # `active` is a symlink on the box, but preflight_models also accepts a
        # plain file containing the version name — accept both, or this reports
        # a false UNKNOWN on a box that is actually fine.
        if active.is_symlink() or active.is_dir():
            resolved = active.resolve()
            target = resolved if resolved.is_dir() else None
        elif active.is_file():
            try:
                cand = cat_dir / active.read_text().strip()
                target = cand if cand.is_dir() else None
            except Exception:
                target = None
        if target is None:
            continue
        mj = target / "model.json"
        if mj.is_file():
            fitted = datetime.fromtimestamp(mj.stat().st_mtime, timezone.utc)
            ages.append((cat_dir.name, (now - fitted).days))
    return ages


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

    @contextlib.contextmanager
    def guard(check_name: str, sev: str = "medium"):
        """Run a check; if it throws, SAY so instead of swallowing it.

        Every health check here was wrapped in `except Exception: pass`, so a
        renamed column or a revoked grant would delete the check from the
        report entirely — and a report with no finding is exactly what a
        healthy day looks like. This is the same failure the DAC7 section of
        docs/WATCHDOG.md calls out ("the check itself errors -> medium;
        reporting nothing must never look like all-clear"), which was applied
        to that one check and to none of the others.
        """
        try:
            yield
        except Exception as e:
            bug(sev, "%s check could not run" % check_name,
                "%s: %s" % (type(e).__name__, str(e)[:200]))

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
    with guard("RLS coverage"):
        rows = await c.fetch("""
            SELECT c.relname tbl, (SELECT COUNT(*) FROM pg_policy p WHERE p.polrelid=c.oid) pols
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity
              AND NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid)
        """)
        for r in rows:
            # Server-only by design. RLS-on with no policy denies ALL client
            # access, which is the intent for these — they are read through an
            # authed endpoint on the direct DSN, never through PostgREST, so
            # deny-all is defence in depth rather than a dead feature.
            #   dac7_seller_year -> GET /p2p/dac7/me (tax counters; a member must
            #   not be able to query other members' rows even by accident)
            #   notification_{impressions,interactions,outcomes} -> POST
            #   /notifications/feedback/{impression,interaction,outcome}.
            #   Verified 2026-08-12 rather than assumed: all three writers are
            #   `pool.acquire()` + raw INSERT in
            #   app/features/notification_feedback_router.py (lines 63-127), so
            #   every access is asyncpg on the direct DSN and PostgREST is never
            #   in the path. Nothing in the app or the RPCs reads them.
            #   Checked against the failure this doc records: the RLS
            #   justification list previously accepted "served through
            #   /notifications" for user_notifications, which read a DIFFERENT
            #   table. The claim to test is not "an endpoint exists" but "this
            #   table's own reader and writer bypass RLS".
            if r["tbl"] in ("subscription_events", "dac7_seller_year",
                            "notification_impressions", "notification_interactions",
                            "notification_outcomes"):
                continue
            bug("medium", "RLS enabled with no policy: %s" % r["tbl"],
                "Users can neither read nor write this table; any feature on it is silently empty.",
                tbl_link(r["tbl"]),
                "SELECT relrowsecurity FROM pg_class WHERE relname='%s';" % r["tbl"])

    # --- worker health ---
    #
    # Scoped to runs THIS machine recorded. `worker_runs` is a prod table on the
    # direct DSN, so a worker started by hand on a laptop writes into it too: on
    # 2026-08-12 five local runs each of calibration_worker and
    # partition_drop_worker (Darwin gaierror; no boto3) produced two `high`
    # findings while every run prod itself made was `ok`. Rows written before
    # metadata.host existed have no host and are counted as ours — a legacy row
    # must fail toward alerting, never toward silence.
    #
    # The detail carries the actual error, per this doc's own rule: a failing
    # worker must say WHY, not just that it failed. Had it done so, the two
    # findings above would have read "ModuleNotFoundError: No module named
    # 'boto3'" and been recognised as a laptop in one glance.
    try:
        host = socket.gethostname()
        rows = await c.fetch("""
            SELECT worker_name,
                   COUNT(*) FILTER (WHERE status='ok'  AND mine) ok,
                   COUNT(*) FILTER (WHERE status<>'ok' AND mine) err,
                   COUNT(*) FILTER (WHERE status<>'ok' AND NOT mine) foreign_err,
                   MAX(started_at) last_run,
                   (ARRAY_AGG(metadata->>'error_repr' ORDER BY started_at DESC)
                      FILTER (WHERE status<>'ok' AND mine))[1] last_err,
                   (ARRAY_AGG(DISTINCT metadata->>'host')
                      FILTER (WHERE status<>'ok' AND NOT mine)) foreign_hosts
            FROM (
              SELECT *, COALESCE(metadata->>'host', $1) = $1 AS mine
              FROM worker_runs WHERE started_at > %s
            ) w
            GROUP BY worker_name ORDER BY err DESC, worker_name""" % since, host)
        for r in rows:
            total = r["ok"] + r["err"]
            if r["err"] and total and r["err"] / total >= 0.5:
                bug("high", "worker failing: %s" % r["worker_name"],
                    "%d errors / %d runs in %dh — last error: %s"
                    % (r["err"], total, hours, r["last_err"] or "(no error_repr recorded)"),
                    tbl_link("worker_runs"),
                    "SELECT status, metadata, started_at FROM worker_runs WHERE worker_name='%s' ORDER BY started_at DESC LIMIT 5;" % r["worker_name"])
            elif r["ok"]:
                healthy.append({"check": "worker %s" % r["worker_name"],
                                "detail": "%d ok / %d err" % (r["ok"], r["err"])})
            # Named, never dropped: a run failing on someone's laptop is not a
            # prod incident, but silently discarding it is how a real second
            # host would go unnoticed.
            if r["foreign_err"]:
                bug("info", "worker %s failed on another host" % r["worker_name"],
                    "%d error run(s) recorded by %s, not by this server (%s). "
                    "Not counted toward the prod failure rate."
                    % (r["foreign_err"],
                       ", ".join([h for h in (r["foreign_hosts"] or []) if h]) or "an unnamed host",
                       host),
                    tbl_link("worker_runs"),
                    "SELECT started_at, status, metadata->>'host' host, metadata->>'error_repr' err FROM worker_runs WHERE worker_name='%s' ORDER BY started_at DESC LIMIT 10;" % r["worker_name"])
    except Exception as e:
        # This check going quiet must not read as "all workers healthy".
        bug("medium", "worker-health check could not run", str(e)[:200])

    # --- pg_cron health ---
    with guard("pg_cron health"):
        rows = await c.fetch("""
            SELECT j.jobname,
                   COUNT(d.*) FILTER (WHERE d.status='succeeded') ok,
                   COUNT(d.*) FILTER (WHERE d.status<>'succeeded') bad,
                   -- The reason, not just the count. "13 failures / 24 runs"
                   -- costs an SSH round trip to learn what every one of those
                   -- runs already recorded: "canceling statement due to
                   -- statement timeout".
                   (ARRAY_AGG(d.return_message ORDER BY d.start_time DESC)
                      FILTER (WHERE d.status<>'succeeded'))[1] last_msg
            FROM cron.job j
            LEFT JOIN cron.job_run_details d ON d.jobid=j.jobid AND d.start_time > %s
            WHERE j.active GROUP BY j.jobname""" % since)
        for r in rows:
            tot = r["ok"] + r["bad"]
            if r["bad"] and tot and r["bad"] / tot >= 0.5:
                bug("high", "cron job failing: %s" % r["jobname"],
                    "%d failures / %d runs — last message: %s"
                    % (r["bad"], tot,
                       " ".join((r["last_msg"] or "(none recorded)").split())[:200]),
                    sql_link(),
                    "SELECT status, return_message, start_time FROM cron.job_run_details d JOIN cron.job j USING (jobid) WHERE j.jobname='%s' ORDER BY start_time DESC LIMIT 5;" % r["jobname"])

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
            # Next month's partition is CREATED BY pg_cron job 32 on the 25th
            # ("0 2 25 * *"). Flagging its absence before then is a false alarm
            # that fires every day from the 1st to the 24th, on every partitioned
            # table — 24 days of daily noise a month, which is how a watchdog
            # gets ignored. Only complain once the job should already have run.
            #
            # `today` is the current month's partition and must exist NOW; that
            # is a real incident at any point in the month.
            today_part = "y%04dm%02d" % (datetime.now(timezone.utc).year,
                                         datetime.now(timezone.utc).month)
            day_of_month = datetime.now(timezone.utc).day
            PARTITION_CRON_DAY = 25

            if today_part not in months:
                bug("high", "no partition for the CURRENT month on %s" % parent,
                    "missing %s — rows are landing in the _default partition RIGHT NOW, "
                    "and retention cannot drop _default" % today_part,
                    sql_link(), "SELECT inhrelid::regclass FROM pg_inherits WHERE inhparent='public.%s'::regclass;" % parent)
            elif want not in months and day_of_month >= PARTITION_CRON_DAY:
                bug("medium", "no partition for next month on %s" % parent,
                    "missing %s and pg_cron job 32 (0 2 25 * *) should already have created it — "
                    "rows will fall into the _default partition, which retention cannot drop" % want,
                    sql_link(), "SELECT inhrelid::regclass FROM pg_inherits WHERE inhparent='public.%s'::regclass;" % parent)
            elif want not in months:
                healthy.append({
                    "check": "%s partition runway" % parent,
                    "detail": "%s present; %s due from pg_cron job 32 on the %dth"
                              % (today_part, want, PARTITION_CRON_DAY),
                })
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
        # EVERY category with a real catalogue, not a hand-kept list of three.
        # The hardcoded [mtg, pokemon, yugioh] could not see that lorcana
        # (6,967 rows), digimon (9,762) and one_piece_tcg (7,675) had fallen to
        # ZERO priceable rows after tcgcsv was 403-blocked on 2026-07-29 — the
        # single largest pricing outage to date, invisible to its own canary
        # because nobody had added those categories to the list. A monitor that
        # only watches what you remembered to name is not a monitor.
        no_source: list[tuple[str, int]] = []
        thin_source: list[tuple] = []
        FLOOR_DEFAULT = 60.0
        FLOOR_OVERRIDE = {"mtg": 80.0, "pokemon": 80.0}
        MIN_CATALOG_ROWS = 500
        canary_rows = await c.fetch(
            """
            SELECT category, count(*) AS n FROM category_items
            WHERE category IS NOT NULL
            GROUP BY category HAVING count(*) >= $1
            ORDER BY 2 DESC
            """,
            MIN_CATALOG_ROWS,
        )
        canaries = [
            (r["category"], FLOOR_OVERRIDE.get(r["category"], FLOOR_DEFAULT))
            for r in canary_rows
        ]
        SAMPLE = 300
        for cat, floor in canaries:
            total = await c.fetchval(
                "SELECT count(*) FROM category_items WHERE category=$1", cat)
            if not total:
                continue
            # SAMPLE, don't scan. The exhaustive version (EXISTS per catalog row
            # against a partitioned 3M-row table) ran for minutes on yugioh's
            # 38k rows and made the daily cron hammer the DB — a monitor that is
            # itself a load problem gets switched off. 300 rows is far more than
            # enough to detect a COLLAPSE, which is all this check is for.
            # STRATIFY BY source. An unordered `LIMIT n` returns the oldest
            # physical rows, which for any category that gained tcgcsv-derived
            # rows means sampling only the old seed rows — that reported yugioh
            # as "collapsed to 40.3%" when the real split is 88% seed / 100%
            # tcgcsv. Same unordered-LIMIT bias that produced a false DEAD in
            # audit_key_overlap; a canary that cries wolf gets muted, so weight
            # each source's rate by its share of the category.
            rows = await c.fetch(
                """
                SELECT source, count(*) AS n FROM category_items
                WHERE category = $1 GROUP BY source
                """, cat)
            priced = sampled = 0
            for sr in rows:
                src, n_src = sr["source"], sr["n"]
                took = min(n_src, max(1, SAMPLE // max(1, len(rows))))
                hit = await c.fetchval(
                    """
                    WITH s AS (
                        -- ORDER BY random(): a bare LIMIT returns the OLDEST
                        -- PHYSICAL ROWS, and stratifying by source did not fix
                        -- that — it just applied the same bias once per source.
                        -- Pokémon has one dominant source, so the canary kept
                        -- reading the same unpriceable head of the table and
                        -- reported 21.3% against a true 96.1%. A canary that
                        -- cries wolf on your healthiest category gets muted,
                        -- and then it cannot warn you about a real one.
                        SELECT category, item_key FROM category_items
                        WHERE category = $1 AND source IS NOT DISTINCT FROM $2
                        ORDER BY random() LIMIT $3
                    )
                    SELECT count(*) FROM s
                    WHERE EXISTS (SELECT 1 FROM price_predictions p
                                  WHERE p.item_ref = s.category||':'||s.item_key
                                    AND p.generated_at >= now() - interval '30 days')
                       OR EXISTS (SELECT 1 FROM catalog_price_refs x
                                  WHERE x.category = s.category AND x.item_key = s.item_key)
                    """, cat, src, took)
                # weight this stratum's rate by its true share of the category
                priced += (hit / took) * n_src if took else 0
                sampled += n_src
            pct = 100.0 * priced / sampled if sampled else 0.0
            if pct >= floor:
                healthy.append({"check": "pricing coverage %s" % cat,
                                "detail": "%.1f%% priceable of %d rows (source-stratified)" % (pct, sampled)})
                continue

            # BELOW FLOOR — but "broken" and "never had a source" are different
            # findings and must not page the same way. Valuation only consumes
            # SOLD comps (valuation_worker excludes is_listing), so the presence
            # of sold comps is what separates them:
            #
            #   sold now                  -> the pipeline is broken. HIGH.
            #   sold before, none now     -> the SOURCE died. HIGH, and the most
            #                                actionable alert this file can emit.
            #   never any sold            -> the known structural gap (eBay
            #                                sold_comps is stubbed). Collected
            #                                into ONE finding below, because 40
            #                                identical HIGHs a day for a
            #                                permanent condition is how a
            #                                monitor gets muted.
            sold_now = await c.fetchval(
                """
                SELECT count(*) FROM market_hits
                WHERE split_part(item_ref, ':', 1) = $1
                  AND NOT is_listing AND seen_at > now() - interval '30 days'
                """, cat) or 0
            sold_before = await c.fetchval(
                """
                SELECT count(*) FROM market_hits
                WHERE split_part(item_ref, ':', 1) = $1
                  AND NOT is_listing
                  AND seen_at BETWEEN now() - interval '90 days' AND now() - interval '30 days'
                """, cat) or 0
            # The discriminator is NOT `sold_now > 0`. That counted ROWS, so
            # one_piece_tcg — ONE sold comp against 7,675 catalogue rows —
            # landed in the same bucket as a real pipeline fault and was told
            # "the data is there and the catalogue cannot reach it". On
            # 2026-08-21 that produced FIVE false HIGHs out of eight, which is
            # the false-alarm pattern this file is repeatedly warned about.
            #
            # Measured that morning, distinct items with a sold comp vs items
            # actually priced: funko 60/60, retro_games 58/58, nintendo_merch
            # 32/32, retro_handhelds 4/4, one_piece_tcg 1/1. EVERY comp that
            # arrived was already used. Nothing was broken; there were simply
            # almost no comps.
            #
            # "The catalogue cannot reach the data" is only true when comps
            # arrive FOR CATALOGUE ROWS THAT STAY UNPRICED. Count that, and
            # nothing else. (Same window and definition of "priceable" as the
            # canary above, so the two numbers cannot disagree.)
            # Two numbers, one pass. They answer different questions and only
            # the first is a pipeline fault:
            #   orphaned  - comps land ON a catalogue row that stays unpriced
            #               -> the crosswalk is broken
            #   unmatched - comps land for a key with NO catalogue row at all
            #               -> the CATALOGUE is missing the item (yugioh: 13,838
            #                  of 14,054 on 2026-08-21), which is a sourcing or
            #                  keying question, not a broken crosswalk
            _cov = await c.fetchrow(
                """
                WITH sold AS (
                    SELECT DISTINCT split_part(item_ref, ':', 2) AS item_key
                    FROM market_hits
                    WHERE NOT is_listing
                      AND seen_at > now() - interval '30 days'
                      AND split_part(item_ref, ':', 1) = $1
                )
                SELECT
                  count(*) FILTER (
                    WHERE ci.item_key IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM catalog_price_refs x
                                       WHERE x.category = $1 AND x.item_key = s.item_key)
                      AND NOT EXISTS (SELECT 1 FROM price_predictions p
                                       WHERE p.item_ref = $1 || ':' || s.item_key
                                         AND p.generated_at >= now() - interval '30 days')
                  ) AS orphaned,
                  count(*) FILTER (WHERE ci.item_key IS NULL) AS unmatched
                FROM sold s
                LEFT JOIN category_items ci
                  ON ci.category = $1 AND ci.item_key = s.item_key
                """, cat)
            orphaned = (_cov["orphaned"] if _cov else 0) or 0
            unmatched = (_cov["unmatched"] if _cov else 0) or 0

            # Page only when the orphaned set is big enough to actually move
            # coverage: a handful of stragglers is normal churn between the
            # comp landing and the next valuation cycle.
            orphan_floor = max(50, int(0.01 * sampled))
            if orphaned >= orphan_floor:
                bug("high", "pricing coverage collapsed for %s: %.1f%%" % (cat, pct),
                    "%.0f of %d catalog rows can reach a price (floor %.0f%%), and %d catalogue "
                    "items have a SOLD COMP from the last 30 days yet are still unpriced. The data "
                    "is there and the catalogue cannot reach it — a keying or crosswalk fault, not "
                    "a sourcing one." % (priced, sampled, floor, orphaned),
                    src_link("server/pipelines/build_catalog_price_crosswalk.py"),
                    "python3 scripts/audit_key_overlap.py",
                    "Rebuild the crosswalk, or check whether items.canonical_ref resolution broke")
            elif sold_before > 0 and sold_now == 0:
                bug("high", "sold-comp source DIED for %s (%.1f%% priceable)" % (cat, pct),
                    "%d sold comps in the 30-90d window and ZERO in the last 30 days. The category "
                    "still collects listings, but valuation ignores listings, so every item here "
                    "has silently stopped being priced. This is a regression with a date, not a "
                    "standing gap." % sold_before,
                    src_link("server/app/agents/marketplace_routing.py"),
                    "SELECT provider, count(*) FILTER (WHERE NOT is_listing) FROM market_hits "
                    "WHERE item_ref LIKE '%s:%%%%' AND seen_at > now() - interval '90 days' "
                    "GROUP BY 1;" % cat,
                    "Find which provider stopped: a blocked adapter, an expired key, or a 403")
            elif sold_now > 0:
                # Comps arrive, and every one of them is already priced. The
                # pipeline is provably working; the volume is simply too thin
                # to lift coverage. Aggregated below, never paged.
                thin_source.append((cat, sampled, pct, unmatched))
            else:
                no_source.append((cat, sampled))
        # ONE finding for every category that has never had a sold comp, with
        # the totals — so the scale is visible without 40 separate pages.
        # Below floor, comps arriving, NOTHING orphaned — the pipeline works and
        # the volume is thin. One info line with the scale, never a page.
        if thin_source:
            names = ", ".join(
                "%s %.0f%% (%s)" % (c, p,
                                    ("%d comps for items not in the catalogue" % u) if u
                                    else "too few comps")
                for c, _n, p, u in sorted(thin_source, key=lambda t: t[2])[:8])
            bug("info",
                "%d categories are below the coverage floor with the crosswalk INTACT"
                % len(thin_source),
                "Every catalogue item that has a sold comp in these categories is already "
                "priced — zero orphaned items — so the crosswalk is working. Coverage is "
                "limited either by comps arriving for keys with no catalogue row, or by there "
                "being too few comps at all: %s. Previously these paged as \"coverage "
                "collapsed\", which was five false HIGHs out of eight on 2026-08-21." % names,
                src_link("server/app/agents/adapters/ebay_caller.py"),
                "See the orphaned-item query in the pricing coverage canary",
                "Same remedy as the no-sold-comp gap: more sold-comp sources")

        if no_source:
            total_rows = sum(n for _, n in no_source)
            names = ", ".join(c for c, _ in sorted(no_source, key=lambda t: -t[1])[:8])
            bug("medium",
                "%d categories have NO sold-comp source (%d catalog rows unpriceable)"
                % (len(no_source), total_rows),
                "Listings arrive for these, but valuation_worker excludes is_listing, so nothing "
                "is ever priced. Structural, not a regression: %s%s. Root cause is "
                "ebay_caller.sold_comps() returning [] — it needs eBay Marketplace Insights "
                "access. Reported as ONE finding on purpose; as one-per-category it drowned every "
                "other bug in this report."
                % (names, " and more" if len(no_source) > 8 else ""),
                src_link("server/app/agents/adapters/ebay_caller.py"),
                "SELECT split_part(item_ref,':',1) cat, count(*) FILTER (WHERE NOT is_listing) sold "
                "FROM market_hits WHERE seen_at > now() - interval '30 days' GROUP BY 1 ORDER BY 2;",
                "Apply for eBay Marketplace Insights, or label these as asking-price estimates")
    except Exception as e:
        bug("info", "pricing coverage canary could not run", str(e)[:200])

    # --- sold comps the valuation queue cannot see (2026-08-26) ---
    # The coverage canary above measures the OUTPUT (can a catalogue row reach
    # a price). This measures the INPUT, and the two failed to agree for eleven
    # days: lorcana had 5,420 sold comps, ZERO rows in price_predictions ever,
    # and the canary reported it as "a keying or crosswalk fault". It was not.
    #
    # valuation_worker.run_once() filters its queue with `price IS NOT NULL`
    # (mirroring the partial index idx_market_hits_valuation_queue) while the
    # value it actually uses is `COALESCE(price_eur, price)`. `price` is the
    # ORIGINAL-currency price and `price_eur` the EUR normalisation, so a
    # writer that fills only price_eur produces rows that are perfectly usable
    # and permanently invisible — processed=false forever, no error anywhere.
    # `scripts/load_lorcana_direct.py` was such a writer.
    #
    # This is the enumerator for that class, not a lorcana check: it asks the
    # queue's own predicate of the whole table and reports whatever it finds.
    # Fixing the reader instead would de-align the partial index and put a
    # 3M-row seq scan on the 30s pooler cap (see the query's own comment), and
    # docs/DATA_SCALING_PLAN.md §6 rule 1 is "default state = refuse to add an
    # index" — so the gate lives here and the fix belongs at the writer, which
    # is what §10 "Writer bugs hide in INSERT column lists" already prescribes.
    with guard("valuation queue visibility"):
        blind = await c.fetch(
            """
            SELECT split_part(item_ref, ':', 1) AS category,
                   provider,
                   count(*) AS rows,
                   min(seen_at) AS oldest
              FROM public.market_hits
             WHERE processed = false
               AND seen_at > now() - interval '90 days'
               AND item_ref IS NOT NULL
               AND (is_listing IS NOT TRUE)
               AND price IS NULL
               AND price_eur IS NOT NULL
             GROUP BY 1, 2
             ORDER BY 3 DESC
             LIMIT 10
            """)
        if blind:
            total = sum(r["rows"] for r in blind)
            named = ", ".join(
                "%s/%s %d rows since %s"
                % (r["category"], r["provider"], r["rows"],
                   r["oldest"].date().isoformat() if r["oldest"] else "?")
                for r in blind)
            bug("high",
                "%d sold comps are invisible to valuation (price NULL, price_eur set)" % total,
                "These rows carry a usable EUR price and will never be processed: the queue "
                "filters on `price IS NOT NULL` while it values on COALESCE(price_eur, price). "
                "They are not errors and nothing logs them — the symptom is a category whose "
                "coverage stays low while comps keep arriving, which the coverage canary "
                "misreports as a crosswalk fault. %s" % named,
                src_link("server/workers/valuation_worker.py"),
                "SELECT split_part(item_ref,':',1), provider, count(*) FROM market_hits "
                "WHERE processed=false AND NOT is_listing AND price IS NULL "
                "AND price_eur IS NOT NULL GROUP BY 1,2;",
                "Add `price` to that writer's INSERT column list and backfill "
                "price = price_eur where currency = 'EUR'")
        else:
            healthy.append({
                "check": "valuation queue visibility",
                "detail": "0 sold comps carry a price_eur the queue's `price IS NOT NULL` "
                          "filter would drop"})

    # --- serving model age: nothing anywhere reported this ---
    #
    # On 2026-08-29, 53 of 54 `active` models on the box dated from 2026-04-10
    # — 141 days — and not one check said so. `scripts/preflight_models.py`
    # validates a model FILE (finite coefficients, structure) and never its
    # AGE; `calibration_worker` measures PICP/ACE/MAE of the predictions but
    # never asks when the model behind them was fitted. A model can be
    # well-formed, pass every gate, and be a season out of date.
    #
    # Retraining is scheduled and delivers nothing: nightly-train-eval-gate
    # trains 36 categories onto the GitHub runner's disk, has no S3 upload
    # (train_price contains zero S3 code), a no-op --register, and the runner is
    # then destroyed. docs/INGEST.md has the full chain.
    #
    # Tiering follows this doc rather than the alarm I first wanted to raise.
    # "A daily siren is how a channel stops being read", and a delivery chain
    # that was never wired is a STRUCTURAL gap, not a regression with a date —
    # so it is ONE aggregated medium stating the totals, the same shape as the
    # 45-categories-no-sold-comp finding. `high` is reserved for the case that
    # really is anomalous rather than merely unwired.
    #
    # Root resolution mirrors app/ml/model_loader.py::_artifacts_root, so this
    # inspects exactly what serving loads and not a path that merely looks right.
    with guard("serving model age"):
        roots = serving_artifact_roots()
        ages = serving_model_ages(roots)

        if not ages:
            # UNKNOWN, not healthy — "reporting nothing must never look like
            # all-clear". A missing directory is could-not-ask, and on a dev box
            # there are simply no artifacts, which is also not evidence.
            bug("medium", "serving model age is UNKNOWN this run",
                "No resolvable `active` model.json under any of: %s. This is "
                "not evidence that the models are fresh — it is evidence the "
                "check could not run."
                % ", ".join(str(r) for r in roots),
                src_link("server/scripts/watchdog.py"),
                "ssh collectai 'ls -la /opt/collectors/server/artifacts/*/active'",
                "")
        else:
            STALE_DAYS, ALARM_DAYS = 90, 270
            stale = sorted((a for a in ages if a[1] > STALE_DAYS), key=lambda a: -a[1])
            oldest_cat, oldest_days = max(ages, key=lambda a: a[1])
            named = ", ".join("%s %dd" % (c, d) for c, d in stale[:8])
            detail = (
                "These are the artifacts app/ml/model_loader.py serves from "
                "disk. They are well-formed — preflight_models passes them — "
                "and simply old. Retraining is scheduled but delivers nothing: "
                "nightly-train-eval-gate writes artifacts to the GitHub "
                "runner's disk, has no S3 upload, a no-op --register, and the "
                "runner is then destroyed. %s" % named)
            verify = ("ssh collectai 'for d in /opt/collectors/server/artifacts/*/; "
                      "do [ -L \"$d/active\" ] && readlink \"$d/active\"; done "
                      "| cut -c1-8 | sort | uniq -c'")
            fix = ("Decide how trained artifacts reach the box (train in the "
                   "bake, or upload to S3 and pull), then retrain")
            if oldest_days > ALARM_DAYS:
                bug("high",
                    "%d of %d serving models are over %d days old (oldest %s at %dd)"
                    % (len(stale), len(ages), ALARM_DAYS, oldest_cat, oldest_days),
                    detail, src_link("server/pipelines/train_price.py"), verify, fix)
            elif stale:
                bug("medium",
                    "%d of %d serving models are older than %d days (oldest %s at %dd)"
                    % (len(stale), len(ages), STALE_DAYS, oldest_cat, oldest_days),
                    detail, src_link("server/pipelines/train_price.py"), verify, fix)
            else:
                healthy.append({
                    "check": "serving model age",
                    "detail": "all %d serving models fitted within %d days "
                              "(oldest is %s at %dd)"
                              % (len(ages), STALE_DAYS, oldest_cat, oldest_days)})

    # --- column drift: reader and writer on different columns ---
    # Two-phase by necessity: the code half needs src/ + app/, which are never
    # deployed here, so a refs blob is generated on the dev box
    # (`npm run audit:drift:refresh`) and shipped. If it goes stale the audit is
    # still answering questions about code that no longer exists, so age is
    # reported rather than silently trusted.
    try:
        import subprocess
        refs = SERVER_ROOT / "scripts" / "coldrift_refs.json"
        if not refs.exists():
            healthy.append({"check": "column drift", "detail": "skipped — no refs blob shipped"})
        else:
            age_d = (datetime.now(timezone.utc).timestamp() - refs.stat().st_mtime) / 86400
            # --json, not the human summary line. Parsing "N HIGH" out of the
            # digest told an operator that ONE mismatch existed and never
            # WHICH — the same defect this doc already fixed for tcgcsv_worker
            # ("a failing worker must say WHY"). It paged daily from 2026-08-22
            # and finding out cost an SSH plus a re-run of the audit; the
            # answer, when finally looked up, was that the finding was false.
            r = subprocess.run(
                ["/opt/collectors/.venv/bin/python",
                 str(SERVER_ROOT / "scripts" / "audit_column_drift.py"),
                 "--refs", str(refs), "--json"],
                capture_output=True, timeout=600, cwd=str(SERVER_ROOT))
            # audit_column_drift.py is advisory and ALWAYS exits 0, so a
            # non-zero code means it died. Without this, a crash produces empty
            # stdout -> {} -> [] -> "0 findings" in what_went_well: a dead
            # audit reading as a clean one, which is the exact shape this file
            # exists to catch. Raise so the enclosing except reports it.
            if r.returncode != 0:
                raise RuntimeError("audit exited %d: %s"
                                   % (r.returncode, r.stderr.decode()[-200:]))
            drift = json.loads(r.stdout.decode() or "{}").get("findings") or []
            # DEAD_PAIR is deliberately not counted: both columns unwritten is
            # not drift, and audit_column_drift.py explains why.
            highs = [f for f in drift if f.get("confidence") == "HIGH"]
            n_high = len(highs)
            if n_high:
                named = "; ".join(
                    "%s: reads %s (%d non-null) / writes %s (%d non-null)"
                    % (f["table"], f["read_only_column"], f["read_only_nonnull"],
                       f["write_only_column"], f["write_only_nonnull"])
                    for f in highs[:3])
                bug("high", "column drift: %d reader/writer column mismatch(es)" % n_high,
                    "A column the code READS is entirely NULL while a similarly-named one is "
                    "written — the feature is starved of input and returns empty without "
                    "erroring. %s" % named,
                    src_link("server/scripts/audit_column_drift.py"),
                    "python3 scripts/audit_column_drift.py --refs scripts/coldrift_refs.json",
                    "Repoint the reader to the column the writer actually fills")
            elif age_d > 21:
                bug("info", "column-drift refs are %d days old" % int(age_d),
                    "The code half of this audit is stale; regenerate with "
                    "`npm run audit:drift:refresh` so it reflects current code.",
                    src_link("package.json"), "ls -l scripts/coldrift_refs.json", "")
            else:
                healthy.append({"check": "column drift",
                                "detail": "0 findings (refs %d days old)" % int(age_d)})
    except Exception as e:
        bug("info", "column-drift audit could not run", str(e)[:200])

    # --- search canary ---
    # unified_search ILIKEs four sources (items, category_items,
    # user_public_profiles, events). items is user-scoped and the profile view is
    # empty by design (COMMUNITY_GATED), but category_items and events MUST
    # return hits for common terms — if they stop, search silently returns an
    # empty page and still answers 200.
    try:
        probes = [("category_items", "title", ["charizard", "pikachu", "booster"]),
                  ("events", "title", ["tournament", "expo", "con"])]
        for table, col, terms in probes:
            hits = {}
            for t in terms:
                hits[t] = await c.fetchval(
                    f'SELECT count(*) FROM public."{table}" WHERE "{col}" ILIKE $1', f"%{t}%")
            if not any(hits.values()):
                bug("high", "search returns nothing from %s" % table,
                    "None of these common terms matched: %s. unified_search ILIKEs this "
                    "table and would render an empty results page with HTTP 200."
                    % ", ".join("%s=%d" % kv for kv in hits.items()),
                    src_link("server/app/features/search_router.py"),
                    "SELECT count(*) FROM %s WHERE %s ILIKE '%%charizard%%';" % (table, col),
                    "Check the table still has rows and the column was not renamed")
            else:
                healthy.append({"check": "search source %s" % table,
                                "detail": ", ".join("%s=%d" % kv for kv in hits.items())})
    except Exception as e:
        bug("info", "search canary could not run", str(e)[:200])

    # --- item-render canary ---
    # The item card needs name + category to render at all. A row missing them
    # shows as a blank card, which is how the 2026-07-24 Home-vs-Items bug
    # presented (Zod dropped a non-nullable `name` and the list silently emptied).
    try:
        r = await c.fetchrow("""
            SELECT count(*) total,
                   count(*) FILTER (WHERE COALESCE(NULLIF(name,''), NULLIF(title,'')) IS NULL) no_name,
                   count(*) FILTER (WHERE category IS NULL) no_category,
                   count(*) FILTER (WHERE user_id IS NULL) no_owner
            FROM public.items
        """)
        if r and r["total"]:
            broken = (r["no_name"] or 0) + (r["no_owner"] or 0)
            if broken:
                bug("high", "%d item row(s) cannot render" % broken,
                    "items missing a name (%d) or an owner (%d) out of %d. A nameless row "
                    "renders as a blank card; a NULL user_id is invisible under RLS to "
                    "everyone, including its creator."
                    % (r["no_name"], r["no_owner"], r["total"]),
                    tbl_link("items"),
                    "SELECT id FROM items WHERE user_id IS NULL OR COALESCE(NULLIF(name,''),NULLIF(title,'')) IS NULL;",
                    "Backfill the name, or delete the orphan rows")
            else:
                healthy.append({"check": "item render fields",
                                "detail": "%d items, all have name + owner (%d lack a category)"
                                          % (r["total"], r["no_category"])})
    except Exception as e:
        bug("info", "item-render canary could not run", str(e)[:200])

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

    # --- DAC7: who is over the line, and who is about to be -----------------
    #
    # THE GAP THIS CLOSES: `_dac7_accrue` notifies the SELLER when they cross and
    # nobody else. The founder found out by querying the database, which means in
    # practice not until a seller asked — and a crossing is the moment a decision
    # is needed (spec §5c recommends exactly this alert: "so we learn we have a
    # trader before a regulator does").
    #
    # Tiered deliberately, because the watchdog doc's rule is that a daily siren
    # trains you to ignore the channel:
    #   crossed, not yet notified -> HIGH. The terms promise notice; that promise
    #                                is currently broken for that member.
    #   crossed and notified      -> MEDIUM. Nothing is broken, but the platform
    #                                now has a reportable seller and that is a
    #                                decision, not a status line.
    #   approaching               -> INFO. Warning, not alarm.
    #   nobody near the line      -> healthy, stating the ceiling so the number
    #                                is auditable rather than implied.
    #
    # Thresholds are DERIVED from the live limits, never hardcoded here: a second
    # copy of 30/2000 in the watchdog is one more place to drift from the terms.
    try:
        limits = await c.fetchrow(
            "SELECT EXTRACT(YEAR FROM now())::int AS yr")
        year = int(limits["yr"])
        # Mirrors dac7_reportable(): reportable when EITHER limb breaches.
        SALES_LIMIT, GROSS_LIMIT = 30, 2000.0
        approach_sales = int(SALES_LIMIT * 2 / 3)      # 20
        approach_gross = GROSS_LIMIT * 0.75            # 1500.0

        rows = await c.fetch(
            """
            SELECT user_id, sales_count, gross_eur, reportable_at, notified_at
            FROM public.dac7_seller_year
            WHERE year = $1
              AND (sales_count >= $2 OR gross_eur >= $3)
            ORDER BY gross_eur DESC, sales_count DESC
            LIMIT 25
            """,
            year, approach_sales, approach_gross,
        )

        over = [r for r in rows
                if r["sales_count"] >= SALES_LIMIT or float(r["gross_eur"]) > GROSS_LIMIT]
        near = [r for r in rows if r not in over]

        def who(r):
            return "%s: %d sales / EUR %.0f" % (
                str(r["user_id"])[:8], r["sales_count"], float(r["gross_eur"]))

        unnotified = [r for r in over if r["notified_at"] is None]
        if unnotified:
            bug("high", "DAC7: seller over the line and NOT notified",
                "The marketplace terms (§6) promise notice before anything is reported. "
                "These sellers crossed and notified_at is still null, so that promise is "
                "unkept right now: %s" % "; ".join(who(r) for r in unnotified),
                tbl_link("dac7_seller_year"),
                "SELECT * FROM dac7_seller_year WHERE year=%d AND reportable_at IS NOT NULL "
                "AND notified_at IS NULL;" % year,
                "Check _dac7_accrue's notify_user call — the stamp is written BEFORE the "
                "send, so a null here means the UPDATE itself did not run.")
        notified_over = [r for r in over if r["notified_at"] is not None]
        if notified_over:
            bug("medium", "DAC7: you now have a reportable seller",
                "Above 30 sales OR EUR 2,000 in a calendar year, a marketplace in our "
                "position is required to report. Nothing is collected or filed by Sparrow "
                "today (no TIN/address/IBAN columns exist, by design), so this is the "
                "trigger for the adviser conversation in spec §5a, not a code fix: %s"
                % "; ".join(who(r) for r in notified_over),
                tbl_link("dac7_seller_year"),
                "SELECT * FROM dac7_seller_year WHERE year=%d AND reportable_at IS NOT NULL;" % year,
                "One conversation with a Dutch tax adviser on registration + whether the 5%% "
                "event-ticket fee (terms.tsx:154) pulls events in. Do NOT build collection "
                "until that answer exists.")
        if near:
            bug("info", "DAC7: seller approaching the reporting threshold",
                "Not reportable yet. Flagged at %d sales or EUR %.0f so there is warning "
                "before the decision is forced: %s"
                % (approach_sales, approach_gross, "; ".join(who(r) for r in near)),
                tbl_link("dac7_seller_year"),
                "SELECT * FROM dac7_seller_year WHERE year=%d ORDER BY gross_eur DESC;" % year,
                "No action needed. If one of these crosses, the medium finding above fires.")
        if not rows:
            top = await c.fetchrow(
                "SELECT COALESCE(MAX(sales_count),0) s, COALESCE(MAX(gross_eur),0) g "
                "FROM public.dac7_seller_year WHERE year = $1", year)
            healthy.append({
                "check": "DAC7 thresholds",
                "detail": "no seller within reach for %d — busiest is %d sales / EUR %.0f "
                          "against limits of %d / EUR %.0f"
                          % (year, int(top["s"] or 0), float(top["g"] or 0),
                             SALES_LIMIT, GROSS_LIMIT),
            })
    except Exception as exc:
        # A missing table is a real finding, not a silent skip: this check
        # reporting nothing must never be indistinguishable from "all clear".
        bug("medium", "DAC7 threshold check could not run",
            "The reporting-threshold check errored, so today's report says NOTHING about "
            "whether a seller crossed: %s" % exc,
            tbl_link("dac7_seller_year"),
            "SELECT count(*) FROM dac7_seller_year;",
            "Confirm public.dac7_seller_year exists (migration 20260809_dac7_seller_thresholds.sql).")

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
    import subprocess, time, urllib.parse
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

    # Which sub-queries we could not ask. NOT the same thing as "asked, and the
    # answer was zero" — see the `failed` handling below.
    failed: list = []

    def query(sql: str, label: str):
        """Run one Logflare query. Returns rows, or None when we could not ask.

        `None` and `[]` mean different things and the difference is the whole
        point of this function. Until 2026-08-12 every failure path here —
        curl non-zero, a timeout, an HTTP error body with no `result` key, a
        revoked PAT — returned `[]`, which then summed to `"postgres_errors": 0`
        and rendered as a green day. It was wrong on five of the last nine days:
        08-04/05/06 reported 0 Postgres errors AND 0 API calls, and 08-11
        reported 0 Postgres errors, while every neighbouring day logged 600-760
        rejected writes. Three days of "clean" were three days of blind.

        docs/WATCHDOG.md already states the rule this now obeys, for the DAC7
        check: *reporting nothing must never look like all-clear.*
        """
        url = ("https://api.supabase.com/v1/projects/%s/analytics/endpoints/logs.all"
               "?sql=%s&iso_timestamp_start=%s&iso_timestamp_end=%s"
               % (PROJECT_REF, urllib.parse.quote(sql), start, end))
        # RETRY. The `edge_logs` source answers intermittently: measured
        # 2026-08-26, the same query with the same PAT alternated OK/FAIL
        # inside one minute (2 of 10 attempts succeeded), while `postgres_logs`
        # answered on every attempt in the same runs. One shot per sub-query
        # therefore blinded the API half of the report on roughly half of all
        # days — and, worse, took the "API returning 5xx" HIGH with it: on
        # 08-25 and 08-26 that finding vanished from the report while a
        # successful manual query showed 16 5xx in the same 24h window. A
        # finding that disappears because we could not ask is the exact defect
        # the [] -> None change was made to prevent, one level up.
        last = "no attempt"
        for attempt in range(3):
            if attempt:
                time.sleep(2 * attempt)   # 2s, 4s — flaps clear in seconds
            try:
                r = subprocess.run(["curl", "-s", "--max-time", "45",
                                    "-H", "Authorization: Bearer %s" % tok, url],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    last = "curl exit %d" % r.returncode
                    continue
                payload = json.loads(r.stdout or "{}") or {}
                if not isinstance(payload, dict) or "result" not in payload:
                    # Management API errors arrive as 200-with-a-body or 4xx
                    # JSON; either way there is no `result` key and we learned
                    # nothing.
                    last = str(payload.get("message") or payload.get("error")
                               or (r.stdout or "")[:120] or "empty response")[:160]
                    continue
                return payload.get("result") or []
            except Exception as e:
                last = repr(e)
        failed.append("%s: %s (3 attempts)" % (label, last))
        return None

    out["window"] = {"start": start, "end": end}

    # Logflare's analytics endpoint silently returns PARTIAL data for long
    # windows. Measured 2026-08-21, same query, three windows:
    #   6h  -> 15 "ON CONFLICT" errors
    #   24h -> 15   (consistent: all 15 fell in the last 6h)
    #   72h -> 14   <- fewer than its own 6h subset, and user_blocks/
    #                 settings_json/shipping vanished entirely
    # A superset window returning fewer rows than its subset is proof the
    # answer is truncated, not smaller. docs/WATCHDOG.md advertises
    # `--hours 168`, which therefore produces a confidently wrong report.
    # Say so in the report rather than letting the numbers pass as facts.
    if hours > 24:
        failed.append(
            "window=%gh exceeds the ~24h range Logflare answers completely; "
            "counts below are PARTIAL and must not be read as totals" % hours)

    pg_rows = query(
        'select event_message as msg, count(*) as n from postgres_logs '
        'cross join unnest(metadata) m cross join unnest(m.parsed) p '
        'where p.error_severity = "ERROR" group by msg order by n desc limit 10',
        "postgres_errors")
    code_rows = query(
        'select cast(r.status_code as string) as code, count(*) as n from edge_logs '
        'cross join unnest(metadata) m cross join unnest(m.response) r '
        'group by code order by n desc',
        "api_status_codes")
    path_rows = query(
        'select rq.path as path, cast(rs.status_code as string) as code, count(*) as n '
        'from edge_logs cross join unnest(metadata) m '
        'cross join unnest(m.request) rq cross join unnest(m.response) rs '
        'where rs.status_code >= 400 group by path, code order by n desc limit 10',
        "api_failing_paths")

    out["postgres_errors"] = [{"message": (r.get("msg") or "")[:220], "count": r.get("n")}
                              for r in (pg_rows or [])]
    out["api_status_codes"] = [{"code": r.get("code"), "count": r.get("n")}
                               for r in (code_rows or [])]
    out["api_failing_paths"] = [{"path": r.get("path"), "code": r.get("code"), "count": r.get("n")}
                                for r in (path_rows or [])]

    # A total is only a number when the query behind it actually answered.
    # `None` renders as "unknown" and, unlike 0, cannot be mistaken for calm.
    codes = {c["code"]: c["count"] for c in out["api_status_codes"]}
    out["totals"] = {
        "postgres_errors": (sum(e["count"] or 0 for e in out["postgres_errors"])
                            if pg_rows is not None else None),
        "api_5xx": (sum(v for k, v in codes.items() if str(k).startswith("5"))
                    if code_rows is not None else None),
        "api_4xx": (sum(v for k, v in codes.items() if str(k).startswith("4"))
                    if code_rows is not None else None),
        "api_ok": (sum(v for k, v in codes.items() if str(k).startswith("2"))
                   if code_rows is not None else None),
    }
    # `available` is now earned, not assumed: it used to be set to True before
    # the first query ran, so a totally unreachable Logflare still reported
    # `"available": true` with zeros under it.
    out["available"] = pg_rows is not None
    if failed:
        out["unavailable"] = failed
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
    # Blind is a finding. Without this the report simply omits whatever the
    # failed query would have said, and a day we could not see reads exactly
    # like a day with nothing to see — which is how 08-04/05/06 passed as green
    # while catalog ingest was losing every attribute-bearing row.
    if sblogs.get("unavailable"):
        # Do NOT send the operator to mint a PAT unless the PAT is actually the
        # problem. `available` is True exactly when postgres_logs answered, and
        # every sub-query uses the SAME token in the SAME run — so a partial
        # failure alongside available=True is proof the credential is fine and
        # the source flapped. Saying "refresh the PAT" there is a wrong
        # diagnostic printed as fact, which this repo has already paid for
        # (learning_a_wrong_diagnostic_is_believed_for_sessions): on 2026-08-26
        # the PAT was a valid sbp_ token, postgres_logs answered, and only
        # edge_logs was flapping.
        creds_ok = bool(sblogs.get("available"))
        bugs.append({"severity": "medium",
                     "title": "watchdog could not read part of the Supabase logs",
                     "detail": ("This report is INCOMPLETE — the counts below are missing, "
                                "not zero: %s.%s"
                                % ("; ".join(sblogs["unavailable"])[:400],
                                   (" The PAT is NOT the cause: postgres_logs answered with the "
                                    "same token in this run, so this is the log source flapping "
                                    "upstream." if creds_ok else
                                    " No sub-query answered, so the credential is a real "
                                    "suspect."))),
                     "link": (sblogs.get("links") or {}).get("postgres_logs", ""),
                     "verify": ("Re-run in a minute; if only edge_logs/auth_logs fail it is "
                                "upstream. Credential check: head -c4 ~/.supabase/access-token "
                                "(must be sbp_)"),
                     "suggested_fix": (
                         "Upstream flap — re-run `scripts/watchdog.py --hours 24 --summary`; "
                         "note that api_5xx / api_4xx are UNKNOWN this run, not zero"
                         if creds_ok else
                         "Refresh the Management API PAT at "
                         "https://supabase.com/dashboard/account/tokens, then re-run")})
    # `or 0` on a value that is legitimately None converts UNKNOWN into "fine".
    # The 2026-08-12 change made the TOTAL honest — `api_5xx` correctly read
    # None on a blind run — and this line then evaluated None to 0 and dropped
    # the finding entirely. On 08-25 and 08-26 "API returning 5xx" was absent
    # from the report while the same window really held 16. A missing total is
    # visible in the JSON; a missing BUG looks exactly like a healthy day.
    # Three states, not two.
    _api_5xx = (sblogs.get("totals") or {}).get("api_5xx")
    if _api_5xx is None:
        if sblogs.get("unavailable"):
            bugs.append({"severity": "medium", "title": "API 5xx rate is UNKNOWN this run",
                         "detail": ("The edge_logs query did not answer, so this report cannot "
                                    "say whether the API is erroring. This is not a green "
                                    "result — the same window has previously held 16 5xx while "
                                    "this finding was silently absent."),
                         "link": (sblogs.get("links") or {}).get("api_logs", ""),
                         "verify": "Supabase > Logs > API, or re-run the watchdog",
                         "suggested_fix": "Re-run; edge_logs answers intermittently"})
    elif _api_5xx >= 10:
        bugs.append({"severity": "high", "title": "API returning 5xx",
                     "detail": "%d 5xx responses in %dh" % (_api_5xx, args.hours),
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
                body += "\n\n<b>\U0001f6f0 Supabase (API + DB)</b>"
                # A total is None when its query could not be asked, and the
                # API and Postgres queries fail INDEPENDENTLY — 08-09 and 08-12
                # both returned Postgres rows with no API rows at all. Note
                # `t.get("api_ok", 0)` cannot be used to defend this: the key
                # exists and holds None, so the default never applies and the
                # arithmetic below would raise TypeError and kill the digest.
                if None in (t.get("api_ok"), t.get("api_4xx"), t.get("api_5xx")):
                    body += "\n<i>API request counts unavailable this run</i>"
                else:
                    ok, e4, e5 = t["api_ok"], t["api_4xx"], t["api_5xx"]
                    tot = ok + e4 + e5
                    rate = (100.0 * (e4 + e5) / tot) if tot else 0.0
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
                if t.get("postgres_errors") is None:
                    body += "\n\n<i>Postgres error counts unavailable this run</i>"
                else:
                    body += "\n\n<b>{:,}</b> Postgres errors".format(t["postgres_errors"])
                for e in (sb.get("postgres_errors") or [])[:3]:
                    body += "\n  <b>{:,}</b> — {}".format(e["count"] or 0, esc(e["message"][:100]))
                links = sb.get("links") or {}
                body += "\n" + " · ".join(x for x in [
                    a_href(links.get("postgres_logs", ""), "pg logs"),
                    a_href(links.get("api_logs", ""), "api logs"),
                    a_href(links.get("auth_logs", ""), "auth logs")] if x)
            else:
                # Name the reason. "unavailable" alone is what let three blind
                # days pass unexamined.
                why = sb.get("error") or "; ".join(sb.get("unavailable") or []) or "unavailable"
                body += "\n\n<b>\U0001f6f0 Supabase logs</b>\n<i>%s</i>" % esc(why[:250])

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
            await send_ops_alert(_trim_html(body, 3800), title=title, silent=green)
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
