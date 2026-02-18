"""
Taxonomy Registry Router.

Provides read-only API access to the versioned taxonomy registry
for frontend category dropdowns and taxonomy management.
"""

import logging
from typing import Optional

from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.cache import cache_get, cache_set
from app.db import db_configured, get_conn
from app.errors import error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])

# Cache TTL for taxonomy data (changes very rarely)
_TAXONOMY_TTL = 3600  # 1 hour


@router.get("/current")
async def taxonomy_current():
    """Return the current (latest non-deprecated) taxonomy version with all categories."""
    cached = cache_get("taxonomy:current")
    if cached is not None:
        return JSONResponse(content=cached, headers={"Cache-Control": "public, max-age=3600", "X-Cache": "HIT"})

    if not db_configured():
        return _fallback_taxonomy()

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT version, categories, mapping_rules, effective_from, notes
                FROM public.taxonomy_registry
                WHERE deprecated_at IS NULL
                ORDER BY effective_from DESC
                LIMIT 1
                """
            )

        if not row:
            return _fallback_taxonomy()

        result = {
            "version": row["version"],
            "categories": row["categories"],
            "mapping_rules_count": len(row["mapping_rules"]) if row["mapping_rules"] else 0,
            "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
            "notes": row["notes"],
        }
        cache_set("taxonomy:current", result, ttl=_TAXONOMY_TTL)
        return JSONResponse(content=result, headers={"Cache-Control": "public, max-age=3600", "X-Cache": "MISS"})
    except (OSError, RuntimeError, Exception) as exc:
        logger.warning("Failed to fetch taxonomy from DB, using fallback: %s", exc, exc_info=True)
        return _fallback_taxonomy()


@router.get("/versions")
async def taxonomy_versions():
    """Return list of all taxonomy versions with metadata."""
    if not db_configured():
        return {"versions": [{"version": "v1.0", "status": "active"}]}

    try:
        async with get_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT version, effective_from, deprecated_at,
                       migration_from, notes, created_by
                FROM public.taxonomy_registry
                ORDER BY effective_from DESC
                """
            )

        return {
            "versions": [
                {
                    "version": r["version"],
                    "effective_from": r["effective_from"].isoformat() if r["effective_from"] else None,
                    "deprecated_at": r["deprecated_at"].isoformat() if r["deprecated_at"] else None,
                    "status": "deprecated" if r["deprecated_at"] else "active",
                    "migration_from": r["migration_from"],
                    "notes": r["notes"],
                    "created_by": r["created_by"],
                }
                for r in rows
            ]
        }
    except (OSError, RuntimeError, Exception) as exc:
        logger.warning("Failed to fetch taxonomy versions: %s", exc, exc_info=True)
        return {"versions": [{"version": "v1.0", "status": "active"}]}


@router.get("/categories")
async def taxonomy_categories():
    """Return flat list of categories for the current taxonomy version (for UI dropdowns)."""
    cached = cache_get("taxonomy:categories")
    if cached is not None:
        return JSONResponse(content=cached, headers={"Cache-Control": "public, max-age=3600", "X-Cache": "HIT"})

    if not db_configured():
        return {"version": "v1.0", "categories": _fallback_category_list()}

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT version, categories
                FROM public.taxonomy_registry
                WHERE deprecated_at IS NULL
                ORDER BY effective_from DESC
                LIMIT 1
                """
            )

        if not row or not row["categories"]:
            return {"version": "v1.0", "categories": _fallback_category_list()}

        cats = row["categories"]
        flat = [
            {
                "category_id": c.get("category_id"),
                "display_name": c.get("display_name", c.get("category_id", "")),
                "subtypes": [s.get("id") for s in c.get("subtypes", [])],
                "collections": c.get("collections", []),
            }
            for c in cats
        ]
        result = {"version": row["version"], "categories": flat}
        cache_set("taxonomy:categories", result, ttl=_TAXONOMY_TTL)
        return JSONResponse(content=result, headers={"Cache-Control": "public, max-age=3600", "X-Cache": "MISS"})
    except (OSError, RuntimeError, Exception) as exc:
        logger.warning("Failed to fetch categories from registry: %s", exc, exc_info=True)
        return {"version": "v1.0", "categories": _fallback_category_list()}


@router.get("/{version}")
async def taxonomy_by_version(version: str):
    """Return specific taxonomy version details."""
    if not db_configured():
        raise error_response(503, "Database not configured", code="DB_NOT_CONFIGURED")

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow(
                """
                SELECT version, categories, mapping_rules, effective_from,
                       deprecated_at, migration_from, migration_rules, notes, created_by
                FROM public.taxonomy_registry
                WHERE version = $1
                """,
                version,
            )

        if not row:
            raise error_response(404, "Taxonomy version not found", code="TAXONOMY_NOT_FOUND")

        return {
            "version": row["version"],
            "categories": row["categories"],
            "mapping_rules": row["mapping_rules"],
            "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
            "deprecated_at": row["deprecated_at"].isoformat() if row["deprecated_at"] else None,
            "migration_from": row["migration_from"],
            "migration_rules": row["migration_rules"],
            "notes": row["notes"],
            "created_by": row["created_by"],
        }
    except Exception:
        logger.exception("Failed to fetch taxonomy version %s", version)
        raise error_response(500, "Failed to fetch taxonomy", code="TAXONOMY_FETCH_ERROR")


# ---------------------------------------------------------------------------
# Fallback data (when DB is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK_CATEGORIES = [
    # TCGs (4)
    "pokemon", "mtg", "yugioh", "lorcana",
    # Toys / Figures (4)
    "funko", "designer_toys", "anime_figures", "hot_toys",
    # Building / Models (4)
    "lego", "gunpla", "scale_models", "warhammer",
    # Gaming (1)
    "retro_games",
    # Media (5)
    "manga", "bluray_steelbook", "anime_bluray", "anime_soundtrack", "anime_ost_vinyl",
    # Music / Fandom (4)
    "kpop_merch", "taylor_swift", "pop_fandom", "kpop_lightsticks",
    # Disney / Theme Parks (3)
    "disney", "theme_park", "ghibli",
    # Japan Exclusives (3)
    "bandai_premium", "jp_magazine", "jp_event",
    # Nintendo / Pokemon Merch (2)
    "nintendo_merch", "retro_pokemon",
    # IP-Specific (2)
    "one_piece", "vtuber",
    # Niche (2)
    "keycaps", "loungefly",
    # Legacy (3)
    "diecast", "sportscards", "retro_handhelds",
]


def _fallback_taxonomy():
    return {
        "version": "v1.0",
        "categories": [{"category_id": c, "display_name": c.replace("_", " ").title()} for c in _FALLBACK_CATEGORIES],
        "mapping_rules_count": 0,
        "effective_from": None,
        "notes": "Fallback — database unavailable",
    }


def _fallback_category_list():
    return [
        {"category_id": c, "display_name": c.replace("_", " ").title(), "subtypes": [], "collections": []}
        for c in _FALLBACK_CATEGORIES
    ]
