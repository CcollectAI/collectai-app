"""
Insurance valuation PDF/HTML export router.

Generates a professional insurance valuation report for a user's collection.

Endpoints:
- GET /export/insurance-report   — Generate insurance valuation report (HTML or JSON)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.auth import get_current_user_id
from app.db import db_configured
from app.errors import error_response
from app.lib.db_helpers import get_db_pool
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])

# Rate limit: 5 report generations per hour per user
_export_limit = per_user_rate_limit(5, window_seconds=3600, scope="insurance_export")

# Supported currency codes
_ALLOWED_CURRENCIES = {"EUR", "USD", "GBP", "JPY", "KRW", "AUD", "CAD"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class InsuranceItemRow(BaseModel):
    id: str
    name: str
    category: str
    condition: str
    grade: str
    estimated_value: float | None = None
    currency: str = "EUR"
    image_url: str | None = None
    date_acquired: str | None = None


class InsuranceReportData(BaseModel):
    generated_at: str
    user_email: str | None = None
    user_name: str | None = None
    total_items: int
    total_estimated_value: float
    currency: str
    methodology: str
    items: list[InsuranceItemRow]


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------


def _render_html_report(data: InsuranceReportData) -> str:
    """Render the insurance valuation report as a print-friendly HTML page."""

    # Build item rows
    item_rows = ""
    for i, item in enumerate(data.items, 1):
        img_cell = ""
        if item.image_url:
            safe_url = _escape_html(item.image_url)
            img_cell = f'<img src="{safe_url}" alt="" style="width:48px;height:48px;object-fit:cover;border-radius:4px;" />'
        else:
            img_cell = '<div style="width:48px;height:48px;background:#f0f0f0;border-radius:4px;display:flex;align-items:center;justify-content:center;color:#999;font-size:10px;">N/A</div>'

        val_display = f"{data.currency} {item.estimated_value:,.2f}" if item.estimated_value is not None else "N/A"
        date_display = item.date_acquired or "N/A"
        condition_display = item.condition or "N/A"
        grade_display = item.grade or "N/A"

        item_rows += f"""
        <tr>
            <td style="text-align:center;">{i}</td>
            <td>{img_cell}</td>
            <td><strong>{_escape_html(item.name)}</strong><br/><span style="color:#666;font-size:12px;">{_escape_html(item.category)}</span></td>
            <td>{_escape_html(condition_display)}</td>
            <td>{_escape_html(grade_display)}</td>
            <td style="text-align:right;font-weight:600;">{val_display}</td>
            <td>{date_display}</td>
        </tr>"""

    total_display = f"{data.currency} {data.total_estimated_value:,.2f}"
    gen_date = datetime.fromisoformat(data.generated_at.replace("Z", "+00:00")).strftime("%B %d, %Y at %H:%M UTC")
    user_display = data.user_name or data.user_email or "CollectAI User"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Collection Insurance Valuation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            color: #1a1a1a;
            background: #ffffff;
            padding: 40px;
            max-width: 1000px;
            margin: 0 auto;
        }}
        @media print {{
            body {{ padding: 20px; }}
            .no-print {{ display: none !important; }}
            table {{ page-break-inside: auto; }}
            tr {{ page-break-inside: avoid; }}
        }}
        .header {{
            text-align: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 3px solid #81D8D0;
        }}
        .header h1 {{
            font-size: 28px;
            color: #1a1a1a;
            margin-bottom: 8px;
        }}
        .header .subtitle {{
            color: #666;
            font-size: 14px;
        }}
        .header .logo-text {{
            color: #81D8D0;
            font-weight: 700;
            font-size: 16px;
            margin-bottom: 16px;
        }}
        .summary {{
            display: flex;
            gap: 20px;
            margin-bottom: 32px;
            flex-wrap: wrap;
        }}
        .summary-card {{
            flex: 1;
            min-width: 200px;
            background: #f8fffe;
            border: 1px solid #e0f5f3;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}
        .summary-card .label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        .summary-card .value {{
            font-size: 24px;
            font-weight: 700;
            color: #1a1a1a;
        }}
        .summary-card .value.accent {{
            color: #81D8D0;
        }}
        .info-box {{
            background: #f9f9f9;
            border: 1px solid #e5e5e5;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 24px;
            font-size: 13px;
            color: #666;
            line-height: 1.6;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 32px;
        }}
        thead th {{
            background: #f5f5f5;
            padding: 12px 10px;
            text-align: left;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            color: #666;
            border-bottom: 2px solid #ddd;
        }}
        tbody td {{
            padding: 12px 10px;
            border-bottom: 1px solid #eee;
            font-size: 13px;
            vertical-align: middle;
        }}
        tbody tr:hover {{
            background: #fafafa;
        }}
        .total-row {{
            font-size: 18px;
            font-weight: 700;
            text-align: right;
            padding: 16px 0;
            border-top: 3px solid #81D8D0;
            margin-top: 8px;
        }}
        .methodology {{
            margin-top: 24px;
            padding: 16px;
            background: #f9f9f9;
            border-radius: 8px;
            font-size: 12px;
            color: #888;
            line-height: 1.6;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #eee;
            font-size: 11px;
            color: #aaa;
        }}
        .print-btn {{
            display: inline-block;
            background: #81D8D0;
            color: #fff;
            padding: 12px 32px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            border: none;
            margin: 16px auto;
        }}
        .print-btn:hover {{
            background: #6bc9c1;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo-text">CollectAI</div>
        <h1>Collection Insurance Valuation Report</h1>
        <div class="subtitle">Prepared for {_escape_html(user_display)} &middot; {gen_date}</div>
    </div>

    <div class="no-print" style="text-align:center;margin-bottom:24px;">
        <button class="print-btn" onclick="window.print()">Print / Save as PDF</button>
    </div>

    <div class="summary">
        <div class="summary-card">
            <div class="label">Total Items</div>
            <div class="value">{data.total_items}</div>
        </div>
        <div class="summary-card">
            <div class="label">Total Estimated Value</div>
            <div class="value accent">{total_display}</div>
        </div>
        <div class="summary-card">
            <div class="label">Report Date</div>
            <div class="value" style="font-size:16px;">{datetime.fromisoformat(data.generated_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')}</div>
        </div>
    </div>

    <div class="info-box">
        <strong>Important:</strong> This report provides estimated market values based on recent
        comparable sales data and algorithmic price predictions. Values are approximate and should
        be reviewed by a qualified appraiser for official insurance purposes. Actual insurance
        coverage amounts should be determined in consultation with your insurance provider.
    </div>

    <table>
        <thead>
            <tr>
                <th style="width:40px;">#</th>
                <th style="width:60px;">Photo</th>
                <th>Item</th>
                <th style="width:100px;">Condition</th>
                <th style="width:80px;">Grade</th>
                <th style="width:130px;text-align:right;">Est. Value</th>
                <th style="width:100px;">Acquired</th>
            </tr>
        </thead>
        <tbody>
            {item_rows}
        </tbody>
    </table>

    <div class="total-row">
        Total Estimated Value: {total_display}
    </div>

    <div class="methodology">
        <strong>Methodology:</strong> {_escape_html(data.methodology)}
    </div>

    <div class="footer">
        <p>Generated by CollectAI &middot; {gen_date}</p>
        <p>This document is for informational purposes only and does not constitute a formal appraisal.</p>
    </div>
</body>
</html>"""


