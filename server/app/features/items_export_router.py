from __future__ import annotations

import csv
import io
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.auth import get_current_user_id
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

router = APIRouter(prefix="/items-export", tags=["Items Export"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class ItemsExportResponse(BaseModel):
    download_url: Optional[str] = None
    csv_inline: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Round-trip 12-col schema — must match IMPORT_COLUMNS in import_router.py.
# Used by /overview so a user can export → edit → re-import. Last change 2026-04-29.
EXPORT_COLUMNS = [
    "name", "category", "condition", "grade", "graded_by", "sealed",
    "purchase_price", "purchase_currency", "purchase_date",
    "estimated_value", "currency", "notes",
]
EMPTY_CSV = ",".join(EXPORT_COLUMNS) + "\n"

# Comprehensive "inventory overview" schema for /full. NOT round-trip —
# adds attribute columns + price-prediction range + ownership flags. Use
# this for insurance, accountants, or any "snapshot of my collection"
# scenario. Image URLs intentionally excluded per design decision.
FULL_EXPORT_COLUMNS = [
    "item_id",            # canonical_key for cross-reference
    "name",
    "category",
    "brand",              # from attrs.brand
    "set_or_series",      # from attrs.set or attrs.series
    "edition",            # items.edition_label (already a column)
    "rarity",             # from attrs.rarity
    "variant",            # items.variant_key
    "serial_number",      # items.serial_number
    "limited_edition",    # is_limited_edition + limited_edition_number/total
    "first_edition",      # items.is_first_edition (yes/no)
    "quantity",           # items.quantity
    "condition",
    "grade",              # condition_grade
    "graded_by",
    "sealed",
    "purchase_price",
    "purchase_currency",
    "purchase_date",
    "estimated_value",    # converted to display_currency
    "estimated_value_low",  # q10 from price_predictions
    "estimated_value_high", # q90 from price_predictions
    "currency",           # display currency (matches estimated_value/_low/_high)
    "for_sale",
    "asking_price",
    "asking_currency",
    "collection_name",    # user-defined collection grouping
    "notes",
    "added_at",           # items.created_at
    "updated_at",         # items.updated_at
]
FULL_EMPTY_CSV = ",".join(FULL_EXPORT_COLUMNS) + "\n"

# Currencies the FE supports per memory + theme. Anything else falls back
# to EUR with a log warning.
SUPPORTED_CURRENCIES = {"EUR", "USD", "GBP", "JPY", "KRW", "AUD", "CAD"}


def _bool_to_str(v: Any) -> str:
    """attrs.sealed and similar bools render as yes/no for spreadsheet
    friendliness. Matches the example rows in the import template.
    """
    if v is True:
        return "yes"
    if v is False:
        return "no"
    return ""


async def _resolve_display_currency(conn, user_id: str, override: Optional[str]) -> str:
    """Pick the currency the export's value columns should be denominated in.

    Priority:
      1. ?currency= query param (if provided + supported)
      2. user_settings.currency for this user
      3. EUR (server-side storage default)
    """
    if override:
        c = override.strip().upper()
        if c in SUPPORTED_CURRENCIES:
            return c
        logger.warning("[items-export] unsupported currency override: %s", override)
    try:
        row = await conn.fetchrow(
            "SELECT currency FROM user_settings WHERE user_id = $1",
            user_id,
        )
        if row and row["currency"]:
            c = str(row["currency"]).strip().upper()
            if c in SUPPORTED_CURRENCIES:
                return c
    except Exception as e:
        logger.debug("[items-export] user_settings lookup failed: %s", e)
    return "EUR"


async def _eur_to_display_factor(display_currency: str) -> float:
    """How many `display_currency` units per 1 EUR. Returns 1.0 for EUR
    or any FX failure (safe default — under-converts rather than blowing
    up the whole export).
    """
    if display_currency == "EUR":
        return 1.0
    try:
        from app.lib.fx_service import get_rates_from_eur
        rates = await get_rates_from_eur()
        return float(rates.get(display_currency, 1.0))
    except Exception as e:
        logger.warning("[items-export] FX lookup failed (%s); falling back to EUR", e)
        return 1.0


def _fmt_money(amount: Optional[float], factor: float = 1.0) -> str:
    """Format a numeric money value with 2 decimals, applying FX factor.
    Empty string for None — matches the import template's empty-cell convention.
    """
    if amount is None:
        return ""
    try:
        return f"{float(amount) * factor:.2f}"
    except (ValueError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=ItemsExportResponse)
async def export_items_overview(
    user_id: str = Depends(get_current_user_id),
    currency: Optional[str] = Query(
        None,
        description=(
            "Override display currency for estimated_value (EUR/USD/GBP/JPY/KRW/AUD/CAD). "
            "If omitted, falls back to user_settings.currency, then EUR."
        ),
    ),
    _rl=Depends(per_user_rate_limit(5, window_seconds=60, scope="items_export")),
) -> ItemsExportResponse:
    """Round-trip CSV export — 12 columns matching the import template.

    Columns match IMPORT_COLUMNS so a user can export → edit in Excel → re-import.
    estimated_value falls back to the latest q50 prediction when the user hasn't
    set a manual estimate. graded_by + sealed surface from items.attrs (no
    dedicated columns).

    `currency`: previously hardcoded to "EUR"; now respects the user's
    preferred currency (`user_settings.currency`) or an explicit `?currency=`
    override. estimated_value is FX-converted from its EUR storage to match.
    purchase_price is left in its purchase_currency (no conversion — that
    field reflects the historical price the user paid).
    """
    pool = get_db_pool()
    if not pool:
        return ItemsExportResponse(download_url=None, csv_inline=EMPTY_CSV)

    try:
        async with pool.acquire() as conn:
            display_currency = await _resolve_display_currency(conn, user_id, currency)
            factor = await _eur_to_display_factor(display_currency)

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
                    -- Partition prune: latest prediction is always within
                    -- the last 60 days. The LATERAL fires once per item
                    -- so without this filter export of a 100-item
                    -- collection walks all partitions 100 times.
                    SELECT q50
                    FROM price_predictions
                    WHERE item_ref = i.canonical_ref
                      AND generated_at > now() - interval '60 days'
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
                    _fmt_money(row["purchase_price"]),  # purchase_price stays in its own currency
                    row["purchase_currency"],
                    row["purchase_date"].isoformat() if row["purchase_date"] else "",
                    _fmt_money(row["estimated_value"], factor),
                    display_currency,
                    row["notes"],
                ])

            return ItemsExportResponse(
                download_url=None,
                csv_inline=buf.getvalue(),
            )

    except Exception as e:
        logger.error("[items-export/overview] DB error: %s", e)
        return ItemsExportResponse(download_url=None, csv_inline=EMPTY_CSV)


