#!/usr/bin/env python3
"""Seed the App Store / Play Store reviewer demo account.

Creates `reviewer@sparrowcollect.com` in Supabase Auth + populates with
demonstration data so Apple/Google reviewers can exercise the full app
without rejection for 2.1 (App Completeness).

Pre-conditions:
- Supabase project live and reachable
- SUPABASE_URL + SUPABASE_SERVICE_KEY in env (.env or shell)
- bake's API endpoint live at https://api.sparrowcollect.com (or local)

Usage:
    # Set the password as an arg (won't echo, save to a password manager)
    python3 scripts/seed_reviewer_account.py --password 'StrongP4ss!XYZ'

    # Or via env var
    REVIEWER_PASSWORD='...' python3 scripts/seed_reviewer_account.py

The reviewer account gets:
- 25 collection items across 6 categories (pokemon, lego, manga, vinyl,
  anime_figures, kpop_merch)
- Portfolio value tracked over 30 days (via existing prediction data)
- 2 active purchase mandates
- 1 active build & paint project (warhammer)
- 2 demo connection users for chat testing

Idempotent: re-running with the same email won't duplicate data — it
deletes existing rows for the user first.

This script DELIBERATELY does NOT seed:
- Stripe subscription state — reviewer testing IAP must use sandbox
- Push notification tokens — reviewer's device differs each review
- 2FA — adds friction for reviewers; left off
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REVIEWER_EMAIL = "reviewer@sparrowcollect.com"

DEMO_ITEMS = [
    # category, title, condition
    ("pokemon", "Charizard Base Set Holo PSA 9", "near_mint"),
    ("pokemon", "Pikachu Illustrator Promo (graded)", "mint"),
    ("pokemon", "Mew Ancient Mew Promo", "near_mint"),
    ("pokemon", "Lugia Neo Genesis 1st Edition", "near_mint"),
    ("pokemon", "Charizard VMAX Rainbow Rare", "mint"),
    ("lego", "LEGO Star Wars UCS Millennium Falcon 75192", "new_sealed"),
    ("lego", "LEGO Creator Expert Roller Coaster 10261", "new_sealed"),
    ("lego", "LEGO Architecture Statue of Liberty 21042", "new_sealed"),
    ("lego", "LEGO Technic Bugatti Chiron 42083", "near_mint"),
    ("manga", "One Piece Volume 1 First Print (JP)", "near_mint"),
    ("manga", "Berserk Deluxe Edition Volume 1", "mint"),
    ("manga", "Akira Volume 1 Original Print", "good"),
    ("manga", "Naruto Boxset 1-72 Hardcover", "near_mint"),
    ("vinyl", "Pink Floyd - Dark Side of the Moon UK 1st Press", "very_good"),
    ("vinyl", "Daft Punk - Random Access Memories 2xLP", "near_mint"),
    ("vinyl", "Radiohead - In Rainbows Original Vinyl", "mint"),
    ("vinyl", "Taylor Swift - Folklore Limited Edition", "mint"),
    ("anime_figures", "Studio Ghibli Totoro 1/8 Scale", "new_sealed"),
    ("anime_figures", "One Piece Luffy Gear 5 Figuarts", "new_sealed"),
    ("anime_figures", "Demon Slayer Tanjiro 1/7 Aniplex", "near_mint"),
    ("anime_figures", "Goku Ultra Instinct S.H. Figuarts", "new_sealed"),
    ("kpop_merch", "BTS Map of the Soul: 7 Album Set", "new_sealed"),
    ("kpop_merch", "TWICE Formula of Love Lightstick", "new_sealed"),
    ("kpop_merch", "BLACKPINK Born Pink Photobook", "new_sealed"),
    ("kpop_merch", "NewJeans Get Up Album Bunny Edition", "new_sealed"),
]

DEMO_MANDATES = [
    {
        "category": "pokemon",
        "search_query": "Charizard Base Set holo PSA 10",
        "max_budget_eur": 8000,
        "preferred_condition": "mint",
    },
    {
        "category": "lego",
        "search_query": "LEGO UCS AT-AT 75313 sealed",
        "max_budget_eur": 950,
        "preferred_condition": "new_sealed",
    },
]

DEMO_BUILD_PROJECT = {
    "category": "warhammer",
    "title": "Space Marines Primaris Intercessors x10",
    "status": "primed",
    "started_at": datetime.now(timezone.utc) - timedelta(days=14),
    "current_step": 3,
    "total_steps": 12,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed App Store reviewer account")
    parser.add_argument("--user-id", default=None,
                        help="Reuse an existing auth user id (list_users is broken on this project)")
    parser.add_argument("--password", help="Reviewer account password (or set REVIEWER_PASSWORD env var)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions, don't execute")
    args = parser.parse_args()

    password = args.password or os.environ.get("REVIEWER_PASSWORD")
    if not password:
        print("ERROR: --password or REVIEWER_PASSWORD env var required", file=sys.stderr)
        print("       Pick a strong password (12+ chars, mixed case, digits, symbols)", file=sys.stderr)
        print("       Save it to App Review Notes for the reviewer", file=sys.stderr)
        return 2
    if len(password) < 12:
        print("ERROR: password too short (min 12 chars)", file=sys.stderr)
        return 2

    # Lazy import so the script can be loaded without all deps installed
    try:
        from supabase import create_client
    except ImportError:
        print("ERROR: pip install supabase", file=sys.stderr)
        return 2

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in env", file=sys.stderr)
        return 2

    sb = create_client(url, key)

    # 1. Create or get the auth user (idempotent: delete first if exists)
    print(f"[1/5] Ensuring auth user {REVIEWER_EMAIL} exists...")
    if args.dry_run:
        print("  DRY-RUN: would delete + recreate auth user")
        user_id = "dry-run-uuid-placeholder"
    else:
        # `list_users()` returns "Database error finding users" on this project,
        # so the old idempotency path silently fell through to create_user and
        # died with "already registered" on every re-run — after a first run had
        # ALREADY created the auth user. That is how the account came to exist
        # in `auth.users` with no profile and no items, which is worse than not
        # existing: it authenticates and then shows an empty app.
        #
        # Create-then-fall-back-to-update is the shape that survives both.
        user_id = None
        try:
            result = sb.auth.admin.create_user({
                "email": REVIEWER_EMAIL,
                "password": password,
                "email_confirm": True,  # reviewers cannot receive a confirm mail
                "user_metadata": {"full_name": "App Store Reviewer", "is_reviewer": True},
            })
            user_id = result.user.id
            print(f"  created user {user_id}")
        except Exception as e:
            if "already been registered" not in str(e):
                raise
            existing_id = os.environ.get("REVIEWER_USER_ID") or args.user_id
            if not existing_id:
                print(
                    "  ERROR: the user exists but its id was not supplied and this\n"
                    "  project's admin list_users() is broken. Re-run with\n"
                    "  --user-id <uuid>  (SELECT id FROM auth.users WHERE email=...)",
                    file=sys.stderr,
                )
                return 2
            user_id = existing_id
            print(f"  user exists — reusing {user_id} and resetting its password")
            sb.auth.admin.update_user_by_id(
                user_id, {"password": password, "email_confirm": True}
            )

    # 2. Create profile row
    print(f"[2/5] Creating profile for {user_id}...")
    if not args.dry_run:
        # Only columns `public.profiles` ACTUALLY has (verified against the
        # live schema 2026-08-20): id, username, created_at, display_name,
        # avatar_url, avatar_color, referred_by_code, seller_age_verified_at,
        # bio. The previous payload wrote `country`, `preferred_currency`,
        # `age_confirmed` and `onboarded_at` — none of which exist — and
        # PostgREST rejected the whole upsert with PGRST204 on the first of
        # them, so the script died at step 2 having already created the auth
        # user. That is why `reviewer@sparrowcollect.com` could be "missing"
        # while a half-seeded run had happened.
        #
        # `display_name` and `username` are not cosmetic here: BOTH public
        # profile views filter on `COALESCE(NULLIF(display_name,''),
        # NULLIF(username,'')) IS NOT NULL`, so a profile without them is
        # invisible in search and on leaderboards — and its own public profile
        # screen 404s.
        sb.table("profiles").upsert({
            "id": user_id,
            "username": "reviewer",
            "display_name": "App Store Reviewer",
            "bio": "Demo account for App Store / Play Store review.",
        }, on_conflict="id").execute()

    # 3. Seed 25 demo items
    print(f"[3/5] Seeding {len(DEMO_ITEMS)} demo items...")
    # `items` has NO `currency` column (verified 2026-08-20) — the old payload
    # carried one and PostgREST rejects the whole insert on an unknown column.
    #
    # `estimated_value` is set deliberately: without a value every row renders
    # "Not yet priced" and the portfolio totals €0, so a reviewer told to expect
    # a 25-item collection meets a screen full of blanks — the same guideline
    # 2.1 problem as an empty account, one step later. Values are plausible
    # per category rather than uniform, because a portfolio where every item
    # costs the same reads as fake.
    demo_values = {
        "pokemon": 420.0, "lego": 615.0, "manga": 95.0,
        "vinyl": 140.0, "anime_figures": 230.0, "kpop_merch": 65.0,
    }
    # DELETE FIRST. The module docstring has always claimed "re-running with
    # the same email won't duplicate data — it deletes existing rows for the
    # user first", and no delete existed anywhere in the file: a second run
    # simply inserted 25 more items. Prose describing behaviour nothing
    # implements is the house bug; here it is, in the script that fixes an
    # instance of it.
    if not args.dry_run:
        sb.table("items").delete().eq("user_id", user_id).execute()
        sb.table("purchase_mandates").delete().eq("user_id", user_id).execute()

    items_payload = []
    for idx, (category, title, condition) in enumerate(DEMO_ITEMS):
        base = demo_values.get(category, 120.0)
        items_payload.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "category": category,
            # `title` alone is enough: `items` carries both halves of the
            # name/title pair and a trigger fills the missing one.
            "title": title,
            "condition": condition,
            "estimated_value": round(base * (0.8 + 0.06 * (idx % 7)), 2),
            "created_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
        })
    if not args.dry_run:
        sb.table("items").insert(items_payload).execute()

    # 4. Seed 2 purchase mandates
    print(f"[4/5] Seeding {len(DEMO_MANDATES)} purchase mandates...")
    mandate_payload = []
    for m in DEMO_MANDATES:
        # Real columns (verified 2026-08-20): the table has `name`,
        # `max_total_budget` and `condition_filter` — not `max_budget_eur` or
        # `preferred_condition`, which never existed here.
        mandate_payload.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": m["search_query"][:60],
            "category": m["category"],
            "search_query": m["search_query"],
            # `max_price` is NOT NULL — the per-deal ceiling, distinct from the
            # mandate's total budget. A mandate with a total but no per-deal cap
            # would let one purchase eat the whole budget, which is why the
            # column is required.
            "max_price": m["max_budget_eur"],
            "max_total_budget": m["max_budget_eur"],
            # `condition_filter` is text[], not text — a bare string gives
            # 22P02 "malformed array literal".
            "condition_filter": [m["preferred_condition"]],
            "status": "active",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        })
    if not args.dry_run:
        sb.table("purchase_mandates").insert(mandate_payload).execute()

    # 5. Build & paint project — SKIPPED (2026-08-20).
    #
    # `public.build_projects` DOES NOT EXIST. This step would have failed the
    # whole run at the last line, after everything else had been written, which
    # is the worst place for a script that is not transactional. If build
    # projects come back, find the real table name before restoring this — do
    # not resurrect the old payload on faith.
    print("[5/5] Build & paint project: SKIPPED — public.build_projects does not exist.")

    print(f"\n✓ Reviewer account seeded.")
    print(f"  Email:    {REVIEWER_EMAIL}")
    print(f"  Password: {password}")
    print(f"  User ID:  {user_id}")
    print(f"\nNext: paste this credential into docs/APP_REVIEW_NOTES.md")
    print(f"      and into App Store Connect → App Information → Sign In Information")
    return 0


if __name__ == "__main__":
    sys.exit(main())
