"""
Duplicate and variant detection for QuickScan.

Checks if a scanned item is already owned by the user, is a variant
of an owned item, or contributes to set completion.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def check_user_duplicates(
    user_id: Optional[str],
    category_id: Optional[str],
    normalized_key: Optional[str],
    catalog_match_key: Optional[str],
    pool,
) -> dict[str, Any]:
    """
    Check if the scanned item is already in the user's collection.

    Returns:
        {
            "owned_count": int,
            "owned_item_ids": [str],
            "is_variant": bool,
            "variant_of": str | None,
            "set_completion": {"owned": int, "total": int, "pct": float} | None
        }
    """
    result: dict[str, Any] = {
        "owned_count": 0,
        "owned_item_ids": [],
        "is_variant": False,
        "variant_of": None,
        "set_completion": None,
    }

    if not pool or not user_id or not category_id:
        return result

    search_key = catalog_match_key or normalized_key
    if not search_key:
        return result

    try:
        async with pool.acquire() as conn:
            # Exact match: items WHERE user_id AND normalized_key
            try:
                rows = await conn.fetch(
                    """
                    SELECT id, title, canonical_key AS normalized_key
                    FROM items
                    WHERE user_id = $1::uuid
                      AND category = $2
                      AND canonical_key ILIKE $3
                    LIMIT 5
                    """,
                    user_id,
                    category_id,
                    f"%{search_key[:80]}%",
                )
                if rows:
                    result["owned_count"] = len(rows)
                    result["owned_item_ids"] = [str(r["id"]) for r in rows]
            except Exception as e:
                logger.debug("Duplicate exact match error: %s", e)

            # Variant detection: fuzzy match on first 3 tokens within same category
            if result["owned_count"] == 0 and search_key:
                try:
                    tokens = search_key.lower().split()[:3]
                    if len(tokens) >= 2:
                        fuzzy_pattern = f"%{' '.join(tokens)}%"
                        rows = await conn.fetch(
                            """
                            SELECT id, title, canonical_key AS normalized_key
                            FROM items
                            WHERE user_id = $1::uuid
                              AND category = $2
                              AND canonical_key ILIKE $3
                            LIMIT 3
                            """,
                            user_id,
                            category_id,
                            fuzzy_pattern,
                        )
                        if rows:
                            result["is_variant"] = True
                            result["variant_of"] = rows[0]["title"]
                except Exception as e:
                    logger.debug("Duplicate variant detection error: %s", e)

            # Set completion: how many items in this category does user own vs total catalog
            try:
                owned_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM items WHERE user_id = $1::uuid AND category = $2",
                    user_id,
                    category_id,
                )
                total_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM category_items WHERE category = $1",
                    category_id,
                )
                if total_count and total_count > 0:
                    result["set_completion"] = {
                        "owned": owned_count or 0,
                        "total": total_count,
                        "pct": round((owned_count or 0) / total_count * 100, 1),
                    }
            except Exception as e:
                logger.debug("Duplicate set completion error: %s", e)

    except Exception as e:
        logger.warning("Duplicate check error: %s", e)

    return result
