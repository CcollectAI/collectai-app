"""
ComicBookRealm marketplace adapter for the Marketplace Aggregation Agent.

ComicBookRealm (comicbookrealm.com) is an established comic book price guide
and database providing guide values, graded values (CGC grades), and cover
images. This adapter scrapes search results to extract pricing data.

Prices are in USD; converted to EUR via pipelines.import_common.to_eur.

Covers: comic_books only.

Env vars:
    COMICBOOKREALM_ENABLED - "true" to enable (default: "true")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from workers.circuit_breaker import comicbookrealm_circuit, CircuitOpenError

logger = logging.getLogger(__name__)

COMICBOOKREALM_SOURCE_RELIABILITY = 0.80
COMICBOOKREALM_SOLD_RELIABILITY = 0.85

# ComicBookRealm search URL
COMICBOOKREALM_SEARCH_URL = "https://comicbookrealm.com/search"

# Categories that ComicBookRealm covers
SUPPORTED_CATEGORIES = [
    "comic_books",
]

# USD to EUR fallback rate
_FALLBACK_USD_TO_EUR = 0.92


def _convert_usd_to_eur(usd_price: float) -> float:
    """Convert USD price to EUR using live rates with fallback."""
    try:
        from pipelines.import_common import to_eur
        return to_eur(usd_price, "USD")
    except Exception:
        return round(usd_price * _FALLBACK_USD_TO_EUR, 2)


def _parse_usd_price(text: str) -> float:
    """Extract a USD price from text like '$12.50', 'US$25.00', 'USD 100'."""
    if not text:
        return 0.0

    patterns = [
        r'\$\s*([\d,]+(?:\.\d{2})?)',           # $ symbol
        r'US\$\s*([\d,]+(?:\.\d{2})?)',          # US$ prefix
        r'USD\s*([\d,]+(?:\.\d{2})?)',           # USD prefix
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except (ValueError, TypeError):
                continue

    return 0.0


def _normalize_listing(
    issue_id: str,
    title: str,
    usd_price: float,
    condition: Optional[str],
    image_url: str,
    is_sold: bool = False,
    grade: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a ComicBookRealm listing to the standard MarketHit format."""
    eur_price = _convert_usd_to_eur(usd_price)
    item_url = f"https://comicbookrealm.com/report/comic/{issue_id}" if issue_id else COMICBOOKREALM_SEARCH_URL

    hit: Dict[str, Any] = {
        "source": "comicbookrealm",
        "raw_id": f"cbr-{issue_id}",
        "title": title[:500],
        "price": eur_price,
        "currency": "EUR",
        "source_price": usd_price,
        "source_currency": "USD",
        "url": item_url,
        "condition": condition or grade,
        "image_url": image_url,
        "is_sold": is_sold,
        "sold_at": None,
    }

    if grade:
        hit["grade"] = grade

    return hit