def _escape_html(text: str) -> str:
    """Basic HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/insurance-report")
async def export_insurance_report(
    format: str = Query(default="html", pattern="^(html|json)$", description="Output format: html or json"),
    currency: str = Query(default="EUR", description="Currency code"),
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_export_limit),
):
    """
    Generate an insurance valuation report for the authenticated user's collection.

    - `?format=html` (default) — Returns a print-friendly HTML page that can be saved as PDF
    - `?format=json` — Returns raw JSON data for programmatic use
    """
    # Validate currency against allowlist to prevent XSS via currency param
    if currency not in _ALLOWED_CURRENCIES:
        raise error_response(400, f"Unsupported currency: {currency}. Supported: {', '.join(sorted(_ALLOWED_CURRENCIES))}", code="INVALID_CURRENCY")

    now = datetime.now(timezone.utc).isoformat()

    pool = get_db_pool()
    if not pool:
        # No DB — return empty report
        data = InsuranceReportData(
            generated_at=now,
            total_items=0,
            total_estimated_value=0.0,
            currency=currency,
            methodology="No database connection available. This is a placeholder report.",
            items=[],
        )
        if format == "json":
            return JSONResponse(content=data.model_dump())
        return HTMLResponse(content=_render_html_report(data))

    try:
        async with pool.acquire() as conn:
            # Fetch user info for the report header
            user_row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(raw_user_meta_data->>'full_name', raw_user_meta_data->>'name', email) AS display_name,
                    email
                FROM auth.users
                WHERE id = $1::uuid
                """,
                user_id,
            )

            # Fetch all items with their latest valuation
            rows = await conn.fetch(
                """
                SELECT
                    i.id,
                    COALESCE(i.title, i.canonical_key, '') AS title,
                    COALESCE(i.category, '')                 AS category,
                    COALESCE(i.condition, '')                AS condition,
                    COALESCE(i.condition_grade, '')          AS grade,
                    i.image_url,
                    i.created_at                             AS date_acquired,
                    pp.q50                                   AS estimated_value
                FROM items i
                LEFT JOIN LATERAL (
                    -- price_predictions canonical join columns are item_ref
                    -- + generated_at, not item_id + asof (learnings.md §42).
                    -- Partition prune: latest prediction is always within
                    -- the last 60 days; LATERAL fires once per item.
                    SELECT q50
                    FROM price_predictions
                    WHERE item_ref = i.canonical_key
                      AND generated_at > now() - interval '60 days'
                    ORDER BY generated_at DESC
                    LIMIT 1
                ) pp ON true
                WHERE i.user_id = $1::uuid
                ORDER BY i.category, i.title
                """,
                user_id,
            )

            items: list[InsuranceItemRow] = []
            total_value = 0.0

            for row in rows:
                val = float(row["estimated_value"]) if row["estimated_value"] is not None else None
                if val is not None:
                    total_value += val

                date_str = None
                if row["date_acquired"]:
                    try:
                        date_str = row["date_acquired"].strftime("%Y-%m-%d")
                    except Exception:
                        date_str = str(row["date_acquired"])

                items.append(InsuranceItemRow(
                    id=str(row["id"]),
                    name=row["title"],
                    category=row["category"],
                    condition=row["condition"],
                    grade=row["grade"],
                    estimated_value=val,
                    currency=currency,
                    image_url=row["image_url"] if row["image_url"] else None,
                    date_acquired=date_str,
                ))

            user_email = user_row["email"] if user_row else None
            user_name = user_row["display_name"] if user_row else None

            data = InsuranceReportData(
                generated_at=now,
                user_email=user_email,
                user_name=user_name,
                total_items=len(items),
                total_estimated_value=round(total_value, 2),
                currency=currency,
                methodology=(
                    "Values are estimated using CollectAI's pricing algorithm, which analyzes "
                    "recent sold listings from major marketplaces (eBay, TCGPlayer, Cardmarket, "
                    "StockX, and others), applies condition-based adjustments, and uses ridge "
                    "regression models to predict current fair market value (q50 median estimate). "
                    "Population data and rarity factors are incorporated where available."
                ),
                items=items,
            )

            if format == "json":
                return JSONResponse(content=data.model_dump())
            return HTMLResponse(content=_render_html_report(data))

    except Exception as e:
        logger.error("[export] Insurance report generation failed: %s", e)
        raise error_response(500, "Failed to generate insurance report", code="EXPORT_ERROR")
