"""
Marketplace Aggregation Agent.

Orchestrates multiple market source adapters (eBay, TCGPlayer, future sources),
normalizes results, deduplicates hits, and computes provenance/confidence scores.

Usage:
    agent = MarketplaceAgent()
    result = await agent.aggregate_search("Charizard Base Set Holo", category="pokemon")
    comps  = await agent.find_sold_comps("Charizard Base Set Holo", category="pokemon")
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.agents.adapters.ebay_caller import EbayCaller
from app.agents.adapters.tcgplayer_caller import TCGPlayerCaller
from app.agents.adapters.firecrawl_caller import FirecrawlCaller
from app.agents.adapters.crawl4ai_caller import Crawl4AICaller
from app.agents.adapters.mercari_us_caller import MercariUSCaller
from app.agents.adapters.whatnot_caller import WhatNotCaller
from app.agents.adapters.vinted_caller import VintedCaller
from app.agents.adapters.mavin_caller import MavinCaller
from app.agents.adapters.catawiki_caller import CatawikiCaller
from app.agents.adapters.whisky_auctioneer_caller import WhiskyAuctioneerCaller
from app.agents.adapters.mandarake_caller import MandarakeCaller
from app.agents.adapters.bezel_caller import BezelCaller
from app.agents.adapters.chrono24_caller import Chrono24Caller
from app.agents.adapters.keh_caller import KEHCaller
from app.agents.adapters.mpb_caller import MPBCaller
from app.agents.adapters.drop_caller import DropCaller
from app.agents.adapters.gouletpens_caller import GouletPensCaller
from app.agents.adapters.brickeconomy_caller import BrickEconomyCaller
from app.agents.adapters.popmart_caller import PopMartCaller
from app.agents.adapters.booth_caller import BoothCaller
from app.agents.adapters.scalemates_caller import ScaleMatesCaller
from app.agents.adapters.ktown4u_caller import KTown4UCaller
from app.agents.adapters.comicbookrealm_caller import ComicBookRealmCaller
from app.agents.adapters.masterofmalt_caller import MasterOfMaltCaller
from app.agents.adapters.pricecharting_caller import PriceChartingCaller
from app.agents.adapters.yahoo_auctions_caller import YahooAuctionsCaller
from app.agents.adapters.stockx_caller import StockXCaller
from app.agents.adapters.discogs_caller import DiscogsCaller
from app.agents.adapters.cardmarket_caller import CardmarketCaller
from app.agents.adapters.bricklink_caller import BrickLinkCaller
from app.agents.adapters.scrapedo_caller import ScrapedoCaller
from app.agents.adapters.grailed_caller import GrailedCaller
from app.agents.adapters.google_shopping_caller import GoogleShoppingCaller
from app.agents.adapters.etsy_caller import EtsyCaller
from app.agents.adapters.comc_caller import COMCCaller
from app.agents.adapters.reverb_caller import ReverbCaller
from app.agents.adapters.abebooks_caller import AbeBooksCaller
from app.lib.region_marketplace_config import (
    should_use_adapter,
    get_ebay_marketplace_id,
    get_firecrawl_sites,
    get_crawl4ai_sites,
)

# Re-export routing config and helpers so existing imports keep working
from app.agents.marketplace_routing import (  # noqa: F401
    SOURCE_RELIABILITY,
    RECENCY_7D_BOOST,
    RECENCY_30D_BOOST,
    SOLD_BONUS,
    CONDITION_MATCH_BONUS,
    ADAPTER_CATEGORY_ROUTING,
    adapter_serves_category,
)
from app.agents.marketplace_helpers import (  # noqa: F401
    ScoredMarketHit,
    AggregationResult,
    _content_hash,
    _parse_sold_date,
    _compute_recency_score,
    _compute_provenance_score,
    _compute_aggregate_confidence,
    dedup_and_score,
    _inflight,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class MarketplaceAgent:
    """Marketplace Aggregation Agent.

    Orchestrates multiple adapters, deduplicates, scores, and returns
    structured AggregationResult objects.
    """

    def __init__(self) -> None:
        self._ebay = EbayCaller()
        self._tcgplayer = TCGPlayerCaller()
        self._firecrawl = FirecrawlCaller()
        self._crawl4ai = Crawl4AICaller()
        self._mercari_us = MercariUSCaller()
        self._whatnot = WhatNotCaller()
        self._vinted = VintedCaller()
        self._mavin = MavinCaller()
        self._catawiki = CatawikiCaller()
        self._whisky_auctioneer = WhiskyAuctioneerCaller()
        self._mandarake = MandarakeCaller()
        self._bezel = BezelCaller()
        self._chrono24 = Chrono24Caller()
        self._keh = KEHCaller()
        self._mpb = MPBCaller()
        self._drop = DropCaller()
        self._gouletpens = GouletPensCaller()
        self._brickeconomy = BrickEconomyCaller()
        self._popmart = PopMartCaller()
        self._booth = BoothCaller()
        self._scalemates = ScaleMatesCaller()
        self._ktown4u = KTown4UCaller()
        self._comicbookrealm = ComicBookRealmCaller()
        self._masterofmalt = MasterOfMaltCaller()
        self._pricecharting = PriceChartingCaller()
        self._yahoo_auctions = YahooAuctionsCaller()
        self._stockx = StockXCaller()
        self._discogs = DiscogsCaller()
        self._cardmarket = CardmarketCaller()
        self._bricklink = BrickLinkCaller()
        self._scrapedo = ScrapedoCaller()
        self._grailed = GrailedCaller()
        self._google_shopping = GoogleShoppingCaller()
        self._etsy = EtsyCaller()
        self._comc = COMCCaller()
        self._reverb = ReverbCaller()
        self._abebooks = AbeBooksCaller()

    # Map adapter name -> (instance, extra_kwargs_builder | None)
    # This keeps the routing DRY between aggregate_search and find_sold_comps.
    def _adapter_map(self) -> Dict[str, Any]:
        """Return name->instance mapping for all adapters."""
        return {
            "ebay": self._ebay,
            "tcgplayer": self._tcgplayer,
            "firecrawl": self._firecrawl,
            "crawl4ai": self._crawl4ai,
            "mercari_us": self._mercari_us,
            "whatnot": self._whatnot,
            "vinted": self._vinted,
            "mavin": self._mavin,
            "catawiki": self._catawiki,
            "whisky_auctioneer": self._whisky_auctioneer,
            "mandarake": self._mandarake,
            "bezel": self._bezel,
            "chrono24": self._chrono24,
            "keh": self._keh,
            "mpb": self._mpb,
            "drop": self._drop,
            "gouletpens": self._gouletpens,
            "brickeconomy": self._brickeconomy,
            "popmart": self._popmart,
            "booth": self._booth,
            "scalemates": self._scalemates,
            "ktown4u": self._ktown4u,
            "comicbookrealm": self._comicbookrealm,
            "masterofmalt": self._masterofmalt,
            "pricecharting": self._pricecharting,
            "yahoo_auctions": self._yahoo_auctions,
            "stockx": self._stockx,
            "discogs": self._discogs,
            "cardmarket": self._cardmarket,
            "bricklink": self._bricklink,
            "scrapedo": self._scrapedo,
            "grailed": self._grailed,
            "google_shopping": self._google_shopping,
            "etsy": self._etsy,
            "comc": self._comc,
            "reverb": self._reverb,
            "abebooks": self._abebooks,
        }

    @property
    def adapters_configured(self) -> Dict[str, bool]:
        """Return which adapters are configured."""
        return {name: inst.configured for name, inst in self._adapter_map().items()}

    async def close(self) -> None:
        """Close all adapter HTTP clients."""
        for inst in self._adapter_map().values():
            await inst.close()

    # ------------------------------------------------------------------
    # Internal: build task list from routing config
    # ------------------------------------------------------------------

    def _build_search_tasks(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        region: Optional[str],
        mode: str = "search",
    ) -> tuple[list[tuple[str, Any]], int]:
        """Build the list of (source_name, coroutine) tasks.

        *mode* is "search" for aggregate_search or "sold" for find_sold_comps.

        Returns (tasks, total_sources).
        """
        tasks: list[tuple[str, Any]] = []
        total_sources = 0

        ebay_mktplace = get_ebay_marketplace_id(region)
        fc_sites = get_firecrawl_sites(region, category)
        c4_sites = get_crawl4ai_sites(region, category)

        amap = self._adapter_map()

        for adapter_name, inst in amap.items():
            if not inst.configured:
                continue
            if not should_use_adapter(region, adapter_name):
                continue
            if not adapter_serves_category(adapter_name, category):
                continue

            # Build kwargs for this adapter
            kw: Dict[str, Any] = {"query": query, "category": category, "limit": limit}

            if adapter_name == "ebay":
                kw["marketplace_id"] = ebay_mktplace
            elif adapter_name == "firecrawl":
                kw["region_sites"] = fc_sites
            elif adapter_name == "crawl4ai":
                kw["region_sites"] = c4_sites
            elif adapter_name in ("vinted", "mpb"):
                kw["region"] = region
            elif adapter_name == "google_shopping":
                kw["region"] = region

            if mode == "search":
                # eBay gets two tasks: listed + sold
                if adapter_name == "ebay":
                    total_sources += 1
                    tasks.append(("ebay_listed", inst.search(**kw)))
                    total_sources += 1
                    kw_sold = dict(kw)
                    tasks.append(("ebay_sold", inst.sold_comps(**kw_sold)))
                else:
                    total_sources += 1
                    tasks.append((adapter_name, inst.search(**kw)))
            else:
                # sold comps mode
                if adapter_name == "ebay":
                    total_sources += 1
                    tasks.append(("ebay_sold", inst.sold_comps(**kw)))
                elif adapter_name == "google_shopping":
                    # Google Shopping has no sold comps — skip
                    continue
                else:
                    total_sources += 1
                    suffix = f"{adapter_name}_sold" if not adapter_name.endswith("_sold") else adapter_name
                    if hasattr(inst, "sold_comps"):
                        tasks.append((suffix, inst.sold_comps(**kw)))
                    else:
                        tasks.append((suffix, inst.search(**kw)))

        return tasks, total_sources

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

    async def aggregate_search(
        self,
        query: str,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        limit: int = 20,
        include_sold: bool = True,
        region: Optional[str] = None,
    ) -> AggregationResult:
        """Search across all configured marketplace adapters.

        Deduplicates results, computes provenance scores, and returns
        an AggregationResult with aggregate confidence.

        *region* (americas/europe/japan/other) gates adapters and targets
        region-specific eBay marketplaces and Firecrawl sites.

        Results are cached for 6 hours by (query, category, condition, region).
        """
        # Check cache first — identical searches within TTL reuse previous results
        from app.cache import cache_get, cache_set
        _SEARCH_CACHE_TTL = 6 * 3600  # 6 hours
        cache_key = f"mkt_search:{query}:{category}:{condition}:{region}:{include_sold}"
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug("[MarketplaceAgent] cache hit for %s", cache_key)
            return cached

        # In-flight dedup: if an identical search is already running, await it
        if cache_key in _inflight:
            logger.debug("[MarketplaceAgent] dedup — waiting for in-flight %s", cache_key)
            return await _inflight[cache_key]

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        _inflight[cache_key] = future
        try:
            result = await self._do_aggregate_search(
                query, category, condition, limit, include_sold, region,
                cache_key, _SEARCH_CACHE_TTL, cache_set,
            )
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            _inflight.pop(cache_key, None)

    async def _do_aggregate_search(
        self,
        query: str,
        category: Optional[str],
        condition: Optional[str],
        limit: int,
        include_sold: bool,
        region: Optional[str],
        cache_key: str,
        cache_ttl: int,
        cache_set_fn,
    ) -> AggregationResult:
        """Internal: perform the actual adapter queries (called after cache miss)."""
        tasks, total_sources = self._build_search_tasks(
            query, category, limit, region, mode="search",
        )

        if not tasks:
            logger.warning("[MarketplaceAgent] No adapters configured for query: %s", query)
            return AggregationResult(
                hits=[],
                total_sources_queried=0,
                successful_sources=0,
                aggregate_confidence=0.0,
                dedup_count=0,
                query_metadata={"query": query, "category": category, "region": region},
            )

        all_hits: List[Dict[str, Any]] = []
        successful_sources = 0
        source_errors: List[str] = []

        # Execute all adapter queries concurrently
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True,
        )

        for (source_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error("[MarketplaceAgent] %s failed: %s", source_name, result)
                source_errors.append(source_name)
            elif isinstance(result, list):
                successful_sources += 1
                all_hits.extend(result)
            else:
                logger.warning("[MarketplaceAgent] %s returned unexpected type: %s", source_name, type(result))

        # Deduplicate and score
        scored_hits, dedup_count = dedup_and_score(all_hits, condition=condition)

        # Compute aggregate confidence
        aggregate_confidence = _compute_aggregate_confidence(
            scored_hits, total_sources, successful_sources,
        )

        agg_result = AggregationResult(
            hits=scored_hits,
            total_sources_queried=total_sources,
            successful_sources=successful_sources,
            aggregate_confidence=aggregate_confidence,
            dedup_count=dedup_count,
            query_metadata={
                "query": query,
                "category": category,
                "condition": condition,
                "limit": limit,
                "include_sold": include_sold,
                "region": region,
                "source_errors": source_errors,
            },
        )

        # Cache successful results
        if scored_hits:
            cache_set_fn(cache_key, agg_result, cache_ttl)

        return agg_result

    # ------------------------------------------------------------------
    # Sold comps + DB persistence
    # ------------------------------------------------------------------

    async def find_sold_comps(
        self,
        query: str,
        category: Optional[str] = None,
        condition: Optional[str] = None,
        limit: int = 20,
        region: Optional[str] = None,
    ) -> AggregationResult:
        """Find sold comparables across all adapters.

        Only returns sold/completed items for price estimation.
        Results are cached for 12 hours since sold data changes slowly.
        """
        from app.cache import cache_get, cache_set
        _COMPS_CACHE_TTL = 12 * 3600  # 12 hours
        cache_key = f"mkt_comps:{query}:{category}:{condition}:{region}"
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug("[MarketplaceAgent] comps cache hit for %s", cache_key)
            return cached

        tasks, total_sources = self._build_search_tasks(
            query, category, limit, region, mode="sold",
        )

        if not tasks:
            return AggregationResult(
                hits=[],
                total_sources_queried=0,
                successful_sources=0,
                aggregate_confidence=0.0,
                dedup_count=0,
                query_metadata={"query": query, "category": category, "region": region, "mode": "sold_comps"},
            )

        all_hits: List[Dict[str, Any]] = []
        successful_sources = 0
        source_errors: List[str] = []

        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True,
        )

        for (source_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error("[MarketplaceAgent] %s failed: %s", source_name, result)
                source_errors.append(source_name)
            elif isinstance(result, list):
                successful_sources += 1
                all_hits.extend(result)

        # Deduplicate and score
        scored_hits, dedup_count = dedup_and_score(all_hits, condition=condition)

        aggregate_confidence = _compute_aggregate_confidence(
            scored_hits, total_sources, successful_sources,
        )

        agg_result = AggregationResult(
            hits=scored_hits,
            total_sources_queried=total_sources,
            successful_sources=successful_sources,
            aggregate_confidence=aggregate_confidence,
            dedup_count=dedup_count,
            query_metadata={
                "query": query,
                "category": category,
                "condition": condition,
                "limit": limit,
                "region": region,
                "mode": "sold_comps",
                "source_errors": source_errors,
            },
        )

        # Cache successful results
        if scored_hits:
            cache_set(cache_key, agg_result, _COMPS_CACHE_TTL)

        return agg_result

    async def persist_comps_to_db(
        self,
        result: AggregationResult,
        normalized_key: Optional[str] = None,
    ) -> int:
        """Persist scored market hits to the market_hits table.

        Returns the number of rows inserted.
        """
        try:
            from app.db import get_conn, db_configured
        except ImportError:
            logger.warning("[MarketplaceAgent] DB module not available")
            return 0

        if not db_configured():
            logger.info("[MarketplaceAgent] DB not configured, skipping persistence")
            return 0

        inserted = 0
        try:
            async with get_conn() as conn:
                for scored in result.hits:
                    hit = scored.hit
                    try:
                        await conn.execute(
                            """
                            INSERT INTO market_hits
                                (provider, listing_id, title, price, currency,
                                 condition, ended_at, url, normalized_key, item_ref, features_json)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            ON CONFLICT (provider, listing_id) DO NOTHING
                            """,
                            hit.get("source", ""),
                            hit.get("raw_id", ""),
                            hit.get("title", ""),
                            hit.get("price"),
                            hit.get("currency", "EUR"),
                            hit.get("condition"),
                            _parse_sold_date(hit.get("sold_at")),
                            hit.get("url"),
                            normalized_key,
                            normalized_key,  # item_ref = normalized_key for valuation worker
                            json.dumps({
                                "content_hash": hit.get("content_hash", ""),
                                "provenance_score": scored.provenance_score,
                                "source_reliability": scored.source_reliability,
                                "is_sold": scored.is_sold,
                            }),
                        )
                        inserted += 1
                    except Exception:
                        logger.warning(
                            "[MarketplaceAgent] Failed to insert hit %s:%s",
                            hit.get("source"), hit.get("raw_id"),
                            exc_info=True,
                        )
        except RuntimeError as e:
            logger.warning("[MarketplaceAgent] DB connection error: %s", e)
        except Exception:
            logger.error("[MarketplaceAgent] DB persistence failed", exc_info=True)

        logger.info("[MarketplaceAgent] Persisted %d/%d hits to market_hits", inserted, len(result.hits))
        return inserted

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all configured adapters."""
        checks: Dict[str, Any] = {}
        tasks = []

        for name, inst in self._adapter_map().items():
            if inst.configured:
                tasks.append((name, inst.health_check()))
            else:
                checks[name] = {"configured": False, "healthy": False}

        if tasks:
            results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True,
            )
            for (name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    checks[name] = {"configured": True, "healthy": False, "error": str(result)}
                else:
                    checks[name] = {"configured": True, "healthy": bool(result)}

        return {
            "adapters": checks,
            "any_healthy": any(
                v.get("healthy", False) for v in checks.values()
            ),
        }
