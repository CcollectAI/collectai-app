#!/usr/bin/env python3
"""
Audit Row-Level Security coverage on every table a user's rows can reach.

Two distinct failure modes, opposite directions, both silent:

  RLS DISABLED        every authenticated user can read every other user's rows
                      through PostgREST. Nothing errors; the data just leaks.
  FULLY DENIED        every read returns [] and every write is rejected. The
                      feature looks "empty", not broken — the exact shape of the
                      silent-failure class this codebase keeps producing
                      (CLAUDE.md, "The failure mode this codebase is prone to").

A grep cannot answer either question: both are properties of the LIVE database,
not of the source. Run against DB_DSN_DIRECT.

WHY THIS SCRIPT WAS REWRITTEN (2026-07-27)
------------------------------------------
The first version had two blind spots, and on 2026-07-26 both of them hid a
fully-denied, client-facing table at the same time:

  1. It defined deny-all as `rls_enabled AND policies == 0`. A table carrying a
     single policy whose body is literally `USING false` is *equally* denied but
     counted as "policied, fine". build_paint_notes had exactly that, and read
     as an empty feature for weeks.
  2. It only scanned tables that have a `user_id` column. Ownership is often
     derived through a foreign key instead — build_paint_steps has no user_id,
     it belongs to a user via project_id -> build_paint_projects.user_id — so
     it was invisible to the scan entirely.

Both are fixed here:

  * Denial is computed per SQL command from the actual policy expressions
    (pg_get_expr of polqual / polwithcheck), honouring PERMISSIVE vs
    RESTRICTIVE semantics. A table is "fully denied" only when SELECT, INSERT,
    UPDATE and DELETE are all unreachable.
  * The scan universe is the transitive FK closure: every table with a user_id
    column, plus every table that reaches one (or auth.users) by following
    foreign keys up to MAX_FK_DEPTH hops.

`--self-test` proves the detector actually fires, by building a throwaway
`USING false` table and an FK-owned child inside a rolled-back transaction and
asserting both are caught. A gate nobody has seen fail is not a gate.

Usage:
    python3 server/scripts/audit_rls_coverage.py             # exit 1 on findings
    python3 server/scripts/audit_rls_coverage.py --json
    python3 server/scripts/audit_rls_coverage.py --self-test
    python3 server/scripts/audit_rls_coverage.py --list-denied   # curation aid
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("asyncpg not installed — run on EC2 (/opt/collectors/.venv)", file=sys.stderr)
    raise SystemExit(2)

# How many foreign keys deep to chase ownership. build_paint_steps is 1 hop;
# 3 covers every user-owned chain in this schema with room to spare, and keeps
# the closure from swallowing the whole catalog through shared lookup tables.
MAX_FK_DEPTH = 3

# ---------------------------------------------------------------------------
# Tables where total denial is correct: only the service-role backend touches
# them, so RLS never runs against their reads. The service role and the
# `postgres` role the API connects as both carry BYPASSRLS.
#
# An entry here is a DECISION; a missing table is a BUG.
#
# The standard applied to every line below: the table is legitimately deny-all
# only if the mobile client never names it. The client's entire Supabase surface
# is 19 `.from()` targets and 16 `rpc_*` calls (rpc_* are SECURITY DEFINER, so
# they run as the definer and are unaffected by RLS); everything else in the app
# goes through the EC2 backend on the service role. Reasons cite that.
# ---------------------------------------------------------------------------
DENY_ALL_OK: dict[str, str] = {
    # -- billing / payments -------------------------------------------------
    "subscription_events": "Stripe/RevenueCat webhook audit trail; written by the service role, never named by the client.",
    "sponsor_subscriptions": "Stripe sponsor-subscription mirror, written only by billing_router webhooks.",
    "event_tickets": "Stripe ticket purchases; written by billing_router, read back by the backend only.",
    "sponsor_companies": "Sponsor registry administered through /sponsor-companies on the backend; the app's sponsor screens call the API, never this table.",

    # -- events -------------------------------------------------------------
    # NOTE: the table's own posture is right, but v_events_with_attendees_v1 is
    # security_invoker and aggregates this table, so client reads of that view
    # get going/interested counts of 0. Tracked as a separate finding — the fix
    # is on the view, not here.
    "event_attendees": "RSVPs are written and read exclusively by the EC2 backend (/events/*/rsvp); no client `.from('event_attendees')` exists.",
    "event_announcements": "Host announcements; created and listed through /events/*/announcements on the backend.",
    "event_announcement_reads": "Read receipts written by the announcements endpoints; backend-only.",
    "event_sponsor_analytics": "Sponsor impression/click counters incremented by the backend; sponsor reporting is a server route.",
    "event_templates": "Saved event templates, served through /events/templates; no direct client read.",
    "event_follows_v1": "Follow rows written by the backend follow endpoints and consumed by event_engagement_worker.",

    # -- alerts, notifications, push ----------------------------------------
    "alert_endpoints": "Alert delivery targets managed by /alerts; consumed by the signal-alert worker.",
    "alert_rules": "Alert rule definitions written by /alerts and evaluated server-side.",
    "notification_history": "Notification log written by the push pipeline; the app reads it via /notifications.",
    "notification_impressions": "Impression telemetry written by the backend from client events; never queried by the client.",
    "notification_interactions": "Tap/dismiss telemetry written by the backend; never queried by the client.",
    "notification_outcomes": "Computed notification outcomes written by the outcome worker; analytics only.",
    "push_outbox_v1": "Outbound push queue drained by the push worker; a client reader would be a bug.",
    "user_push_tokens": "Device push tokens registered through /notifications/register; backend-only.",
    "user_push_devices": "Device registry companion to user_push_tokens; backend-only.",
    "user_notifications": "In-app notification rows served through /notifications; no direct client read.",
    "drop_follows": "Drop-follow subscriptions written by /alerts and read by the drop worker.",

    # -- chat (legacy, superseded by the *_v1 tables) -----------------------
    "chat_messages": "Superseded by chat_messages_v1, which is the table the client actually reads; this one is dormant.",
    "chat_members": "Legacy chat membership; superseded by chat_thread_members_v1.",
    "chat_bans": "Legacy chat bans; superseded by chat_thread_bans_v1.",
    "chat_typing": "Legacy typing state; superseded by chat_typing_v1 behind rpc_set_typing_v1 (SECURITY DEFINER).",
    "chat_reports": "Abuse reports; write-only from the backend moderation path, deliberately unreadable by clients.",
    "chat_rooms": "Legacy public rooms; superseded by chat_threads_v1.",

    # -- scanning / prediction pipeline -------------------------------------
    "prediction_sessions": "Only referenced by src/app/(admin)/review.tsx, which sits outside the expo-router root (./app) and is therefore unreachable dead code; the live writer is the backend.",
    "quickscan_drafts_v1": "Quick Scan drafts persisted through /quickscan; the client holds drafts in local state.",
    "quickscan_history": "Scan history served through /quickscan/history on the backend.",
    "item_extractions_v1": "Vision extraction output written by the scan pipeline; internal ML artefact.",
    "pricing_traces": "Per-prediction trace rows written by the valuation worker; debugging artefact.",
    "guidance_runs": "Guidance/LLM run log written by the backend; internal telemetry.",
    "suggestion_logs": "Catalog-suggestion audit log written by the backend.",
    "taxonomy_corrections": "Taxonomy correction feedback written by the backend, consumed by retraining.",
    "item_valuation_history": "Valuation snapshots written by valuation_worker; the app reads values off items/price_history via the API.",
    "item_provenance_events": "Provenance timeline written through /items/*/provenance; served by the backend.",
    "buyer_intents": "Purchase-mandate intent rows written by the deal pipeline.",
    "agent_jobs": "Background agent job queue claimed by workers.",
    "demand_signals": "Demand telemetry written by the backend (record_demand_signal); feeds mv_demand_heat.",

    # -- market data (incl. monthly partitions) -----------------------------
    "market_hits_default": "market_hits partition; ingest writes via upsert_market_hits_batch, workers read. No client path.",
    "market_hits_archive": "market_hits archive partition; warm-tier data, backend-only.",
    "market_hits_y2026m07": "market_hits monthly partition; backend-only.",
    "market_hits_y2026m08": "market_hits monthly partition; backend-only.",
    "market_hits_y2026m09": "market_hits monthly partition; backend-only.",
    "price_history_default": "price_history partition; chart data is served through the API, never read directly.",
    "price_history_y2026m07": "price_history monthly partition; backend-only.",
    "price_ground_truths": "Realised-sale ground truth used for model calibration; backend-only.",

    # -- collections / items derived data -----------------------------------
    "collection_items": "Collection membership written through /collections; the client reads items, not this join table.",
    "wishlist_items_v1": "Wishlist rows served through the backend wishlist routes.",
    "image_embeddings": "Vision embeddings written by the scan pipeline; ML artefact.",
    "item_embeddings": "Text embeddings written by the matching pipeline; ML artefact.",
    "item_latest_price_mat": "Materialised latest-price helper refreshed by a worker; the app reads items.estimated_value.",
    "agreements": "Deal-desk agreements; the Deal Hub is served entirely by /purchase on the backend.",
    "ratings": "Post-deal ratings hanging off agreements; same backend-only Deal Hub surface as its parent.",
    "twitch_events": "Twitch webhook events; the creators feature is stubbed (twitch_creators is empty) and reads go through the API.",
    "twitch_streams_live": "Twitch live-state cache written by the Twitch poller.",
}


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------
CMDS = ("select", "insert", "update", "delete")
_CMD_CODE = {"select": "r", "insert": "a", "update": "w", "delete": "d"}
_PAREN = re.compile(r"^\((.*)\)$", re.S)


def _is_literal_false(expr: str | None) -> bool:
    """True only when the policy body can never evaluate to true.

    pg_get_expr renders the house convention `USING (false)` as `false`, but
    strip redundant parens anyway so `((false))` is not mistaken for a real
    predicate. NULL is NOT false: a FOR INSERT policy has no USING clause and a
    FOR SELECT policy has no WITH CHECK clause, and neither absence denies.
    """
    if expr is None:
        return False
    e = expr.strip().lower()
    while (m := _PAREN.match(e)):
        e = m.group(1).strip()
    return e == "false"


def _relevant_exprs(pol: dict, cmd: str) -> list[str | None]:
    """The policy expressions Postgres actually evaluates for this command."""
    qual, check = pol["using_expr"], pol["check_expr"]
    if cmd in ("select", "delete"):
        return [qual]
    if cmd == "insert":
        # INSERT is gated by WITH CHECK. A FOR ALL policy with no explicit
        # WITH CHECK reuses its USING expression.
        return [check if check is not None else qual]
    # UPDATE reads the old row through USING and writes the new one through
    # WITH CHECK; either being false blocks it.
    return [qual, check if check is not None else qual]


def _applies(pol: dict, cmd: str) -> bool:
    return pol["cmd"] in ("*", _CMD_CODE[cmd])


def denied_commands(policies: list[dict]) -> list[str]:
    """Commands no caller can ever perform, given this table's policies.

    Postgres grants access when at least one PERMISSIVE policy passes AND every
    applicable RESTRICTIVE policy passes. So a command is denied when either
    there is no permissive policy that could ever pass, or some restrictive
    policy can never pass.
    """
    out = []
    for cmd in CMDS:
        permissive = [p for p in policies if p["permissive"] and _applies(p, cmd)]
        restrictive = [p for p in policies if not p["permissive"] and _applies(p, cmd)]
        can_allow = any(
            not any(_is_literal_false(e) for e in _relevant_exprs(p, cmd))
            for p in permissive
        )
        blocked = any(
            any(_is_literal_false(e) for e in _relevant_exprs(p, cmd))
            for p in restrictive
        )
        if not can_allow or blocked:
            out.append(cmd)
    return out


# ---------------------------------------------------------------------------
# Scan universe: user_id columns + the transitive FK closure around them
# ---------------------------------------------------------------------------
TABLES_SQL = """
    SELECT c.oid,
           c.relname                       AS tbl,
           c.relrowsecurity                AS rls,
           coalesce(s.n_live_tup, 0)       AS rows,
           EXISTS (SELECT 1 FROM pg_attribute a
                   WHERE a.attrelid = c.oid AND a.attname = 'user_id'
                     AND a.attnum > 0 AND NOT a.attisdropped) AS has_user_id
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
    -- 'p' as well as 'r': a partitioned PARENT carries its own RLS flag, and
    -- new partitions do NOT inherit ENABLE ROW LEVEL SECURITY. Scanning only
    -- ordinary tables would miss both halves of that.
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
"""

FKS_SQL = """
    SELECT con.conrelid AS child, con.confrelid AS parent,
           con.conrelid::regclass::text  AS child_name,
           con.confrelid::regclass::text AS parent_name
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE con.contype = 'f' AND n.nspname = 'public'
"""

POLICIES_SQL = """
    SELECT p.polrelid                                AS oid,
           p.polname                                 AS name,
           p.polcmd::text                            AS cmd,
           p.polpermissive                           AS permissive,
           pg_get_expr(p.polqual, p.polrelid)        AS using_expr,
           pg_get_expr(p.polwithcheck, p.polrelid)   AS check_expr
    FROM pg_policy p
    JOIN pg_class c ON c.oid = p.polrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
