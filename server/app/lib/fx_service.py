"""
Live FX rate service with in-memory TTL caching.

Fetches rates from api.exchangerate.host (free, no key required),
caches for 1 hour, and falls back to hardcoded rates from app.config
if the API is unreachable.

All backend prices are stored in EUR.  The service exposes:
    get_rates()          -> dict  foreign→EUR  (for price normalisation)
    get_rates_from_eur() -> dict  EUR→foreign  (for frontend display)
    convert_to_eur(amount, currency) -> float
"""

from __future__ import annotations

import logging
from typing import Dict

import httpx

from app.cache import cache_get, cache_set
from app.config import USD_TO_EUR, GBP_TO_EUR, JPY_TO_EUR

logger = logging.getLogger(__name__)

_CACHE_KEY = "fx:rates"
_CACHE_TTL = 3600  # 1 hour

# Hardcoded fallback rates (foreign → EUR)
_FALLBACK_TO_EUR: Dict[str, float] = {
    "USD": USD_TO_EUR,
    "GBP": GBP_TO_EUR,
    "JPY": JPY_TO_EUR,
    "EUR": 1.0,
}

_API_URL = "https://api.exchangerate.host/latest"


async def _fetch_live_rates() -> Dict[str, float] | None:
    """Fetch live rates from exchangerate.host.  Returns foreign→EUR dict or None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_API_URL, params={"base": "EUR", "symbols": "USD,GBP,JPY"})
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success", True):
                logger.warning("[fx_service] API returned success=false: %s", data)
                return None

            eur_based = data.get("rates", {})
            if not eur_based:
                return None

            # Convert EUR-based rates (EUR→foreign) to foreign→EUR
            to_eur: Dict[str, float] = {"EUR": 1.0}
            for cur, rate in eur_based.items():
                if rate and float(rate) > 0:
                    to_eur[cur] = round(1.0 / float(rate), 6)

            logger.info("[fx_service] Fetched live rates: %s", to_eur)
            return to_eur
    except Exception:
        logger.warning("[fx_service] Failed to fetch live rates, using fallback", exc_info=True)
        return None


async def get_rates() -> Dict[str, float]:
    """Return foreign→EUR conversion rates (e.g. {"USD": 0.92, "GBP": 1.16, ...}).

    Cached for 1 hour.  Falls back to config defaults if API unreachable.
    """
    cached = cache_get(_CACHE_KEY)
    if cached is not None:
        return cached

    live = await _fetch_live_rates()
    rates = live if live else dict(_FALLBACK_TO_EUR)
    cache_set(_CACHE_KEY, rates, ttl=_CACHE_TTL)
    return rates


async def get_rates_from_eur() -> Dict[str, float]:
    """Return EUR→foreign rates (e.g. {"USD": 1.08, "GBP": 0.86, ...}).

    Inverse of get_rates().
    """
    to_eur = await get_rates()
    from_eur: Dict[str, float] = {}
    for cur, rate in to_eur.items():
        if cur == "EUR":
            from_eur["EUR"] = 1.0
        elif rate and rate > 0:
            from_eur[cur] = round(1.0 / rate, 4)
    return from_eur


async def convert_to_eur(amount: float, currency: str) -> float:
    """Convert an amount in *currency* to EUR using live (or fallback) rates."""
    if currency.upper() == "EUR":
        return amount
    rates = await get_rates()
    rate = rates.get(currency.upper())
    if rate is None:
        logger.warning("[fx_service] Unknown currency %s, returning amount as-is", currency)
        return amount
    return round(amount * rate, 2)
