"""
Dossier Factory -- FastAPI router.

Endpoints:
  GET /dossier/{item_id}         Full dossier as JSON
  GET /dossier/{item_id}/summary Lightweight summary (identity + valuation)
  GET /dossier/{item_id}/export  Self-contained HTML download
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.subscription import require_plan

from app.auth import get_current_user_id
from app.db import db_configured, get_conn
from app.agents.dossier_agent import generate_dossier, ItemDossier

router = APIRouter(prefix="/dossier", tags=["dossier"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class DossierResponse(BaseModel):
    item_id: str
    generated_at: str
    version: str
    identity: Dict[str, Any]
    valuation: Dict[str, Any]
    provenance: List[Dict[str, Any]]
    price_history: List[Dict[str, Any]]
    market_comps: List[Dict[str, Any]]
    photos: List[str]
    collections: List[str]
    authenticity_signals: List[str]
    completeness_score: float


class DossierSummaryResponse(BaseModel):
    item_id: str
    generated_at: str
    identity: Dict[str, Any]
    valuation: Dict[str, Any]
    completeness_score: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{item_id}", response_model=DossierResponse)
async def get_dossier(item_id: str, user_id: str = Depends(get_current_user_id)):
    """Return full dossier for an item as JSON."""
    if not db_configured():
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with get_conn() as conn:
            dossier = await generate_dossier(item_id, user_id, conn)
    except ValueError as e:
        logger.warning("[dossier] %s (item=%s, user=%s)", e, item_id, user_id)
        raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        logger.error("[dossier] Error generating dossier: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate dossier")

    return DossierResponse(**dossier.to_dict())


@router.get("/{item_id}/summary", response_model=DossierSummaryResponse)
async def get_dossier_summary(item_id: str, user_id: str = Depends(get_current_user_id)):
    """Return lightweight summary (identity + valuation + completeness)."""
    if not db_configured():
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with get_conn() as conn:
            dossier = await generate_dossier(item_id, user_id, conn)
    except ValueError as e:
        logger.warning("[dossier] %s (item=%s, user=%s)", e, item_id, user_id)
        raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        logger.error("[dossier] Error generating dossier summary: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate dossier summary")

    return DossierSummaryResponse(
        item_id=dossier.item_id,
        generated_at=dossier.generated_at,
        identity=dossier.identity,
        valuation=dossier.valuation,
        completeness_score=dossier.completeness_score,
    )


@router.get("/{item_id}/export")
async def export_dossier_html(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    _plan: str = Depends(require_plan("pro")),
):
    """Return dossier as a downloadable self-contained HTML document."""
    if not db_configured():
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with get_conn() as conn:
            dossier = await generate_dossier(item_id, user_id, conn)
    except ValueError as e:
        logger.warning("[dossier] %s (item=%s, user=%s)", e, item_id, user_id)
        raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        logger.error("[dossier] Error exporting dossier: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to export dossier")

    html_content = _render_html(dossier)

    # Build safe filename
    item_name = dossier.identity.get("name", "item") or "item"
    safe_name = re.sub(r"[^\w\s-]", "", item_name).strip().replace(" ", "_")[:50]
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"dossier_{safe_name}_{date_str}.html"

    return HTMLResponse(
        content=html_content,
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# HTML renderer (self-contained, no external deps)
# ---------------------------------------------------------------------------

def _esc(value: Any) -> str:
    """HTML-escape a value."""
    if value is None:
        return ""
    return html.escape(str(value))


def _fmt_price(value: Any, currency: str = "EUR") -> str:
    """Format a price value for display."""
    if value is None:
        return "-"
    try:
        num = float(value)
    except (ValueError, TypeError):
        return "-"
    symbol = "\u20ac" if currency.upper() == "EUR" else currency
    return f"{symbol}{num:,.2f}"


def _fmt_date(value: Any) -> str:
    """Format an ISO date string for display."""
    if not value:
        return "-"
    s = str(value)
    # Try to parse and reformat
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(s[:26], fmt[:len(s)])
            return dt.strftime("%d %b %Y")
        except (ValueError, IndexError):
            continue
    # Fallback: return first 10 chars
    return s[:10] if len(s) >= 10 else s


def _completeness_bar(score: float) -> str:
    """Render a simple completeness bar in HTML."""
    pct = int(score * 100)
    color = "#81D8D0" if pct >= 60 else "#F59E0B" if pct >= 40 else "#EF4444"
    return f"""
    <div style="margin-top:6px;">
      <div style="display:flex;justify-content:space-between;font-size:12px;color:#6B7280;margin-bottom:4px;">
        <span>Completeness</span><span>{pct}%</span>
      </div>
      <div style="background:#E5E7EB;border-radius:6px;height:8px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:{color};border-radius:6px;transition:width 0.3s;"></div>
      </div>
    </div>"""


def _render_html(dossier: ItemDossier) -> str:
    """Render ItemDossier into a self-contained HTML document."""

    item_name = _esc(dossier.identity.get("name", "Unknown Item"))
    category = _esc(dossier.identity.get("category", ""))
    condition = _esc(dossier.identity.get("condition", ""))
    grade = _esc(dossier.identity.get("grade", ""))
    image_url = dossier.identity.get("image_url") or (dossier.photos[0] if dossier.photos else "")

    # --- Header image section ---
    image_html = ""
    if image_url:
        image_html = f"""
        <div style="text-align:center;margin-bottom:24px;">
          <img src="{_esc(image_url)}" alt="{item_name}"
               style="max-width:100%;max-height:300px;border-radius:12px;object-fit:cover;box-shadow:0 2px 8px rgba(0,0,0,0.1);" />
        </div>"""

    # --- Valuation card ---
    val = dossier.valuation
    valuation_html = ""
    if val and val.get("q50") is not None:
        conf = val.get("confidence_score")
        conf_str = f"{int(float(conf) * 100)}%" if conf is not None else "N/A"
        valuation_html = f"""
        <div style="background:linear-gradient(135deg,#81D8D0 0%,#5BC0B8 100%);border-radius:12px;padding:24px;color:#FFFFFF;margin-bottom:24px;">
          <h2 style="margin:0 0 16px 0;font-size:18px;font-weight:600;">Valuation</h2>
          <div style="display:flex;justify-content:space-between;align-items:flex-end;">
            <div>
              <div style="font-size:12px;opacity:0.85;">Low</div>
              <div style="font-size:20px;font-weight:700;">{_fmt_price(val.get('q10'))}</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:12px;opacity:0.85;">Estimated</div>
              <div style="font-size:28px;font-weight:800;">{_fmt_price(val.get('q50'))}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:12px;opacity:0.85;">High</div>
              <div style="font-size:20px;font-weight:700;">{_fmt_price(val.get('q90'))}</div>
            </div>
          </div>
          <div style="margin-top:12px;font-size:12px;opacity:0.85;">
            Confidence: {conf_str}
          </div>
          {f'<div style="margin-top:8px;font-size:13px;opacity:0.9;">{_esc(val.get("explanation", ""))}</div>' if val.get("explanation") else ""}
        </div>"""

    # --- Identity details ---
    attrs = dossier.identity.get("attributes") or {}
    attrs_rows = ""
    if isinstance(attrs, dict):
        for k, v in attrs.items():
            attrs_rows += f"<tr><td style='padding:6px 12px;color:#6B7280;font-size:13px;'>{_esc(k)}</td><td style='padding:6px 12px;font-size:13px;'>{_esc(v)}</td></tr>"

    identity_html = f"""
    <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:20px;margin-bottom:24px;">
      <h2 style="margin:0 0 12px 0;font-size:18px;font-weight:600;color:#1F2937;">Item Details</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr><td style="padding:6px 12px;color:#6B7280;font-size:13px;">Category</td><td style="padding:6px 12px;font-size:13px;">{category}</td></tr>
        <tr><td style="padding:6px 12px;color:#6B7280;font-size:13px;">Condition</td><td style="padding:6px 12px;font-size:13px;">{condition or '-'}</td></tr>
        <tr><td style="padding:6px 12px;color:#6B7280;font-size:13px;">Grade</td><td style="padding:6px 12px;font-size:13px;">{grade or '-'}</td></tr>
        <tr><td style="padding:6px 12px;color:#6B7280;font-size:13px;">Sealed</td><td style="padding:6px 12px;font-size:13px;">{'Yes' if dossier.identity.get('sealed') else 'No'}</td></tr>
        {attrs_rows}
      </table>
    </div>"""

    # --- Provenance timeline ---
    provenance_html = ""
    if dossier.provenance:
        events_li = ""
        for evt in dossier.provenance:
            icon = {
                "added": "&#x2795;",
                "purchase": "&#x1F4B0;",
                "sale": "&#x1F4B8;",
                "graded": "&#x2B50;",
                "verified": "&#x2705;",
                "transferred_in": "&#x2B05;",
                "transferred_out": "&#x27A1;",
            }.get(evt.get("event_type", ""), "&#x25CF;")
            note = f"<br><span style='color:#6B7280;font-size:12px;'>{_esc(evt.get('note', ''))}</span>" if evt.get("note") else ""
            events_li += f"""
            <div style="display:flex;gap:12px;margin-bottom:16px;">
              <div style="width:32px;height:32px;background:#F0FDFA;border:2px solid #81D8D0;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">{icon}</div>
              <div>
                <div style="font-size:13px;font-weight:600;color:#1F2937;">{_esc(evt.get('event_type', '').replace('_', ' ').title())}</div>
                <div style="font-size:12px;color:#9CA3AF;">{_fmt_date(evt.get('timestamp'))}{f" &middot; {_esc(evt.get('source'))}" if evt.get('source') else ""}</div>
                {note}
              </div>
            </div>"""

        provenance_html = f"""
        <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:20px;margin-bottom:24px;">
          <h2 style="margin:0 0 16px 0;font-size:18px;font-weight:600;color:#1F2937;">Provenance Timeline</h2>
          {events_li}
        </div>"""

    # --- Authenticity signals ---
    auth_html = ""
    if dossier.authenticity_signals:
        badges = ""
        for sig in dossier.authenticity_signals:
            label = sig.replace("_", " ").title()
            badges += f'<span style="display:inline-block;background:#F0FDFA;color:#0D9488;border:1px solid #81D8D0;border-radius:999px;padding:4px 12px;font-size:12px;font-weight:500;margin-right:8px;margin-bottom:6px;">{_esc(label)}</span>'
        auth_html = f"""
        <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:20px;margin-bottom:24px;">
          <h2 style="margin:0 0 12px 0;font-size:18px;font-weight:600;color:#1F2937;">Authenticity Signals</h2>
          <div>{badges}</div>
        </div>"""

    # --- Market comparables ---
    comps_html = ""
    if dossier.market_comps:
        rows = ""
        for comp in dossier.market_comps:
            title_cell = _esc(comp.get("title", ""))
            comp_href = comp.get("affiliate_url") or comp.get("url")
            if comp_href:
                title_cell = f'<a href="{_esc(comp_href)}" style="color:#0D9488;text-decoration:none;" target="_blank" rel="noopener">{title_cell}</a>'
            rows += f"""
            <tr style="border-bottom:1px solid #F3F4F6;">
              <td style="padding:8px 12px;font-size:13px;">{title_cell}</td>
              <td style="padding:8px 12px;font-size:13px;">{_fmt_price(comp.get('price'), comp.get('currency', 'EUR'))}</td>
              <td style="padding:8px 12px;font-size:13px;color:#6B7280;">{_esc(comp.get('source', ''))}</td>
              <td style="padding:8px 12px;font-size:13px;color:#6B7280;">{_fmt_date(comp.get('sold_date'))}</td>
              <td style="padding:8px 12px;font-size:13px;color:#6B7280;">{_esc(comp.get('condition', ''))}</td>
            </tr>"""

        comps_html = f"""
        <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:20px;margin-bottom:24px;overflow-x:auto;">
          <h2 style="margin:0 0 12px 0;font-size:18px;font-weight:600;color:#1F2937;">Market Comparables</h2>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:2px solid #E5E7EB;">
                <th style="padding:8px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Title</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Price</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Source</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Date</th>
                <th style="padding:8px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Condition</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    # --- Price history ---
    ph_html = ""
    if dossier.price_history:
        ph_rows = ""
        for ph in dossier.price_history:
            ph_rows += f"""
            <tr style="border-bottom:1px solid #F3F4F6;">
              <td style="padding:6px 12px;font-size:13px;">{_fmt_date(ph.get('recorded_at'))}</td>
              <td style="padding:6px 12px;font-size:13px;">{_fmt_price(ph.get('price'), ph.get('currency', 'EUR'))}</td>
              <td style="padding:6px 12px;font-size:13px;color:#6B7280;">{_esc(ph.get('source', ''))}</td>
            </tr>"""

        ph_html = f"""
        <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:20px;margin-bottom:24px;">
          <h2 style="margin:0 0 12px 0;font-size:18px;font-weight:600;color:#1F2937;">Price History</h2>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:2px solid #E5E7EB;">
                <th style="padding:6px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Date</th>
                <th style="padding:6px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Price</th>
                <th style="padding:6px 12px;text-align:left;font-size:12px;color:#6B7280;font-weight:600;">Source</th>
              </tr>
            </thead>
            <tbody>{ph_rows}</tbody>
          </table>
        </div>"""

    # --- Collections ---
    collections_html = ""
    if dossier.collections:
        badges = " ".join(
            f'<span style="display:inline-block;background:#EFF6FF;color:#3B82F6;border:1px solid #BFDBFE;border-radius:999px;padding:4px 12px;font-size:12px;font-weight:500;margin-right:8px;">{_esc(c)}</span>'
            for c in dossier.collections
        )
        collections_html = f"""
        <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:20px;margin-bottom:24px;">
          <h2 style="margin:0 0 12px 0;font-size:18px;font-weight:600;color:#1F2937;">Collections</h2>
          <div>{badges}</div>
        </div>"""

    # --- Completeness ---
    completeness_html = _completeness_bar(dossier.completeness_score)

    # --- Full page ---
    generated = _fmt_date(dossier.generated_at)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CollectAI Dossier - {item_name}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: #F9FAFB;
      color: #1F2937;
      line-height: 1.5;
    }}
    .container {{
      max-width: 720px;
      margin: 0 auto;
      padding: 32px 20px;
    }}
    @media print {{
      body {{ background: #FFF; }}
      .container {{ padding: 16px; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div style="text-align:center;margin-bottom:32px;">
      <div style="display:inline-flex;align-items:center;gap:8px;margin-bottom:12px;">
        <div style="width:36px;height:36px;background:#81D8D0;border-radius:8px;display:flex;align-items:center;justify-content:center;">
          <span style="color:#FFFFFF;font-weight:800;font-size:16px;">C</span>
        </div>
        <span style="font-size:18px;font-weight:700;color:#1F2937;">Collect<span style="color:#81D8D0;">AI</span></span>
      </div>
      <h1 style="font-size:24px;font-weight:800;color:#1F2937;margin-bottom:4px;">{item_name}</h1>
      <p style="font-size:14px;color:#6B7280;">{category}{f" &middot; {condition}" if condition else ""}{f" &middot; {grade}" if grade else ""}</p>
      <p style="font-size:12px;color:#9CA3AF;margin-top:4px;">Generated {generated} &middot; Dossier v{_esc(dossier.version)}</p>
      {completeness_html}
    </div>

    {image_html}
    {valuation_html}
    {identity_html}
    {auth_html}
    {provenance_html}
    {comps_html}
    {ph_html}
    {collections_html}

    <!-- Footer -->
    <div style="text-align:center;padding-top:24px;border-top:1px solid #E5E7EB;margin-top:8px;">
      <p style="font-size:11px;color:#9CA3AF;">
        This dossier was generated by CollectAI. Valuations are estimates based on market data and
        should not be considered financial advice. &copy; {datetime.now(timezone.utc).year} CollectAI
      </p>
    </div>
  </div>
</body>
</html>"""