"""


def owned_universe(tables: list[dict], fks: list[dict]) -> dict[str, str]:
    """Every table a user's rows can reach, mapped to why it is in scope.

    Roots are tables carrying user_id (and anything FK-referencing auth.users).
    From there ownership propagates DOWN the foreign keys: if `parent` is owned
    and `child` references it, the child's rows belong to whoever owns the
    parent's rows. That is precisely the edge build_paint_steps travels, and it
    is the edge the previous user_id-only scan could not see.
    """
    by_oid = {t["oid"]: t["tbl"] for t in tables}
    scope: dict[str, str] = {}
    frontier: list[int] = []

    for t in tables:
        if t["has_user_id"]:
            scope[t["tbl"]] = "has user_id"
            frontier.append(t["oid"])
    for fk in fks:
        if fk["parent_name"] == "auth.users" and fk["child_name"] not in scope:
            child = by_oid.get(fk["child"])
            if child and child not in scope:
                scope[child] = "FK -> auth.users"
                frontier.append(fk["child"])

    children: dict[int, list[tuple[int, str]]] = {}
    for fk in fks:
        children.setdefault(fk["parent"], []).append((fk["child"], fk["parent_name"]))

    for depth in range(1, MAX_FK_DEPTH + 1):
        nxt: list[int] = []
        for oid in frontier:
            for child_oid, parent_name in children.get(oid, []):
                name = by_oid.get(child_oid)
                if not name or name in scope:
                    continue
                scope[name] = f"FK -> {parent_name} (depth {depth})"
                nxt.append(child_oid)
        if not nxt:
            break
        frontier = nxt

    return scope


async def collect(conn) -> dict:
    tables = [dict(r) for r in await conn.fetch(TABLES_SQL)]
    fks = [dict(r) for r in await conn.fetch(FKS_SQL)]
    pols = [dict(r) for r in await conn.fetch(POLICIES_SQL)]

    by_rel: dict[int, list[dict]] = {}
    for p in pols:
        by_rel.setdefault(p["oid"], []).append(p)

    scope = owned_universe(tables, fks)

    leaks, denied = [], []
    for t in tables:
        if t["tbl"] not in scope:
            continue
        if not t["rls"]:
            leaks.append({"tbl": t["tbl"], "rows": t["rows"], "why": scope[t["tbl"]]})
            continue
        pol = by_rel.get(t["oid"], [])
        blocked = denied_commands(pol)
        if len(blocked) == len(CMDS):
            denied.append({
                "tbl": t["tbl"],
                "rows": t["rows"],
                "why": scope[t["tbl"]],
                "policies": ", ".join(f"{p['name']}[{p['cmd']}]" for p in pol) or "none",
            })
    return {"scanned": len(scope), "total_tables": len(tables), "leaks": leaks, "denied": denied}


# ---------------------------------------------------------------------------
# Self-test — prove the two blind spots are actually closed
# ---------------------------------------------------------------------------
async def self_test(conn) -> int:
    """Build the exact shapes that slipped through the old audit, inside a
    transaction that is always rolled back, and assert they are now caught."""
    failures = []
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("""
            CREATE TABLE public._rls_selftest_parent (id uuid PRIMARY KEY, user_id uuid);
            CREATE TABLE public._rls_selftest_child  (
                id uuid PRIMARY KEY,
                parent_id uuid REFERENCES public._rls_selftest_parent(id)
            );
            ALTER TABLE public._rls_selftest_parent ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public._rls_selftest_child  ENABLE ROW LEVEL SECURITY;
            -- blind spot 1: a policy exists, and it denies everything
            CREATE POLICY _selftest_deny ON public._rls_selftest_child
                FOR ALL USING (false) WITH CHECK (false);
            -- a control: an ordinary owner policy must NOT be reported
            CREATE POLICY _selftest_own ON public._rls_selftest_parent
                FOR ALL USING (user_id = '00000000-0000-0000-0000-000000000000'::uuid);
        """)
        res = await collect(conn)
        found = {d["tbl"] for d in res["denied"]}

        # blind spot 2: the child has no user_id — it must still be in scope
        if "_rls_selftest_child" not in found:
            failures.append(
                "FK-owned table with a `USING false` policy was NOT reported — "
                "both blind spots are still open"
            )
        if "_rls_selftest_parent" in found:
            failures.append("a normal owner policy was misreported as deny-all")

        # and the false-detector must not fire on a real predicate
        if _is_literal_false("(user_id = auth.uid())"):
            failures.append("_is_literal_false matched a real predicate")
        if not _is_literal_false("((false))"):
            failures.append("_is_literal_false missed a parenthesised false")
        if _is_literal_false(None):
            failures.append("_is_literal_false treated a NULL (absent) clause as denial")
    finally:
        await tx.rollback()

    print("\n=== self-test ===")
    for f in failures:
        print(f"    FAIL  {f}")
    if not failures:
        print("    PASS  deny-by-`USING false` detected; FK-owned tables in scope;")
        print("          owner policies and absent clauses not misreported.")
    print()
    return 1 if failures else 0


async def main() -> int:
    dsn = os.environ.get("DB_DSN_DIRECT") or os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN_DIRECT not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(dsn)
    try:
        if "--self-test" in sys.argv:
            return await self_test(conn)
        res = await collect(conn)
    finally:
        await conn.close()

    leaks = res["leaks"]
    denied = res["denied"]
    unexpected = [d for d in denied if d["tbl"] not in DENY_ALL_OK]
    stale = sorted(set(DENY_ALL_OK) - {d["tbl"] for d in denied})

    if "--list-denied" in sys.argv:  # curation aid: dump every denied table
        for d in sorted(denied, key=lambda x: x["tbl"]):
            mark = "ok " if d["tbl"] in DENY_ALL_OK else "NEW"
            print(f"{mark} {d['tbl']:42} rows={d['rows']:>9}  {d['why']:38} {d['policies']}")
        return 0

    if "--json" in sys.argv:
        print(json.dumps({
            "scanned": res["scanned"],
            "total_tables": res["total_tables"],
            "rls_disabled": [r["tbl"] for r in leaks],
            "deny_all_unexpected": [r["tbl"] for r in unexpected],
            "stale_allowlist": stale,
        }, indent=2))
    else:
        print("\n=== RLS coverage on user-owned tables (user_id + FK closure) ===\n")
        print(f"  public tables              : {res['total_tables']}")
        print(f"  in scope (user-owned)      : {res['scanned']}")
        print(f"  RLS disabled (LEAK)        : {len(leaks)}")
        print(f"  fully denied, unexpected   : {len(unexpected)}")
        print(f"  fully denied, documented   : {len(denied) - len(unexpected)}\n")
        for r in leaks:
            print(f"    LEAK  {r['tbl']:40} {r['rows']:>9} rows — RLS off; {r['why']}")
        for r in unexpected:
            print(f"    DENY  {r['tbl']:40} {r['rows']:>9} rows — every command blocked ({r['policies']})")
            print(f"          in scope because: {r['why']}")
        for t in stale:
            print(f"    STALE {t} is allowlisted as deny-all but is no longer deny-all")
        if not (leaks or unexpected or stale):
            print("    clean — every user-owned table is either policied or a documented deny-all")
        print()

    return 1 if (leaks or unexpected or stale) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
