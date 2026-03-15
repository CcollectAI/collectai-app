"""
Smart scrape: Crawl4AI-first with Firecrawl fallback.

Provides a unified scraping interface that tries the free, self-hosted
Crawl4AI first and falls back to the paid Firecrawl API if Crawl4AI
fails or is not configured.

Public API:
    smart_scrape()      -- scrape a single URL (markdown + metadata)
    smart_search_web()  -- web search (Firecrawl-only, Crawl4AI has no search)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.lib import crawl4ai_client, firecrawl_client

logger = logging.getLogger(__name__)


async def smart_scrape(
    url: str,
    formats: list[str] | None = None,
    extract_schema: dict[str, Any] | None = None,
    css_selector: str | None = None,
) -> Optional[dict[str, Any]]:
    """
    Scrape a single URL, trying Crawl4AI first then Firecrawl.

    Args:
        url: The URL to scrape.
        formats: Output formats for Firecrawl (default: ["markdown"]).
                 Crawl4AI always returns markdown.
        extract_schema: JSON schema for Firecrawl structured extraction.
                        If provided and Crawl4AI succeeds, the result will
                        only contain markdown (no 'extract' key) — callers
                        should handle this gracefully.
        css_selector: Optional CSS selector to restrict extraction scope
                      (passed to Crawl4AI).

    Returns:
        Dict with 'markdown', 'metadata', 'url', and optionally 'extract',
        or None if both scrapers fail.
    """
    # --- Try Crawl4AI first (free, self-hosted) ---
    if crawl4ai_client.configured():
        try:
            result = await crawl4ai_client.scrape_url(
                url, css_selector=css_selector,
            )
            if result and result.get("markdown"):
                logger.debug("[smart_scrape] Crawl4AI succeeded for %s", url)
                return result
            logger.debug(
                "[smart_scrape] Crawl4AI returned empty for %s, falling back",
                url,
            )
        except Exception as e:
            logger.debug(
                "[smart_scrape] Crawl4AI failed for %s: %s, falling back to Firecrawl",
                url, e,
            )

    # --- Fall back to Firecrawl (paid API) ---
    if firecrawl_client.configured():
        try:
            result = await firecrawl_client.scrape_url(
                url, formats=formats, extract_schema=extract_schema,
            )
            if result:
                logger.debug("[smart_scrape] Firecrawl succeeded for %s", url)
            return result
        except Exception as e:
            logger.error(
                "[smart_scrape] Firecrawl also failed for %s: %s",
                url, e, exc_info=True,
            )
            return None

    logger.warning("[smart_scrape] No scraper configured for %s", url)
    return None


async def smart_search_web(
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Web search — delegates to Firecrawl (Crawl4AI has no search endpoint).

    Falls through silently if Firecrawl is not configured.
    """
    if firecrawl_client.configured():
        return await firecrawl_client.search_web(query, limit=limit)
    logger.warning("[smart_search_web] Firecrawl not configured — cannot search")
    return []