@router.get("/full", response_model=ItemsExportResponse)
async def export_items_full(
    user_id: str = Depends(get_current_user_id),
    currency: Optional[str] = Query(
        None,
        description=(
            "Display currency for estimated_value, low, high. "
            "EUR/USD/GBP/JPY/KRW/AUD/CAD."
        ),
    ),
    _rl=Depends(per_user_rate_limit(5, window_seconds=60, scope="items_export_full")),
) -> ItemsExportResponse:
    """Comprehensive inventory snapshot — 30 columns covering every
    user-facing detail except images.

    Use this for insurance, accountants, or any "snapshot of my collection"
    scenario. NOT a round-trip CSV (re-importing this would silently drop
    the extra columns since the import handler only knows the 12-col schema).

    What's included:
      - Item ID (canonical_key) for cross-reference
      - Brand, set, edition, rarity, variant, serial_number from items.attrs
      - Quantity, limited-edition + first-edition flags
      - Estimated value range (q10/q50/q90) in user's currency
      - For-sale flag + asking price + asking currency
      - Collection grouping
      - Created / updated timestamps

    What's NOT included:
      - Image URLs (per product decision — CSV isn't the right delivery
        for images; FE has the dossier flow for that).

    Run rate-limited at 5/min per user; not a hot path.
    """
    pool = get_db_pool()
    if not pool:
        return ItemsExportResponse(download_url=None, csv_inline=FULL_EMPTY_CSV)

    try:
        async with pool.acquire() as conn:
            display_currency = await _resolve_display_currency(conn, user_id, currency)
            factor = await _eur_to_display_factor(display_currency)

            rows = await conn.fetch(
                """
                SELECT
                    COALESCE(i.canonical_key, i.id::text)    AS item_id,
                    COALESCE(i.title, i.canonical_key, '')   AS name,
                    COALESCE(i.category, '')                 AS category,
                    COALESCE(i.attrs->>'brand', '')          AS brand,
                    COALESCE(
                        i.attrs->>'set',
                        i.attrs->>'set_name',
                        i.attrs->>'series',
                        ''
                    )                                        AS set_or_series,
                    COALESCE(i.edition_label, '')            AS edition,
                    COALESCE(i.attrs->>'rarity', '')         AS rarity,
                    COALESCE(i.variant_key, '')              AS variant,
                    COALESCE(i.serial_number, '')            AS serial_number,
                    i.is_limited_edition                     AS le_flag,
                    i.limited_edition_number                 AS le_num,
                    i.limited_edition_total                  AS le_total,
                    i.is_first_edition                       AS first_edition_flag,
                    COALESCE(i.quantity, 1)                  AS quantity,
                    COALESCE(i.condition, '')                AS condition,
                    COALESCE(i.condition_grade, '')          AS grade,
                    COALESCE(i.attrs->>'graded_by', '')      AS graded_by,
                    i.attrs->>'sealed'                       AS sealed_raw,
                    i.purchase_price,
                    COALESCE(i.purchase_currency, '')        AS purchase_currency,
                    i.purchase_date,
                    COALESCE(i.estimated_value, pp.q50)      AS estimated_value,
                    pp.q10                                   AS estimated_value_low,
                    pp.q90                                   AS estimated_value_high,
                    COALESCE(i.for_sale, FALSE)              AS for_sale,
                    i.asking_price,
                    COALESCE(i.asking_currency, '')          AS asking_currency,
                    COALESCE(i.collection_name, '')          AS collection_name,
                    COALESCE(i.notes, '')                    AS notes,
                    i.created_at                             AS added_at,
                    i.updated_at                             AS updated_at
                FROM items i
                LEFT JOIN LATERAL (
                    SELECT q10, q50, q90
                    FROM price_predictions
                    WHERE item_ref = i.canonical_ref
                      AND generated_at > now() - interval '60 days'
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
            writer.writerow(FULL_EXPORT_COLUMNS)

            for row in rows:
                sealed_bool: Optional[bool] = None
                sr = row["sealed_raw"]
                if sr in ("true", "True"):
                    sealed_bool = True
                elif sr in ("false", "False"):
                    sealed_bool = False

                # Limited edition: collapse the three columns into one
                # human-readable string. "23 / 1000" / "yes" / "" depending
                # on what's populated.
                le_flag = row["le_flag"]
                le_num = row["le_num"]
                le_total = row["le_total"]
                if le_num and le_total:
                    le_str = f"{le_num} / {le_total}"
                elif le_flag:
                    le_str = "yes"
                else:
                    le_str = ""

                writer.writerow([
                    row["item_id"],
                    row["name"],
                    row["category"],
                    row["brand"],
                    row["set_or_series"],
                    row["edition"],
                    row["rarity"],
                    row["variant"],
                    row["serial_number"],
                    le_str,
                    _bool_to_str(row["first_edition_flag"]),
                    row["quantity"],
                    row["condition"],
                    row["grade"],
                    row["graded_by"],
                    _bool_to_str(sealed_bool),
                    _fmt_money(row["purchase_price"]),
                    row["purchase_currency"],
                    row["purchase_date"].isoformat() if row["purchase_date"] else "",
                    _fmt_money(row["estimated_value"], factor),
                    _fmt_money(row["estimated_value_low"], factor),
                    _fmt_money(row["estimated_value_high"], factor),
                    display_currency,
                    _bool_to_str(row["for_sale"]),
                    _fmt_money(row["asking_price"]),
                    row["asking_currency"],
                    row["collection_name"],
                    row["notes"],
                    row["added_at"].isoformat() if row["added_at"] else "",
                    row["updated_at"].isoformat() if row["updated_at"] else "",
                ])

            return ItemsExportResponse(
                download_url=None,
                csv_inline=buf.getvalue(),
            )

    except Exception as e:
        logger.error("[items-export/full] DB error: %s", e)
        return ItemsExportResponse(download_url=None, csv_inline=FULL_EMPTY_CSV)
