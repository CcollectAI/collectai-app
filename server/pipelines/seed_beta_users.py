"""
Seed 8 beta-test users with realistic collector personas.

Creates auth accounts (via Supabase Admin API), profiles, public profiles,
user settings, and personal collection items.  Every user is tagged with
``user_metadata.is_seed = true`` so cleanup only touches seed data.

Usage:
    python -m pipelines.seed_beta_users                     # seed all
    python -m pipelines.seed_beta_users --dry-run            # preview
    python -m pipelines.seed_beta_users --cleanup            # remove seed users
    python -m pipelines.seed_beta_users --password "Custom1!" # custom password
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Ensure server/ is on sys.path so `from app.*` works when invoked as a module
_server_root = str(Path(__file__).resolve().parent.parent)
if _server_root not in sys.path:
    sys.path.insert(0, _server_root)

import asyncpg  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logger = logging.getLogger("collectai.seed_beta_users")


def _setup_logging(level: str = "INFO") -> None:
    if logger.handlers:
        return
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------


@dataclass
class Persona:
    handle: str
    email: str
    display_name: str
    bio: str
    location: str
    interests: list[str]
    categories: list[str]
    currency: str
    region: str
    locale: str
    items: list[dict[str, str]] = field(default_factory=list)


PERSONAS: list[Persona] = [
    Persona(
        handle="alice_poke",
        email="alice@collectai.test",
        display_name="Alice Hartmann",
        bio="Pokemon & Yu-Gi-Oh! enthusiast since 1999. PSA grading addict.",
        location="Berlin, Germany",
        interests=["pokemon", "yugioh", "grading"],
        categories=["pokemon", "yugioh"],
        currency="EUR",
        region="europe",
        locale="de-DE",
        items=[
            {"category": "pokemon", "title": "Charizard Base Set PSA 9", "condition": "graded", "grade": "9", "graded_by": "PSA"},
            {"category": "pokemon", "title": "Pikachu Illustrator Promo JP", "condition": "raw"},
            {"category": "yugioh", "title": "Blue-Eyes White Dragon LOB-001 1st Ed", "condition": "graded", "grade": "8.5", "graded_by": "BGS"},
        ],
    ),
    Persona(
        handle="bob_mtg",
        email="bob@collectai.test",
        display_name="Bob Meier",
        bio="Legacy & Commander player. Reserved List investor.",
        location="Munich, Germany",
        interests=["mtg", "commander", "reserved_list"],
        categories=["mtg"],
        currency="EUR",
        region="europe",
        locale="de-DE",
        items=[
            {"category": "mtg", "title": "Black Lotus Beta HP", "condition": "raw"},
            {"category": "mtg", "title": "Underground Sea Revised NM", "condition": "raw"},
            {"category": "mtg", "title": "Mox Pearl Unlimited BGS 7", "condition": "graded", "grade": "7", "graded_by": "BGS"},
            {"category": "mtg", "title": "Force of Will Alliances LP", "condition": "raw"},
        ],
    ),
    Persona(
        handle="clara_funko",
        email="clara@collectai.test",
        display_name="Clara Rodriguez",
        bio="Funko Pop & designer toy collector. Chase hunter.",
        location="Los Angeles, CA",
        interests=["funko", "designer_toys", "chase_variants"],
        categories=["funko", "designer_toys"],
        currency="USD",
        region="americas",
        locale="en-US",
        items=[
            {"category": "funko", "title": "Freddy Funko as Pennywise SDCC 2019", "condition": "mint", "sealed": "true"},
            {"category": "funko", "title": "Metallic Beerus SDCC Chase", "condition": "mint", "sealed": "true"},
            {"category": "designer_toys", "title": "KAWS Companion Open Edition Grey", "condition": "mint"},
        ],
    ),
    Persona(
        handle="david_hammer",
        email="david@collectai.test",
        display_name="David Krause",
        bio="Warhammer 40K army builder. 3000+ pts Necrons painted.",
        location="Hamburg, Germany",
        interests=["warhammer", "painting", "40k"],
        categories=["warhammer"],
        currency="EUR",
        region="europe",
        locale="de-DE",
        items=[
            {"category": "warhammer", "title": "Silent King – Szarekh (painted)", "condition": "used"},
            {"category": "warhammer", "title": "Indomitus Box Set (sealed)", "condition": "mint", "sealed": "true"},
        ],
    ),
    Persona(
        handle="emi_manga",
        email="emi@collectai.test",
        display_name="Emi Tanaka",
        bio="Manga collector & retro gamer. OOP hunter.",
        location="Tokyo, Japan",
        interests=["manga", "retro_games", "oop_volumes"],
        categories=["manga", "retro_games"],
        currency="JPY",
        region="japan",
        locale="ja-JP",
        items=[
            {"category": "manga", "title": "Berserk Vol 1 First Print JP", "condition": "good"},
            {"category": "manga", "title": "Slam Dunk Complete Box Set", "condition": "mint", "sealed": "true"},
            {"category": "retro_games", "title": "Super Famicom Chrono Trigger CIB", "condition": "used"},
            {"category": "retro_games", "title": "Game Boy Color Pokemon Gold Sealed", "condition": "mint", "sealed": "true"},
        ],
    ),
    Persona(
        handle="frank_sports",
        email="frank@collectai.test",
        display_name="Frank Wilson",
        bio="Sports cards investor. PSA 10 rookie cards only.",
        location="Chicago, IL",
        interests=["sportscards", "rookie_cards", "grading"],
        categories=["sportscards"],
        currency="USD",
        region="americas",
        locale="en-US",
        items=[
            {"category": "sportscards", "title": "Michael Jordan Fleer 1986 PSA 10", "condition": "graded", "grade": "10", "graded_by": "PSA"},
            {"category": "sportscards", "title": "LeBron James Topps Chrome 2003 RC PSA 9", "condition": "graded", "grade": "9", "graded_by": "PSA"},
            {"category": "sportscards", "title": "Luka Doncic Prizm Silver 2018 BGS 9.5", "condition": "graded", "grade": "9.5", "graded_by": "BGS"},
        ],
    ),
    Persona(
        handle="greta_lego",
        email="greta@collectai.test",
        display_name="Greta Nilsson",
        bio="LEGO UCS & diecast collector. Retired sets specialist.",
        location="San Francisco, CA",
        interests=["lego", "diecast", "retired_sets"],
        categories=["lego", "diecast"],
        currency="USD",
        region="americas",
        locale="en-US",
        items=[
            {"category": "lego", "title": "LEGO Star Wars UCS Millennium Falcon 75192 (sealed)", "condition": "mint", "sealed": "true"},
            {"category": "lego", "title": "LEGO Creator Expert Taj Mahal 10256", "condition": "used"},
            {"category": "diecast", "title": "Hot Wheels RLC 1969 Camaro Chrome", "condition": "mint", "sealed": "true"},
            {"category": "diecast", "title": "AUTOart Porsche 911 GT3 RS 1:18", "condition": "mint"},
            {"category": "diecast", "title": "Tomica Limited Vintage Nissan Skyline GT-R", "condition": "mint"},
        ],
    ),
    Persona(
        handle="hiro_anime",
        email="hiro@collectai.test",
        display_name="Hiro Nakamura",
        bio="Anime figures & K-pop merch. Nendoroid completionist.",
        location="Osaka, Japan",
        interests=["anime_figures", "kpop_merch", "nendoroid"],
        categories=["anime_figures", "kpop_merch"],
        currency="JPY",
        region="japan",
        locale="ja-JP",
        items=[
            {"category": "anime_figures", "title": "Saber Alter 1/7 Scale by Alter", "condition": "mint"},
            {"category": "anime_figures", "title": "Nendoroid Rem Re:Zero #663", "condition": "mint", "sealed": "true"},
            {"category": "kpop_merch", "title": "BTS Map of the Soul ON:E Photocard Set", "condition": "mint"},
        ],
    ),
]

DEFAULT_PASSWORD = os.environ.get("SEED_USER_PASSWORD", "ChangeMeBeforeSeed!")


# ---------------------------------------------------------------------------
# Supabase Admin helper
# ---------------------------------------------------------------------------

def _get_supabase_admin():
    """Get Supabase admin client for auth operations."""
    try:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            return None
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.debug("Supabase admin client not available: %s", e)
        return None


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

async def seed_users(
    *,
    dry_run: bool = False,
    password: str | None = None,
) -> dict:
    """Create all 8 beta personas.

    Returns summary dict: {success, created, skipped, total, users}.
    """
    pw = password or os.getenv("SEED_USER_PASSWORD", DEFAULT_PASSWORD)
    summary: dict = {"success": True, "created": 0, "skipped": 0, "total": len(PERSONAS), "users": [], "dry_run": dry_run}

    if dry_run:
        for p in PERSONAS:
            logger.info("[DRY RUN] Would create: %s <%s> — %s (%d items)",
                        p.display_name, p.email, ", ".join(p.categories), len(p.items))
            summary["users"].append({"email": p.email, "handle": p.handle, "user_id": None})
        return summary

    supabase = _get_supabase_admin()
    if not supabase:
        logger.error("Supabase admin client not available (set SUPABASE_URL + SUPABASE_SERVICE_KEY)")
        return {**summary, "success": False, "error": "supabase_unavailable"}

    dsn = os.getenv("DB_DSN", "")
    if not dsn:
        logger.error("DB_DSN not set")
        return {**summary, "success": False, "error": "no_dsn"}

    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(dsn)

        for persona in PERSONAS:
            user_id = await _seed_one_user(supabase, conn, persona, pw)
            if user_id:
                summary["created"] += 1
                summary["users"].append({"email": persona.email, "handle": persona.handle, "user_id": user_id})
            else:
                summary["skipped"] += 1
                summary["users"].append({"email": persona.email, "handle": persona.handle, "user_id": None, "skipped": True})

    except Exception:
        logger.exception("Seed failed")
        summary["success"] = False
        summary["error"] = "seed_failed"
    finally:
        if conn is not None:
            await conn.close()

    return summary


async def _seed_one_user(
    supabase,
    conn: asyncpg.Connection,
    persona: Persona,
    password: str,
) -> str | None:
    """Create a single user and all related data. Returns user_id or None if skipped."""
    # 1. Create auth user (idempotent — check first)
    user_id = _find_or_create_auth_user(supabase, persona, password)
    if not user_id:
        return None

    # 2. Profile
    await conn.execute(
        """
        INSERT INTO profiles (id, username)
        VALUES ($1, $2)
        ON CONFLICT (id) DO NOTHING
        """,
        uuid.UUID(user_id),
        persona.handle,
    )

    # 3. Public profile
    await conn.execute(
        """
        INSERT INTO user_public_profiles (user_id, handle, display_name, bio, location, interests)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (user_id) DO NOTHING
        """,
        uuid.UUID(user_id),
        persona.handle,
        persona.display_name,
        persona.bio,
        persona.location,
        persona.interests,
    )

    # 4. User settings
    await conn.execute(
        """
        INSERT INTO user_settings (user_id, currency, region, locale)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO UPDATE SET
            currency = EXCLUDED.currency,
            region = EXCLUDED.region,
            locale = EXCLUDED.locale,
            updated_at = now()
        """,
        uuid.UUID(user_id),
        persona.currency,
        persona.region,
        persona.locale,
    )

    # 5. Personal items — items has no `sealed` or `attributes_json`
    # columns; sealed + grade/graded_by all live in attrs jsonb.
    for item in persona.items:
        attrs: dict = {}
        if item.get("grade"):
            attrs["grade"] = item["grade"]
        if item.get("graded_by"):
            attrs["graded_by"] = item["graded_by"]
        if item.get("sealed"):
            attrs["sealed"] = item.get("sealed", "").lower() == "true"

        await conn.execute(
            """
            INSERT INTO items (user_id, category, title, condition, attrs)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            uuid.UUID(user_id),
            item["category"],
            item["title"],
            item.get("condition"),
            json.dumps(attrs) if attrs else "{}",
        )

    logger.info("Seeded user %s <%s> (%s) with %d items",
                persona.handle, persona.email, user_id, len(persona.items))
    return user_id


