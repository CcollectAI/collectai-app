"""
Firecrawl API client for CollectAI.

Thin wrapper around the Firecrawl REST API providing:
- scrape_url()   -- scrape a single URL to markdown + optional structured extraction
- search_web()   -- web search returning results with markdown content
- extract_structured() -- extract structured data from a URL using a JSON schema
- crawl_site()   -- crawl a site from a starting URL

Env vars:
    FIRECRAWL_API_KEY  - API key from firecrawl.dev
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import FIRECRAWL_API_KEY, FIRECRAWL_BASE_URL

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Lazy HTTP client
# ---------------------------------------------------------------------------

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
    return _http_client


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }


def configured() -> bool:
    """Return True if Firecrawl API key is set."""
    return bool(FIRECRAWL_API_KEY)


async def close() -> None:
    """Close the shared HTTP client."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_url(
    url: str,
    formats: list[str] | None = None,
    extract_schema: dict[str, Any] | None = None,
) -> Optional[dict[str, Any]]:
    """
    Scrape a single URL via Firecrawl /scrape.

    Args:
        url: The URL to scrape.
        formats: Output formats (default: ["markdown"]).
        extract_schema: Optional JSON schema for structured extraction.

    Returns:
        Dict with keys like 'markdown', 'metadata', 'extract', or None on failure.
    """
    if not configured():
        logger.debug("Firecrawl not configured (no API key)")
        return None

    body: dict[str, Any] = {"url": url}
    if formats:
        body["formats"] = formats
    else:
        body["formats"] = ["markdown"]
    if extract_schema:
        body["formats"] = list(set(body.get("formats", []) + ["extract"]))
        body["extract"] = {"schema": extract_schema}

    client = _get_client()
    try:
        resp = await client.post(
            f"{FIRECRAWL_BASE_URL}/scrape",
            headers=_headers(),
            json=body,
        )
        if resp.status_code == 429:
            logger.warning("[Firecrawl] Rate limited on /scrape for %s", url)
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("data")
    except httpx.HTTPStatusError as e:
        logger.error("[Firecrawl] /scrape HTTP %d for %s", e.response.status_code, url)
        return None
    except Exception:
        logger.error("[Firecrawl] /scrape failed for %s", url, exc_info=True)
        return None


async def search_web(
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search the web via Firecrawl /search.

    Args:
        query: Search query string.
        limit: Max results to return.

    Returns:
        List of result dicts with 'url', 'title', 'markdown', 'metadata'.
    """
    if not configured():
        logger.debug("Firecrawl not configured (no API key)")
        return []

    body: dict[str, Any] = {
        "query": query,
        "limit": min(limit, 20),
        "scrapeOptions": {"formats": ["markdown"]},
    }

    client = _get_client()
    try:
        resp = await client.post(
            f"{FIRECRAWL_BASE_URL}/search",
            headers=_headers(),
            json=body,
        )
        if resp.status_code == 429:
            logger.warning("[Firecrawl] Rate limited on /search for '%s'", query)
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except httpx.HTTPStatusError as e:
        logger.error("[Firecrawl] /search HTTP %d for '%s'", e.response.status_code, query)
        return []
    except Exception:
        logger.error("[Firecrawl] /search failed for '%s'", query, exc_info=True)
        return []


async def extract_structured(
    url: str,
    schema: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """
    Extract structured data from a URL using Firecrawl /scrape with extract format.

    Args:
        url: The URL to extract from.
        schema: JSON schema defining expected fields.

    Returns:
        Extracted dict matching the schema, or None on failure.
    """
    result = await scrape_url(url, formats=["extract"], extract_schema=schema)
    if result and "extract" in result:
        return result["extract"]
    return None


async def crawl_site(
    url: str,
    limit: int = 50,
    max_depth: int = 2,
) -> list[dict[str, Any]]:
    """
    Crawl a site starting from a URL via Firecrawl /crawl.

    Note: This is an async operation. We poll for results.

    Args:
        url: Starting URL.
        limit: Max pages to crawl.
        max_depth: Max link depth.

    Returns:
        List of page dicts with 'url', 'markdown', 'metadata'.
    """
    if not configured():
        logger.debug("Firecrawl not configured (no API key)")
        return []

    body: dict[str, Any] = {
        "url": url,
        "limit": min(limit, 100),
        "maxDepth": max_depth,
        "scrapeOptions": {"formats": ["markdown"]},
    }

    client = _get_client()
    try:
        # Initiate crawl
        resp = await client.post(
            f"{FIRECRAWL_BASE_URL}/crawl",
            headers=_headers(),
            json=body,
        )
        if resp.status_code == 429:
            logger.warning("[Firecrawl] Rate limited on /crawl for %s", url)
            return []
        resp.raise_for_status()
        data = resp.json()
        crawl_id = data.get("id")
        if not crawl_id:
            logger.error("[Firecrawl] /crawl returned no crawl ID for %s", url)
            return []

        # Poll for completion (max 5 minutes)
        import asyncio
        for _ in range(60):
            await asyncio.sleep(5)
            poll_resp = await client.get(
                f"{FIRECRAWL_BASE_URL}/crawl/{crawl_id}",
                headers=_headers(),
            )
            if poll_resp.status_code != 200:
                continue
            poll_data = poll_resp.json()
            status = poll_data.get("status", "")
            if status == "completed":
                return poll_data.get("data", [])
            if status in ("failed", "cancelled"):
                logger.error("[Firecrawl] Crawl %s %s for %s", crawl_id, status, url)
                return []

        logger.warning("[Firecrawl] Crawl %s timed out for %s", crawl_id, url)
        return []

    except httpx.HTTPStatusError as e:
        logger.error("[Firecrawl] /crawl HTTP %d for %s", e.response.status_code, url)
        return []
    except Exception:
        logger.error("[Firecrawl] /crawl failed for %s", url, exc_info=True)
        return []
