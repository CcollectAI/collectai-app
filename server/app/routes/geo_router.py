"""
Geolocation endpoint — IP-based region auto-detection.

Called during onboarding (before login) so no auth is required.
Uses ip-api.com (free, no key, 45 req/min) with 24-hour caching.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import httpx
from fastapi import APIRouter, Depends, Request

from app.cache import cache_get, cache_set
from app.config import GEO_CACHE_TTL
from app.rate_limit import per_ip_rate_limit

import hashlib

router = APIRouter(prefix="/geo", tags=["Geo"])
logger = logging.getLogger(__name__)

# Per-IP: 30 requests per minute for public geo detection
_geo_ip_limit = per_ip_rate_limit(30, scope="geo")


def _mask_ip(ip: str) -> str:
    """Mask an IP address for safe logging (GDPR-friendly)."""
    if ":" in ip:
        # IPv6: use hashed prefix
        return hashlib.sha256(ip.encode()).hexdigest()[:12]
    # IPv4: mask last octet
    parts = ip.rsplit(".", 1)
    return f"{parts[0]}.xxx" if len(parts) == 2 else ip

_CACHE_TTL = GEO_CACHE_TTL

# Country code → (region, default currency)
_COUNTRY_MAP: Dict[str, Tuple[str, str]] = {
    # Americas
    "US": ("americas", "USD"),
    "CA": ("americas", "CAD"),
    "MX": ("americas", "USD"),
    "BR": ("americas", "USD"),
    # Europe
    "DE": ("europe", "EUR"),
    "FR": ("europe", "EUR"),
    "NL": ("europe", "EUR"),
    "GB": ("europe", "GBP"),
    "IT": ("europe", "EUR"),
    "ES": ("europe", "EUR"),
    "BE": ("europe", "EUR"),
    "AT": ("europe", "EUR"),
    "CH": ("europe", "EUR"),
    "SE": ("europe", "EUR"),
    "NO": ("europe", "EUR"),
    "DK": ("europe", "EUR"),
    "FI": ("europe", "EUR"),
    "PL": ("europe", "EUR"),
    "PT": ("europe", "EUR"),
    "IE": ("europe", "EUR"),
    "CZ": ("europe", "EUR"),
    # Japan
    "JP": ("japan", "JPY"),
    # Korea
    "KR": ("korea", "KRW"),
    # Oceania
    "AU": ("oceania", "AUD"),
    "NZ": ("oceania", "AUD"),
}

_FALLBACK = {"region": "other", "currency": "EUR", "country_code": None}


def _get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or direct connection."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


@router.get("/detect", dependencies=[Depends(_geo_ip_limit)], summary="Detect region from IP")
async def detect_region(request: Request):
    """Auto-detect user region from IP address.

    No auth required — called during onboarding before login.
    Returns {region, currency, country_code}.
    """
    ip = _get_client_ip(request)
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return _FALLBACK

    # Check cache
    cache_key = f"geo:{ip}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Call ip-api.com
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,countryCode"},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "success":
                logger.debug("[geo] ip-api returned non-success for %s: %s", _mask_ip(ip), data)
                cache_set(cache_key, _FALLBACK, ttl=_CACHE_TTL)
                return _FALLBACK

            country_code = data.get("countryCode", "")
            region, currency = _COUNTRY_MAP.get(country_code, ("other", "EUR"))

            result = {
                "region": region,
                "currency": currency,
                "country_code": country_code,
            }
            cache_set(cache_key, result, ttl=_CACHE_TTL)
            return result

    except Exception:
        logger.warning("[geo] Failed to detect region for IP %s", _mask_ip(ip), exc_info=True)
        cache_set(cache_key, _FALLBACK, ttl=_CACHE_TTL)
        return _FALLBACK