def _find_or_create_auth_user(supabase, persona: Persona, password: str) -> str | None:
    """Check if user exists by email; create if not. Returns user_id string."""
    try:
        # List users filtered by email
        resp = supabase.auth.admin.list_users()
        existing = [u for u in resp if getattr(u, "email", None) == persona.email]
        if existing:
            uid = str(existing[0].id)
            logger.info("User %s already exists (%s) — skipping auth creation", persona.email, uid)
            return uid
    except Exception as e:
        logger.warning("Could not list users to check existence: %s", e)

    try:
        resp = supabase.auth.admin.create_user({
            "email": persona.email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"is_seed": True, "handle": persona.handle},
        })
        uid = str(resp.user.id)
        logger.info("Created auth user %s (%s)", persona.email, uid)
        return uid
    except Exception as e:
        logger.error("Failed to create auth user %s: %s", persona.email, e)
        return None


# ---------------------------------------------------------------------------
# Cleanup logic
# ---------------------------------------------------------------------------

# Same dependency order as account_router.py
_CLEANUP_TABLES = [
    "mandate_deals",
    "purchase_mandates",
    "alert_trigger_history",
    "user_price_alerts",
    "item_provenance_events",
    "watchlist",
    "price_predictions",
    "market_hits",
    "items",
    "user_category_ownership",
    "user_settings",
    "user_category_follows",
    "event_attendees",
    "profiles",
    "user_public_profiles",
]


