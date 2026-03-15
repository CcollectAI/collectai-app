"""
Crawl4AI client for CollectAI.

Open-source, Playwright-based web crawler providing:
- scrape_url()           -- scrape a single URL to markdown
- crawl_urls()           -- batch-crawl multiple URLs with concurrency control
- extract_structured()   -- CSS/XPath structured extraction
- crawl_site()           -- follow links from a start URL
- close()                -- shut down the Playwright browser

Env vars:
    CRAWL4AI_ENABLED         - "true" to enable (default: false)
    CRAWL4AI_MAX_CONCURRENT  - semaphore bound (default: 3)
    CRAWL4AI_TIMEOUT         - page timeout in seconds (default: 30)
    CRAWL4AI_HEADLESS        - headless browser mode (default: true)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.config import (
    CRAWL4AI_ENABLED,
    CRAWL4AI_HEADLESS,
    CRAWL4AI_MAX_CONCURRENT,
    CRAWL4AI_TIMEOUT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton crawler
# ---------------------------------------------------------------------------

_crawler: Any = None  # AsyncWebCrawler instance
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(CRAWL4AI_MAX_CONCURRENT)
    return _semaphore


async def _get_crawler() -> Any:
    """Return a lazily-initialised AsyncWebCrawler singleton."""
    global _crawler
    if _crawler is not None:
        return _crawler

    from crawl4ai import AsyncWebCrawler, BrowserConfig

    browser_cfg = BrowserConfig(headless=CRAWL4AI_HEADLESS)
    _crawler = AsyncWebCrawler(browser_config=browser_cfg)
    await _crawler.start()
    return _crawler


def configured() -> bool:
    """Return True if Crawl4AI is enabled via env var."""
    return CRAWL4AI_ENABLED


async def close() -> None:
    """Shut down the Playwright browser."""
    global _crawler
    if _crawler is not None:
        try:
            await _crawler.close()
        except Exception:
            logger.debug("[Crawl4AI] Error closing crawler", exc_info=True)
        _crawler = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def _raw_scrape_url(
    url: str,
    css_selector: Optional[str] = None,
    wait_for: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Internal: scrape via Crawl4AI without caching.
    """
    if not configured():
        logger.debug("[Crawl4AI] Not configured (CRAWL4AI_ENABLED is false)")
        return None

    from crawl4ai import CrawlerRunConfig

    run_cfg = CrawlerRunConfig(
        page_timeout=CRAWL4AI_TIMEOUT * 1000,  # ms
        css_selector=css_selector,
        wait_for=wait_for,
    )

    sem = _get_semaphore()
    async with sem:
        try:
            crawler = await _get_crawler()
            result = await crawler.arun(url=url, config=run_cfg)

            if not result.success:
                logger.warning("[Crawl4AI] scrape failed for %s: %s", url, result.error_message)
                return None

            return {
                "markdown": result.markdown or "",
                "metadata": {
                    "title": getattr(result, "title", "") or "",
                    "url": result.url or url,
                },
                "url": result.url or url,
            }
        except Exception:
            logger.error("[Crawl4AI] scrape_url failed for %s", url, exc_info=True)
            return None


async def scrape_url(
    url: str,
    css_selector: Optional[str] = None,
    wait_for: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Scrape a single URL via Crawl4AI with global URL dedup cache.

    Args:
        url: The URL to scrape.
        css_selector: Optional CSS selector to restrict extraction scope.
        wait_for: Optional CSS selector to wait for before scraping (for JS-heavy pages).

    Returns:
        Dict with keys 'markdown', 'metadata', 'url', or None on failure.
    """
    from app.lib.scrape_cache import ENRICH_CACHE_TTL, cached_scrape

    # When custom selectors are specified, bypass cache because the result
    # depends on the selector, not just the URL.
    if css_selector or wait_for:
        return await _raw_scrape_url(url, css_selector=css_selector, wait_for=wait_for)

    return await cached_scrape(
        url,
        lambda u: _raw_scrape_url(u),
        ttl=ENRICH_CACHE_TTL,
    )


async def crawl_urls(
    urls: list[str],
    css_selector: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Batch-crawl multiple URLs with concurrency control.

    Args:
        urls: List of URLs to crawl.
        css_selector: Optional CSS selector to restrict extraction scope.

    Returns:
        List of result dicts (failures are omitted).
    """
    if not configured():
        return []

    tasks = [scrape_url(u, css_selector=css_selector) for u in urls]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[dict[str, Any]] = []
    for r in raw:
        if isinstance(r, dict):
            results.append(r)
        elif isinstance(r, Exception):
            logger.warning("[Crawl4AI] batch item failed: %s", r)
    return results


async def extract_structured(
    url: str,
    css_selector: str,
    fields: Optional[dict[str, str]] = None,
) -> Optional[dict[str, Any]]:
    """
    Extract structured data from a URL using CSS selectors.

    Args:
        url: The URL to extract from.
        css_selector: Main CSS selector for the target content area.
        fields: Optional dict of field_name -> CSS selector for sub-extraction.

    Returns:
        Dict with 'markdown' and 'metadata', or None on failure.
    """
    return await scrape_url(url, css_selector=css_selector)


async def crawl_site(
    url: str,
    limit: int = 50,
    max_depth: int = 2,
) -> list[dict[str, Any]]:
    """
    Follow links from a start URL, crawling up to *limit* pages.

    Args:
        url: Starting URL.
        limit: Max pages to crawl.
        max_depth: Max link depth.

    Returns:
        List of page dicts with 'url', 'markdown', 'metadata'.
    """
    if not configured():
        logger.debug("[Crawl4AI] Not configured")
        return []

    # Scrape the seed page first
    seed = await scrape_url(url)
    if not seed:
        return []

    results = [seed]

    # Extract links from seed markdown for depth-1 crawling
    import re
    link_pattern = re.compile(r"\[.*?\]\((https?://[^\s)]+)\)")
    found_links = link_pattern.findall(seed.get("markdown", ""))

    # Filter to same domain
    from urllib.parse import urlparse
    seed_domain = urlparse(url).netloc
    same_domain_links = [
        link for link in found_links
        if urlparse(link).netloc == seed_domain
    ][:limit - 1]

    if same_domain_links and max_depth >= 1:
        child_results = await crawl_urls(same_domain_links)
        results.extend(child_results)

    return results[:limit]
