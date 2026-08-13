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
from app.config import USD_TO_EUR, GBP_TO_EUR, JPY_TO_EUR, KRW_TO_EUR, AUD_TO_EUR, CAD_TO_EUR, FX_CACHE_TTL

logger = logging.getLogger(__name__)

_CACHE_KEY = "fx:rates"
_CACHE_TTL = FX_CACHE_TTL

# Hardcoded fallback rates (foreign → EUR)
_FALLBACK_TO_EUR: Dict[str, float] = {
    "USD": USD_TO_EUR,
    "GBP": GBP_TO_EUR,
    "JPY": JPY_TO_EUR,
    "KRW": KRW_TO_EUR,
    "AUD": AUD_TO_EUR,
    "CAD": CAD_TO_EUR,
    "EUR": 1.0,
}

# Frankfurter is a free, no-auth FX API maintained by the ECB.
# https://www.frankfurter.app/  — replaces exchangerate.host which went paid in 2024.
_API_URL = "https://api.frankfurter.dev/v1/latest"


async def _fetch_live_rates() -> Dict[str, float] | None:
    """Fetch live rates from Frankfurter (free, ECB-backed). Returns foreign→EUR dict or None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Frankfurter doesn't support KRW (ECB doesn't publish KRW rates)
            # — KRW falls back to the hardcoded value in config.py.
            resp = await client.get(
                _API_URL,
                params={"from": "EUR", "to": "USD,GBP,JPY,AUD,CAD"},
            )
            resp.raise_for_status()
            data = resp.json()

            eur_based = data.get("rates", {})
            if not eur_based:
                return None

            # Convert EUR-based rates (EUR→foreign) to foreign→EUR
            to_eur: Dict[str, float] = {"EUR": 1.0}
            for cur, rate in eur_based.items():
                if rate and float(rate) > 0:
                    to_eur[cur] = round(1.0 / float(rate), 6)

            logger.info("[fx_service] Fetched live rates from Frankfurter: %s", to_eur)
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


def convert_to_eur_sync(amount: float, currency: str) -> float:
    """Sync convert_to_eur for batch import jobs that run outside an event loop.

    Uses hardcoded fallback rates (from app.config) — accepts ~1-3% drift vs
    the live ECB rate in exchange for not needing an async context. Imports
    run nightly against thousands of rows; the async version silently returned
    a coroutine (learning 2026-04-18) that serialised into JSON as
    "Object of type coroutine is not JSON serializable" and dropped entire
    upsert batches on the floor.
    """
    if currency.upper() == "EUR":
        return amount
    rate = _FALLBACK_TO_EUR.get(currency.upper())
    if rate is None:
        logger.warning("[fx_service] Unknown currency %s, returning amount as-is", currency)
        return amount
    return round(amount * rate, 2)


async def fx_arrays() -> "tuple[list[str], list]":
    """FX rates as two parallel ARRAYS, for `unnest($n::text[], $m::numeric[])`.

    Shared by `/p2p/watchlist-matches` and `deal_discovery_worker`, which must
    convert with the SAME rates: one is the screen showing a member what meets
    their target, the other is the alert firing on it, and if they disagreed one
    of them would be calling the member a liar about their own number.

    NOT a jsonb map, which looks equivalent and is not. `app/db.py` registers a
    jsonb codec with `encoder=json.dumps`, so an already-serialised dict gets
    double-encoded into a JSON *string*, `->> 'JPY'` returns NULL, and
    `COALESCE(rate, 1)` then silently leaves every foreign amount unconverted.
    That shipped once and passed a direct-connection probe, because a raw
    asyncpg connection has no such codec — only a call through the real pool
    showed it. Arrays have no custom codec on either path.

    Decimal via `str`: `Decimal(float)` would carry the float's binary error
    into a numeric comparison
    (learning_guard_must_match_constraint_type_space).
    """
    from decimal import Decimal

    rate_map: dict[str, Decimal] = {"EUR": Decimal("1")}
    for cur, rate in (await get_rates()).items():
        if rate and rate > 0:
            rate_map[cur.upper()] = Decimal(str(rate))
    codes = list(rate_map.keys())
    return codes, [rate_map[c] for c in codes]