async def cleanup_seed_users() -> dict:
    """Remove all users with user_metadata.is_seed = true.

    Returns {success, deleted, message}.
    """
    supabase = _get_supabase_admin()
    if not supabase:
        return {"success": False, "deleted": 0, "message": "Supabase admin client not available"}

    dsn = os.getenv("DB_DSN", "")
    if not dsn:
        return {"success": False, "deleted": 0, "message": "DB_DSN not set"}

    # Find seed users
    try:
        resp = supabase.auth.admin.list_users()
        seed_users = [
            u for u in resp
            if getattr(u, "user_metadata", None)
            and u.user_metadata.get("is_seed") is True
        ]
    except Exception as e:
        return {"success": False, "deleted": 0, "message": f"Failed to list users: {e}"}

    if not seed_users:
        return {"success": True, "deleted": 0, "message": "No seed users found"}

    conn: asyncpg.Connection | None = None
    deleted = 0
    try:
        conn = await asyncpg.connect(dsn)

        for user in seed_users:
            uid = uuid.UUID(str(user.id))

            async with conn.transaction():
                for table in _CLEANUP_TABLES:
                    col = "id" if table == "profiles" else "user_id"
                    try:
                        await conn.execute(
                            f"DELETE FROM {table} WHERE {col} = $1",  # noqa: S608
                            uid,
                        )
                    except asyncpg.UndefinedTableError:
                        pass

            # Remove from Supabase Auth
            try:
                supabase.auth.admin.delete_user(str(user.id))
                logger.info("Deleted seed user %s (%s)", getattr(user, "email", "?"), user.id)
                deleted += 1
            except Exception as e:
                logger.error("Failed to delete auth user %s: %s", user.id, e)

    except Exception as e:
        return {"success": False, "deleted": deleted, "message": f"Cleanup error: {e}"}
    finally:
        if conn is not None:
            await conn.close()

    return {"success": True, "deleted": deleted, "message": f"Removed {deleted} seed user(s)"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed 8 beta-test users with realistic collector personas.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating anything")
    parser.add_argument("--cleanup", action="store_true", help="Remove all seed users")
    parser.add_argument("--password", default=None, help="Override default password")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    _setup_logging(args.log_level)

    if args.cleanup:
        result = asyncio.run(cleanup_seed_users())
    else:
        result = asyncio.run(seed_users(dry_run=args.dry_run, password=args.password))

    if not result.get("success", False):
        logger.error("Operation failed: %s", result.get("error") or result.get("message"))
        sys.exit(1)

    logger.info("Result: %s", json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
