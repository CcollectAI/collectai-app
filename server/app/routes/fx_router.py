"""
FX rates endpoint — public (no auth required).

GET /fx/rates → { base, rates (foreign→EUR), rates_from_eur (EUR→foreign) }
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.lib.fx_service import get_rates, get_rates_from_eur
from app.rate_limit import per_ip_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fx", tags=["FX"])

# Per-IP: 60 requests per minute for public FX rates
_fx_ip_limit = per_ip_rate_limit(60, scope="fx")


@router.get("/rates", dependencies=[Depends(_fx_ip_limit)], summary="Get FX rates")
async def fx_rates() -> dict:
    """Return live FX rates (cached 1 h, fallback to config defaults)."""
    to_eur = await get_rates()
    from_eur = await get_rates_from_eur()

    return {
        "base": "EUR",
        "rates": {k: v for k, v in to_eur.items() if k != "EUR"},
        "rates_from_eur": {k: v for k, v in from_eur.items() if k != "EUR"},
    }
