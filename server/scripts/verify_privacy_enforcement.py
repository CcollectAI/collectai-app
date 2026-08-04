#!/usr/bin/env python3
"""
Verify that Settings → Privacy actually enforces anything.

Why this exists: from the table's creation (2026-02-24) until 2026-08-04,
`user_privacy_settings` had **zero readers**. All four toggles saved correctly
and nothing consulted the result:

  show_collection_value   userProvider hardcoded collectionValueEur: null
  show_item_count         userProvider hardcoded collectionCount: null
  allow_discovery         no search query filtered on it
  show_online_status      PresenceIndicator rendered presence for any userId
                          with no check — this one FAILED OPEN (column default
                          is false, status showed anyway)

No test caught it, because every test asked a STRUCTURAL question ("does the
toggle save?"). It did save. The question that matters is a question about
VALUES: with the toggle off, is the data actually hidden? Only exercising the
live view/RPC answers that.

This flips each toggle against a real user in a **rolled-back transaction** and
asserts the data disappears. It is the gate: if someone recreates a view WITH
(security_invoker = true), or drops the predicate from an RPC, this fails.

Usage:
    python3 server/scripts/verify_privacy_enforcement.py           # exit 1 on failure
    python3 server/scripts/verify_privacy_enforcement.py --json
Requires DB_DSN_DIRECT (run on EC2, or with the direct DSN exported).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

try:
    import asyncpg
except ImportError:  # pragma: no cover
    print("asyncpg not installed — run this on EC2 (/opt/collectors/.venv)", file=sys.stderr)
    raise SystemExit(2)


GATED_VIEWS = ("user_public_profiles", "user_public_profile_v1")


async def _check(conn) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    # -- security_invoker must stay OFF -------------------------------------
    # user_privacy_settings has owner-only SELECT policies. A non-invoker view
    # evaluates that RLS as the view owner and can see every row; an invoker
    # view sees nothing for other users, COALESCE supplies the permissive
    # default, and every gate below silently opens while still "passing" a
    # structural test.
    for view in GATED_VIEWS:
        opts = await conn.fetchval(
            "SELECT reloptions FROM pg_class WHERE oid = ('public.' || $1)::regclass", view
        )
        invoker = bool(opts) and any("security_invoker=true" in o for o in opts)
        add(f"{view}: security_invoker is off", not invoker, str(opts))

    # -- the view account deletion DELETEs from must stay auto-updatable ----
    # account_router._do_account_delete issues DELETE FROM user_public_profiles
    # and only catches UndefinedTableError. Adding a JOIN or a target-list
    # aggregate to that view makes it read-only and turns account deletion into
    # a 500.
    updatable = await conn.fetchval(
        "SELECT is_updatable FROM information_schema.views WHERE table_name = 'user_public_profiles'"
    )
    add("user_public_profiles stays auto-updatable (account deletion)", updatable == "YES", str(updatable))

    # -- pick real subjects -------------------------------------------------
    profile_uid = await conn.fetchval(
        "SELECT id FROM profiles "
        "WHERE COALESCE(NULLIF(display_name,''), NULLIF(username,'')) IS NOT NULL LIMIT 1"
    )
    # STRATIFY: presence must be checked against a user that HAS a presence row.
    # Any user without one returns zero rows whether the gate works or not — a
    # valid-looking empty result that proves nothing.
    presence_uid = await conn.fetchval("SELECT user_id FROM user_presence LIMIT 1")

    if profile_uid is None:
        add("a profile exists to test against", False, "no eligible profiles")
        return results

    async def stats(uid):
        return await conn.fetchrow(
            "SELECT collection_count, collection_value_eur FROM user_public_profile_v1 WHERE user_id = $1",
            uid,
        )

    async def discoverable(uid) -> int:
        return await conn.fetchval(
            "SELECT count(*) FROM user_public_profiles WHERE user_id = $1", uid
        )

    async def set_privacy(uid, **cols):
        sets = ", ".join(f"{k} = {str(v).lower()}" for k, v in cols.items())
        names = ", ".join(cols)
        vals = ", ".join(str(v).lower() for v in cols.values())
        await conn.execute(
            f"INSERT INTO user_privacy_settings (user_id, {names}) VALUES ($1, {vals}) "
            f"ON CONFLICT (user_id) DO UPDATE SET {sets}",
            uid,
        )

    # -- stats revealed when ON, hidden when OFF ----------------------------
    await set_privacy(profile_uid, show_item_count=True, show_collection_value=True)
    on = await stats(profile_uid)
    await set_privacy(profile_uid, show_item_count=False, show_collection_value=False)
    off = await stats(profile_uid)

    add("show_item_count ON reveals count", on["collection_count"] is not None, str(on["collection_count"]))
    add("show_item_count OFF hides count", off["collection_count"] is None, str(off["collection_count"]))
    add("show_collection_value ON reveals value", on["collection_value_eur"] is not None, str(on["collection_value_eur"]))
    add("show_collection_value OFF hides value", off["collection_value_eur"] is None, str(off["collection_value_eur"]))

    # -- discovery ----------------------------------------------------------
    await set_privacy(profile_uid, allow_discovery=True)
    disc_on = await discoverable(profile_uid)
    await set_privacy(profile_uid, allow_discovery=False)
    disc_off = await discoverable(profile_uid)
    add("allow_discovery ON makes user findable", disc_on == 1, str(disc_on))
    add("allow_discovery OFF hides user from search", disc_off == 0, str(disc_off))

    # -- defaults for a user who never opened Settings ----------------------
    await conn.execute("DELETE FROM user_privacy_settings WHERE user_id = $1", profile_uid)
    default = await stats(profile_uid)
    add("no settings row → stats visible (column default true)",
        default["collection_count"] is not None, str(default["collection_count"]))

    # -- presence -----------------------------------------------------------
    if presence_uid is None:
        add("presence gate (needs a user_presence row)", False, "no user_presence rows to test")
    else:
        async def presence_rows(uid) -> tuple[int, int]:
            single = await conn.fetch("SELECT * FROM rpc_get_presence_v1($1)", uid)
            batch = await conn.fetch("SELECT * FROM rpc_get_batch_presence_v1($1::uuid[])", [uid])
            return len(single), len(batch)

        await set_privacy(presence_uid, show_online_status=True)
        s_on, b_on = await presence_rows(presence_uid)
        await set_privacy(presence_uid, show_online_status=False)
        s_off, b_off = await presence_rows(presence_uid)
        await conn.execute("DELETE FROM user_privacy_settings WHERE user_id = $1", presence_uid)
        s_none, b_none = await presence_rows(presence_uid)

        add("show_online_status ON exposes presence", s_on == 1 and b_on == 1, f"single={s_on} batch={b_on}")
        add("show_online_status OFF hides presence", s_off == 0 and b_off == 0, f"single={s_off} batch={b_off}")
        add("no settings row → presence hidden (column default false)",
            s_none == 0 and b_none == 0, f"single={s_none} batch={b_none}")

    return results


async def main() -> int:
    dsn = os.getenv("DB_DSN_DIRECT") or os.getenv("DB_DSN")
    if not dsn:
        print("DB_DSN_DIRECT not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(dsn)
    tr = conn.transaction()
    await tr.start()
    try:
        results = await _check(conn)
    except asyncpg.PostgresError as exc:
        # A missing column/view means the enforcement migration has not been
        # applied — report it as a failed check rather than a stack trace, so
        # running this against an unmigrated DB reads as "not enforced".
        results = [("privacy enforcement objects exist", False, f"{type(exc).__name__}: {exc}")]
    finally:
        # Never leave test toggles behind on real accounts.
        await tr.rollback()
        await conn.close()

    failed = [r for r in results if not r[1]]

    if "--json" in sys.argv:
        print(json.dumps(
            {"checks": [{"name": n, "ok": o, "detail": d} for n, o, d in results],
             "failed": len(failed)},
            indent=2,
        ))
    else:
        print("=== Privacy enforcement (live schema, rolled back) ===\n")
        for name, ok, detail in results:
            mark = "PASS" if ok else "FAIL"
            suffix = f"   [{detail}]" if (detail and not ok) else ""
            print(f"  {mark}  {name}{suffix}")
        print()
        print(f"  {len(results) - len(failed)}/{len(results)} checks passed")
        if failed:
            print("\n  A privacy toggle is not being enforced. The data is exposed.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
