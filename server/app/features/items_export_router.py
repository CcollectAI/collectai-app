from __future__ import annotations

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/items-export", tags=["Items Export"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response model (unchanged)
# ---------------------------------------------------------------------------

class ItemsExportResponse(BaseModel):
    download_url: Optional[str] = None
    csv_inline: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=ItemsExportResponse)
async def export_items_overview(
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(5, scope="items_export")),
) -> ItemsExportResponse:
    """
    Export the authenticated user's items as inline CSV.

    Columns: id, title, category, condition, grade, estimated_value, currency
    estimated_value is the latest q50 from price_predictions (if available).
    """
    pool = get_db_pool()
    if not pool:
        # No DB -- return empty CSV with header only
        return ItemsExportResponse(
            download_url=None,
            csv_inline="id,title,category,condition,grade,estimated_value,currency\n",
        )

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    i.id,
                    COALESCE(i.title, i.normalized_key, '') AS title,
                    COALESCE(i.category, '')                 AS category,
                    COALESCE(i.condition, '')                AS condition,
                    COALESCE(i.grade, '')                    AS grade,
                    pp.q50                                   AS estimated_value
                FROM items i
                LEFT JOIN LATERAL (
                    SELECT q50
                    FROM price_predictions
                    WHERE item_id = i.id
                    ORDER BY asof DESC
                    LIMIT 1
                ) pp ON true
                WHERE i.user_id = $1
                ORDER BY i.category, i.title
                """,
                user_id,
            )

            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "title", "category", "condition", "grade", "estimated_value", "currency"])

            for row in rows:
                writer.writerow([
                    str(row["id"]),
                    row["title"],
                    row["category"],
                    row["condition"],
                    row["grade"],
                    f"{float(row['estimated_value']):.2f}" if row["estimated_value"] is not None else "",
                    "EUR",
                ])

            return ItemsExportResponse(
                download_url=None,
                csv_inline=buf.getvalue(),
            )

    except Exception as e:
        logger.error(f"[items-export/overview] DB error: {e}")
        return ItemsExportResponse(
            download_url=None,
            csv_inline="id,title,category,condition,grade,estimated_value,currency\n",
        )
