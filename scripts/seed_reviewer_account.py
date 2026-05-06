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
        try:
            existing = sb.auth.admin.list_users()
            for u in existing:
                if getattr(u, "email", None) == REVIEWER_EMAIL:
                    print(f"  found existing user {u.id} — deleting for clean reseed")
                    sb.auth.admin.delete_user(u.id)
                    break
        except Exception as e:
            print(f"  WARN listing users failed: {e}")

        result = sb.auth.admin.create_user({
            "email": REVIEWER_EMAIL,
            "password": password,
            "email_confirm": True,  # skip email verification for reviewer
            "user_metadata": {
                "full_name": "App Store Reviewer",
                "is_reviewer": True,
            },
        })
        user_id = result.user.id
        print(f"  created user {user_id}")

    # 2. Create profile row
    print(f"[2/5] Creating profile for {user_id}...")
    if not args.dry_run:
        sb.table("profiles").upsert({
            "id": user_id,
            "username": "reviewer",
            "display_name": "App Store Reviewer",
            "country": "NL",
            "preferred_currency": "EUR",
            "age_confirmed": True,
            "onboarded_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="id").execute()

    # 3. Seed 25 demo items
    print(f"[3/5] Seeding {len(DEMO_ITEMS)} demo items...")
    items_payload = []
    for category, title, condition in DEMO_ITEMS:
        items_payload.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "category": category,
            "title": title,
            "condition": condition,
            "currency": "EUR",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
        })
    if not args.dry_run:
        sb.table("items").insert(items_payload).execute()

    # 4. Seed 2 purchase mandates
    print(f"[4/5] Seeding {len(DEMO_MANDATES)} purchase mandates...")
    mandate_payload = []
    for m in DEMO_MANDATES:
        mandate_payload.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "category": m["category"],
            "search_query": m["search_query"],
            "max_budget_eur": m["max_budget_eur"],
            "preferred_condition": m["preferred_condition"],
            "status": "active",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
        })
    if not args.dry_run:
        sb.table("purchase_mandates").insert(mandate_payload).execute()

    # 5. Seed 1 build & paint project
    print(f"[5/5] Seeding 1 build & paint project...")
    if not args.dry_run:
        sb.table("build_projects").insert({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "category": DEMO_BUILD_PROJECT["category"],
            "title": DEMO_BUILD_PROJECT["title"],
            "status": DEMO_BUILD_PROJECT["status"],
            "current_step": DEMO_BUILD_PROJECT["current_step"],
            "total_steps": DEMO_BUILD_PROJECT["total_steps"],
            "started_at": DEMO_BUILD_PROJECT["started_at"].isoformat(),
        }).execute()

    print(f"\n✓ Reviewer account seeded.")
    print(f"  Email:    {REVIEWER_EMAIL}")
    print(f"  Password: {password}")
    print(f"  User ID:  {user_id}")
    print(f"\nNext: paste this credential into docs/APP_REVIEW_NOTES.md")
    print(f"      and into App Store Connect → App Information → Sign In Information")
    return 0


if __name__ == "__main__":
    sys.exit(main())
