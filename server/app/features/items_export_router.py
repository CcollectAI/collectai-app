from __future__ import annotations

import csv
import io
import logging
from typing import Any, Optional

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

# Canonical 12-column schema — must match IMPORT_COLUMNS in import_router.py
# so a user can export → edit → re-import. Last change 2026-04-29.
EXPORT_COLUMNS = [
    "name", "category", "condition", "grade", "graded_by", "sealed",
    "purchase_price", "purchase_currency", "purchase_date",
    "estimated_value", "currency", "notes",
]
EMPTY_CSV = ",".join(EXPORT_COLUMNS) + "\n"


def _bool_to_str(v: Any) -> str:
    """attrs.sealed is stored as a real bool; emit yes/no in CSV so
    spreadsheet apps don't render it as TRUE/FALSE in caps. yes/no
    also matches the example rows in the import template."""
    if v is True:
        return "yes"
    if v is False:
        return "no"
    return ""


@router.get("/overview", response_model=ItemsExportResponse)
async def export_items_overview(
    user_id: str = Depends(get_current_user_id),
    _rl=Depends(per_user_rate_limit(5, window_seconds=60, scope="items_export")),
) -> ItemsExportResponse:
    """Export the authenticated user's items as inline CSV.

    Columns match the import template (see IMPORT_COLUMNS) so round-trips
    work. estimated_value falls back to the latest q50 prediction when the
    user hasn't set a manual estimate. graded_by + sealed live in
    items.attrs (the items table has no dedicated columns).
    """
    pool = get_db_pool()
    if not pool:
        return ItemsExportResponse(download_url=None, csv_inline=EMPTY_CSV)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    COALESCE(i.title, i.canonical_key, '')   AS name,
                    COALESCE(i.category, '')                 AS category,
                    COALESCE(i.condition, '')                AS condition,
                    COALESCE(i.condition_grade, '')          AS grade,
                    COALESCE(i.attrs->>'graded_by', '') AS graded_by,
                    i.attrs->>'sealed'             AS sealed_raw,
                    i.purchase_price,
                    COALESCE(i.purchase_currency, '')        AS purchase_currency,
                    i.purchase_date,
                    COALESCE(i.estimated_value, pp.q50)      AS estimated_value,
                    COALESCE(i.notes, '')                    AS notes
                FROM items i
                LEFT JOIN LATERAL (
                    -- price_predictions canonical join uses item_ref +
                    -- generated_at (learnings.md §42).
                    SELECT q50
                    FROM price_predictions
                    WHERE item_ref = i.canonical_key
                    ORDER BY generated_at DESC
                    LIMIT 1
                ) pp ON true
                WHERE i.user_id = $1
                ORDER BY i.category, i.title
                """,
                user_id,
            )

            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(EXPORT_COLUMNS)

            for row in rows:
                # sealed_raw comes back as 'true'/'false' string from
                # jsonb->>; convert to yes/no via the bool indirection.
                sealed_bool: Optional[bool] = None
                sr = row["sealed_raw"]
                if sr in ("true", "True"):
                    sealed_bool = True
                elif sr in ("false", "False"):
                    sealed_bool = False

                writer.writerow([
                    row["name"],
                    row["category"],
                    row["condition"],
                    row["grade"],
                    row["graded_by"],
                    _bool_to_str(sealed_bool),
                    f"{float(row['purchase_price']):.2f}" if row["purchase_price"] is not None else "",
                    row["purchase_currency"],
                    row["purchase_date"].isoformat() if row["purchase_date"] else "",
                    f"{float(row['estimated_value']):.2f}" if row["estimated_value"] is not None else "",
                    "EUR",
                    row["notes"],
                ])

            return ItemsExportResponse(
                download_url=None,
                csv_inline=buf.getvalue(),
            )

    except Exception as e:
        logger.error("[items-export/overview] DB error: %s", e)
        return ItemsExportResponse(download_url=None, csv_inline=EMPTY_CSV)
