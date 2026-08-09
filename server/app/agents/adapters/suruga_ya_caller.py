"""
Suruga-ya marketplace adapter.

Suruga-ya (駿河屋, suruga-ya.jp) is a Japanese secondhand chain — massive
catalog for games, toys, figures, manga, magazines, trading cards, CDs.
Prices are separately marked as 中古 (used) and 新品 (new). Strong
coverage for JP pop culture, especially mid-value items.

Covers: anime_figures, gunpla, bandai_premium, jp_event, jp_magazine,
retro_games, retro_handhelds, retro_pokemon, nintendo_merch, manga,
one_piece, scale_models.

Requires the JP Lambda proxy (see infra/lambda_jp_proxy/) — direct
requests from EU IP get geo-filtered to a stub page.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from app.agents.adapters._jp_proxy import configured as jp_proxy_configured
from app.agents.adapters._jp_proxy import fetch_via_proxy
from workers.circuit_breaker import CircuitOpenError, suruga_ya_circuit

logger = logging.getLogger(__name__)

SURUGA_YA_SOURCE_RELIABILITY = 0.80

SURUGA_YA_SEARCH_URL = "https://www.suruga-ya.jp/search"
SURUGA_YA_DETAIL_URL_PREFIX = "https://www.suruga-ya.jp/product/detail/"

SUPPORTED_CATEGORIES = [
    "anime_figures",
    "gunpla",
    "bandai_premium",
    "jp_event",
    "jp_magazine",
    "retro_games",
    "retro_handhelds",
    "retro_pokemon",
    "nintendo_merch",
    "manga",
    "one_piece",
    "scale_models",
]

_FALLBACK_JPY_TO_EUR = 0.0062


def _convert_jpy_to_eur(jpy: float) -> float:
    try:
        from pipelines.import_common import to_eur
        return to_eur(jpy, "JPY")
    except Exception:
        return round(jpy * _FALLBACK_JPY_TO_EUR, 2)


# Matches ``中古：￥7,300``, ``新品：￥1,500``, ``￥1,500`` — takes the digits
_PRICE_RE = re.compile(r"[￥¥]\s*([0-9,]+)")


def _parse_jpy(text: str) -> float:
    m = _PRICE_RE.search(text or "")
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return 0.0


def _detect_condition(item_text: str) -> Optional[str]:
    """中古 → Used, 新品 → New. Returns None if neither marker is present."""
    if "中古" in item_text:
        return "Used"
    if "新品" in item_text:
        return "New"
    return None


def _normalize(item_id: str, title: str, jpy_price: float,
               condition: Optional[str], image_url: str) -> Dict[str, Any]:
    eur = _convert_jpy_to_eur(jpy_price)
    return {
        "source": "suruga_ya",
        "raw_id": f"suruga_ya-{item_id}",
        "title": title[:500],
        "price": eur,
        "currency": "EUR",
        "source_price": jpy_price,
        "source_currency": "JPY",
        "url": f"{SURUGA_YA_DETAIL_URL_PREFIX}{item_id}" if item_id else SURUGA_YA_SEARCH_URL,
        "condition": condition,
        "image_url": image_url,
        "is_sold": False,
        "sold_at": None,
    }


class SurugaYaCaller:
    def __init__(self, enabled: Optional[bool] = None) -> None:
        self._enabled = (
            enabled if enabled is not None
            else os.getenv("SURUGA_YA_ENABLED", "true").lower() == "true"
        )
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
                    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            )
        return self._http

    async def _fetch_html(self, url: str) -> Optional[str]:
        if jp_proxy_configured():
            return await fetch_via_proxy(url)
        client = await self._client()
        try:
            resp = await client.get(url)
            return resp.text if resp.status_code == 200 else None
        except Exception:
            return None

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not self.configured:
            return []
        try:
            suruga_ya_circuit.check()
        except CircuitOpenError:
            return []

        try:
            url = f"{SURUGA_YA_SEARCH_URL}?category=&search_word={quote_plus(query)}"
            html = await self._fetch_html(url)
            if not html:
                suruga_ya_circuit.record_failure()
                return []
            suruga_ya_circuit.record_success()
            return self._parse(html, limit)
        except Exception as exc:
            suruga_ya_circuit.record_failure()
            logger.warning("Suruga-ya search error: %s", exc)
            return []

    def _parse(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse search-result cards.

        Each card is an ``<li class="item">`` (or similar — structure
        varies by listing type) containing:
          - ``<h3 class="product-name">{title}</h3>``
          - anchor to ``/product/detail/{id}``
          - ``<p class="price_teika">中古：<span><strong>￥7,300</strong></span></p>``
          - thumbnail img with src including ``shinaban={id}``
        """
        results: List[Dict[str, Any]] = []
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("BeautifulSoup not available; suruga-ya parsing disabled")
            return results

        soup = BeautifulSoup(html, "lxml")

        # Each result has a <h3 class="product-name"> tag inside a wrapper
        # that also contains the price and detail-link. Walk up from the
        # title to the nearest ancestor that contains a price and link.
        for name_tag in soup.select("h3.product-name"):
            if len(results) >= limit:
                break

            title = name_tag.get_text(strip=True)
            if not title:
                continue

            # Walk up to the item wrapper — stop at the first ancestor that
            # contains both a detail anchor AND a price element.
            wrapper = name_tag
            for _ in range(6):
                wrapper = wrapper.parent
                if wrapper is None:
                    break
                anchor = wrapper.find("a", href=re.compile(r"/product/detail/\d+"))
                if anchor and wrapper.select_one("p.price_teika, p.item_price, span.text-red"):
                    break
            if wrapper is None:
                continue

            anchor = wrapper.find("a", href=re.compile(r"/product/detail/(\d+)"))
            if not anchor:
                continue
            m = re.search(r"/product/detail/(\d+)", anchor.get("href", ""))
            if not m:
                continue
            item_id = m.group(1)

            # Price lives anywhere in the wrapper — pull all text + parse
            wrapper_text = wrapper.get_text(" ", strip=True)
            jpy_price = _parse_jpy(wrapper_text)
            condition = _detect_condition(wrapper_text)

            img = wrapper.find("img")
            image_url = img.get("src", "") if img else ""

            results.append(_normalize(item_id, title, jpy_price, condition, image_url))

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        # Suruga-ya doesn't publish a sold-history view — every listing
        # on the site is a current in-stock offer. Return empty.
        return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            html = await self._fetch_html(f"{SURUGA_YA_SEARCH_URL}?search_word=test")
            return html is not None
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
        self._http = None