class ComicBookRealmCaller:
    """Async ComicBookRealm adapter for the marketplace aggregation agent."""

    def __init__(self, enabled: Optional[bool] = None):
        import os
        self._enabled = enabled if enabled is not None else os.getenv("COMICBOOKREALM_ENABLED", "true").lower() == "true"
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def configured(self) -> bool:
        return self._enabled

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                follow_redirects=True,
            )
        return self._http

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search ComicBookRealm for comic book price guide data."""
        if not self.configured:
            return []

        try:
            comicbookrealm_circuit.check()
        except CircuitOpenError:
            logger.warning("ComicBookRealm circuit open — skipping")
            return []

        try:
            client = await self._client()
            resp = await client.get(
                COMICBOOKREALM_SEARCH_URL,
                params={"q": query},
            )

            if resp.status_code in (429, 503):
                comicbookrealm_circuit.record_failure()
                logger.warning("ComicBookRealm returned %d", resp.status_code)
                return []

            if resp.status_code != 200:
                comicbookrealm_circuit.record_failure()
                logger.warning("ComicBookRealm search returned %d", resp.status_code)
                return []

            comicbookrealm_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)
            return results

        except Exception as exc:
            comicbookrealm_circuit.record_failure()
            logger.warning("ComicBookRealm search error: %s", exc)
            return []

    def _parse_search_page(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse ComicBookRealm search results from HTML.

        ComicBookRealm pages contain:
        - Issue IDs in links (e.g., /report/comic/12345)
        - Comic titles and issue numbers
        - Guide values in USD (e.g., $12.50)
        - CGC grade values (e.g., 9.8, 9.6, 9.4)
        - Cover images
        """
        results: List[Dict[str, Any]] = []

        # Pattern to extract issue IDs from links
        issue_id_pattern = re.compile(
            r'/(?:report/)?comic/(\d+)',
        )

        # Price pattern — USD prices
        price_pattern = re.compile(
            r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        )

        # Title pattern
        title_pattern = re.compile(
            r'class="[^"]*(?:comic-title|issue-title|search-result-title|comic_name)[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Broader title extraction from links to comic pages
        title_link_pattern = re.compile(
            r'/(?:report/)?comic/\d+[^"]*"[^>]*>([^<]+)<',
            re.IGNORECASE,
        )

        # Image pattern
        img_pattern = re.compile(
            r'<img[^>]+src="(https?://[^"]*(?:comicbookrealm|cbr)[^"]*\.(jpg|jpeg|png|webp|gif))"',
            re.IGNORECASE,
        )

        # Grade pattern — CGC / CBCS grades (e.g., 9.8, 9.6)
        grade_pattern = re.compile(
            r'(?:CGC|CBCS|Grade)\s*:?\s*([\d.]+)',
            re.IGNORECASE,
        )

        # Extract unique issue IDs
        issue_ids = list(dict.fromkeys(issue_id_pattern.findall(html)))[:limit]
        titles = title_pattern.findall(html)
        if not titles:
            titles = title_link_pattern.findall(html)
        prices = price_pattern.findall(html)
        images = [m[0] for m in img_pattern.findall(html)]
        grades = grade_pattern.findall(html)

        for i, issue_id in enumerate(issue_ids):
            # Title
            title = titles[i].strip() if i < len(titles) else f"Comic #{issue_id}"

            # Price (guide value in USD)
            usd_price = 0.0
            if i < len(prices):
                try:
                    usd_price = float(prices[i].replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Image
            image_url = images[i] if i < len(images) else ""

            # Grade
            grade = grades[i] if i < len(grades) else None

            # Condition from grade
            condition = None
            if grade:
                try:
                    grade_val = float(grade)
                    if grade_val >= 9.6:
                        condition = "Near Mint+"
                    elif grade_val >= 9.2:
                        condition = "Near Mint"
                    elif grade_val >= 8.0:
                        condition = "Very Fine"
                    elif grade_val >= 6.0:
                        condition = "Fine"
                    elif grade_val >= 4.0:
                        condition = "Very Good"
                    else:
                        condition = "Good"
                except (ValueError, TypeError):
                    pass

            results.append(
                _normalize_listing(
                    issue_id, title, usd_price, condition, image_url,
                    is_sold=False, grade=grade,
                )
            )

        return results

    async def sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return guide values as sold reference pricing.

        ComicBookRealm provides price guide values which serve as reference
        pricing benchmarks. These are returned as "sold" comps since they
        represent historical value assessments.
        """
        if not self.configured:
            return []

        try:
            comicbookrealm_circuit.check()
        except CircuitOpenError:
            return []

        try:
            client = await self._client()
            resp = await client.get(
                COMICBOOKREALM_SEARCH_URL,
                params={"q": query},
            )

            # 2026-04-23 silent-failure sweep: any auth/rate/server error
            # trips the circuit. Was special-casing only 429/503.
            if resp.status_code != 200:
                if resp.status_code in (401, 403, 429) or resp.status_code >= 500:
                    comicbookrealm_circuit.record_failure()
                    logger.warning("ComicBookRealm sold_comps HTTP %d — circuit failure", resp.status_code)
                return []

            comicbookrealm_circuit.record_success()
            results = self._parse_search_page(resp.text, limit)

            # Mark guide values as sold reference data
            for hit in results:
                hit["is_sold"] = True

            return results

        except Exception as exc:
            comicbookrealm_circuit.record_failure()
            logger.warning("ComicBookRealm sold_comps error: %s", exc)
            return []

    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            client = await self._client()
            resp = await client.get(
                COMICBOOKREALM_SEARCH_URL,
                params={"q": "test"},
            )
            return resp.status_code in (200, 403)  # 403 = rate limited but reachable
        except Exception:
            return False

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
