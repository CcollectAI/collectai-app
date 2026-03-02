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
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
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
from app.lib.region_marketplace_config import (
    should_use_adapter,
    get_ebay_marketplace_id,
    get_firecrawl_sites,
    get_crawl4ai_sites,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source reliability weights
# ---------------------------------------------------------------------------

SOURCE_RELIABILITY: Dict[str, float] = {
    "ebay_sold": 0.95,
    "tcgplayer": 0.90,
    "mavin": 0.80,
    "mavin_sold": 0.85,
    "mercari_us": 0.70,
    "mercari_us_sold": 0.75,
    "ebay_listed": 0.70,
    "whatnot": 0.65,
    "whatnot_sold": 0.75,
    "vinted": 0.65,
    "vinted_sold": 0.70,
    "firecrawl": 0.65,
    "firecrawl_sold": 0.70,
    "crawl4ai": 0.60,
    "crawl4ai_sold": 0.65,
    "catawiki": 0.80,
    "catawiki_sold": 0.90,
    "whisky_auctioneer": 0.85,
    "whisky_auctioneer_sold": 0.95,
    "mandarake": 0.75,
    "bezel": 0.80,
    "bezel_sold": 0.85,
    "chrono24": 0.70,
    "chrono24_sold": 0.75,
    "keh": 0.85,
    "mpb": 0.80,
    "drop": 0.75,
    "gouletpens": 0.80,
    "brickeconomy": 0.85,
    "brickeconomy_sold": 0.90,
    "popmart": 0.75,
    "booth": 0.70,
    "scalemates": 0.75,
    "ktown4u": 0.75,
    "comicbookrealm": 0.80,
    "comicbookrealm_sold": 0.85,
    "masterofmalt": 0.80,
}

# Bonus scores
RECENCY_7D_BOOST = 0.10
RECENCY_30D_BOOST = 0.05
SOLD_BONUS = 0.15
CONDITION_MATCH_BONUS = 0.10

# In-flight request dedup — concurrent identical searches wait for the first
# caller to finish rather than issuing duplicate adapter calls.
_inflight: Dict[str, asyncio.Future] = {}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScoredMarketHit:
    """A market hit enriched with provenance scoring."""
    hit: Dict[str, Any]
    provenance_score: float
    source_reliability: float
    recency_score: float
    is_sold: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hit": self.hit,
            "provenance_score": round(self.provenance_score, 4),
            "source_reliability": round(self.source_reliability, 4),
            "recency_score": round(self.recency_score, 4),
            "is_sold": self.is_sold,
        }


@dataclass
class AggregationResult:
    """Result of an aggregated marketplace search."""
    hits: List[ScoredMarketHit]
    total_sources_queried: int
    successful_sources: int
    aggregate_confidence: float
    dedup_count: int
    query_metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": [h.to_dict() for h in self.hits],
            "total_sources_queried": self.total_sources_queried,
            "successful_sources": self.successful_sources,
            "aggregate_confidence": round(self.aggregate_confidence, 4),
            "dedup_count": self.dedup_count,
            "query_metadata": self.query_metadata,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content_hash(source: str, raw_id: str) -> str:
    """Compute a SHA-256 content hash for deduplication."""
    payload = f"{source}:{raw_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_sold_date(sold_at: Optional[str]) -> Optional[datetime]:
    """Attempt to parse a sold/end date string into a datetime."""
    if not sold_at:
        return None
    # Try ISO 8601 first, then common variations
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(sold_at, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _compute_recency_score(sold_at: Optional[str]) -> float:
    """Compute recency score based on when the item sold."""
    if not sold_at:
        return 0.0
    dt = _parse_sold_date(sold_at)
    if not dt:
        return 0.0

    now = datetime.now(timezone.utc)
    age = now - dt
    if age <= timedelta(days=7):
        return RECENCY_7D_BOOST
    elif age <= timedelta(days=30):
        return RECENCY_30D_BOOST
    return 0.0


def _compute_provenance_score(
    hit: Dict[str, Any],
    query_condition: Optional[str] = None,
) -> tuple[float, float, float, bool]:
    """Compute provenance score for a single market hit.

    Returns (provenance_score, source_reliability, recency_score, is_sold).
    """
    source = hit.get("source", "")
    is_sold = bool(hit.get("is_sold", False))

    # Determine source reliability key
    if source == "ebay":
        reliability_key = "ebay_sold" if is_sold else "ebay_listed"
    elif source == "tcgplayer":
        reliability_key = "tcgplayer"
    else:
        reliability_key = source

    source_reliability = SOURCE_RELIABILITY.get(reliability_key, 0.50)

    # Recency boost
    recency_score = _compute_recency_score(hit.get("sold_at"))

    # Sold bonus
    sold_bonus = SOLD_BONUS if is_sold else 0.0

    # Condition match bonus
    condition_bonus = 0.0
    if query_condition and hit.get("condition"):
        hit_cond = str(hit.get("condition", "")).lower().strip()
        query_cond = query_condition.lower().strip()
        if query_cond in hit_cond or hit_cond in query_cond:
            condition_bonus = CONDITION_MATCH_BONUS

    provenance_score = min(
        1.0,
        source_reliability + recency_score + sold_bonus + condition_bonus,
    )

    return provenance_score, source_reliability, recency_score, is_sold


def _compute_aggregate_confidence(
    scored_hits: List[ScoredMarketHit],
    total_sources: int,
    successful_sources: int,
) -> float:
    """Compute aggregate confidence for the entire search.

    Weighted by provenance scores, source coverage, and result count.
    """
    if not scored_hits or total_sources == 0:
        return 0.0

    # Source coverage factor (0-0.4)
    coverage = (successful_sources / total_sources) * 0.4

    # Result depth factor (0-0.3) — more results = higher confidence, caps at 20
    result_depth = min(len(scored_hits) / 20.0, 1.0) * 0.3

    # Average provenance quality (0-0.3)
    avg_provenance = sum(h.provenance_score for h in scored_hits) / len(scored_hits)
    quality = avg_provenance * 0.3

    return min(1.0, coverage + result_depth + quality)


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

    @property
    def adapters_configured(self) -> Dict[str, bool]:
        """Return which adapters are configured."""
        return {
            "ebay": self._ebay.configured,
            "tcgplayer": self._tcgplayer.configured,
            "firecrawl": self._firecrawl.configured,
            "crawl4ai": self._crawl4ai.configured,
            "mercari_us": self._mercari_us.configured,
            "whatnot": self._whatnot.configured,
            "vinted": self._vinted.configured,
            "mavin": self._mavin.configured,
            "catawiki": self._catawiki.configured,
            "whisky_auctioneer": self._whisky_auctioneer.configured,
            "mandarake": self._mandarake.configured,
            "bezel": self._bezel.configured,
            "chrono24": self._chrono24.configured,
            "keh": self._keh.configured,
            "mpb": self._mpb.configured,
            "drop": self._drop.configured,
            "gouletpens": self._gouletpens.configured,
            "brickeconomy": self._brickeconomy.configured,
            "popmart": self._popmart.configured,
            "booth": self._booth.configured,
            "scalemates": self._scalemates.configured,
            "ktown4u": self._ktown4u.configured,
            "comicbookrealm": self._comicbookrealm.configured,
            "masterofmalt": self._masterofmalt.configured,
        }

    async def close(self) -> None:
        """Close all adapter HTTP clients."""
        await self._ebay.close()
        await self._tcgplayer.close()
        await self._firecrawl.close()
        await self._crawl4ai.close()
        await self._mercari_us.close()
        await self._whatnot.close()
        await self._vinted.close()
        await self._mavin.close()
        await self._catawiki.close()
        await self._whisky_auctioneer.close()
        await self._mandarake.close()
        await self._bezel.close()
        await self._chrono24.close()
        await self._keh.close()
        await self._mpb.close()
        await self._drop.close()
        await self._gouletpens.close()
        await self._brickeconomy.close()
        await self._popmart.close()
        await self._booth.close()
        await self._scalemates.close()
        await self._ktown4u.close()
        await self._comicbookrealm.close()
        await self._masterofmalt.close()

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
        all_hits: List[Dict[str, Any]] = []
        total_sources = 0
        successful_sources = 0
        source_errors: List[str] = []

        ebay_mktplace = get_ebay_marketplace_id(region)
        fc_sites = get_firecrawl_sites(region, category)
        c4_sites = get_crawl4ai_sites(region, category)

        # Determine which adapters to query
        tasks = []

        # eBay active listings
        if self._ebay.configured and should_use_adapter(region, "ebay"):
            total_sources += 1
            tasks.append(("ebay_listed", self._ebay.search(query, category=category, limit=limit, marketplace_id=ebay_mktplace)))

        # eBay sold comps
        if self._ebay.configured and include_sold and should_use_adapter(region, "ebay"):
            total_sources += 1
            tasks.append(("ebay_sold", self._ebay.sold_comps(query, category=category, limit=limit, marketplace_id=ebay_mktplace)))

        # TCGPlayer (only for TCG categories or if no category specified)
        tcg_categories = {"pokemon", "mtg", "yugioh", "lorcana"}
        if self._tcgplayer.configured and should_use_adapter(region, "tcgplayer") and (category is None or category in tcg_categories):
            total_sources += 1
            tasks.append(("tcgplayer", self._tcgplayer.search(query, category=category, limit=limit)))

        # Firecrawl (web search for sites without direct APIs)
        if self._firecrawl.configured and should_use_adapter(region, "firecrawl"):
            total_sources += 1
            tasks.append(("firecrawl", self._firecrawl.search(query, category=category, limit=limit, region_sites=fc_sites)))

        # Crawl4AI (local web crawler — parallel to Firecrawl)
        if self._crawl4ai.configured and should_use_adapter(region, "crawl4ai"):
            total_sources += 1
            tasks.append(("crawl4ai", self._crawl4ai.search(query, category=category, limit=limit, region_sites=c4_sites)))

        # Mercari US (broad collectible coverage)
        if self._mercari_us.configured and should_use_adapter(region, "mercari_us"):
            total_sources += 1
            tasks.append(("mercari_us", self._mercari_us.search(query, category=category, limit=limit)))

        # WhatNot (live auctions — TCG, Funko, sports cards)
        whatnot_categories = {"pokemon", "mtg", "yugioh", "lorcana", "funko", "sportscards", "designer_toys", "hot_toys", "anime_figures", "kpop_merch"}
        if self._whatnot.configured and should_use_adapter(region, "whatnot") and (category is None or category in whatnot_categories):
            total_sources += 1
            tasks.append(("whatnot", self._whatnot.search(query, category=category, limit=limit)))

        # Vinted (European secondhand marketplace)
        if self._vinted.configured and should_use_adapter(region, "vinted"):
            total_sources += 1
            tasks.append(("vinted", self._vinted.search(query, category=category, limit=limit, region=region)))

        # Mavin.io (sold price aggregator — high quality)
        if self._mavin.configured and should_use_adapter(region, "mavin"):
            total_sources += 1
            tasks.append(("mavin", self._mavin.search(query, category=category, limit=limit)))

        # Catawiki (European auction house — luxury/niche collectibles)
        catawiki_categories = {"whiskey", "vintage_cameras", "watches", "pens", "designer_toys", "comic_books"}
        if self._catawiki.configured and should_use_adapter(region, "catawiki") and (category is None or category in catawiki_categories):
            total_sources += 1
            tasks.append(("catawiki", self._catawiki.search(query, category=category, limit=limit)))

        # Whisky Auctioneer (world's largest online whisky auction)
        if self._whisky_auctioneer.configured and should_use_adapter(region, "whisky_auctioneer") and (category is None or category == "whiskey"):
            total_sources += 1
            tasks.append(("whisky_auctioneer", self._whisky_auctioneer.search(query, category=category, limit=limit)))

        # Mandarake (Japan's #1 collectible retailer — JP market)
        mandarake_categories = {"anime_figures", "bandai_premium", "ghibli", "jp_event", "jp_magazine", "hot_toys", "gunpla", "designer_toys", "manga", "vtuber"}
        if self._mandarake.configured and should_use_adapter(region, "mandarake") and (category is None or category in mandarake_categories):
            total_sources += 1
            tasks.append(("mandarake", self._mandarake.search(query, category=category, limit=limit)))

        # Bezel (trusted watch marketplace — US-focused)
        if self._bezel.configured and should_use_adapter(region, "bezel") and (category is None or category == "watches"):
            total_sources += 1
            tasks.append(("bezel", self._bezel.search(query, category=category, limit=limit)))

        # Chrono24 (world's largest watch marketplace — global)
        if self._chrono24.configured and should_use_adapter(region, "chrono24") and (category is None or category == "watches"):
            total_sources += 1
            tasks.append(("chrono24", self._chrono24.search(query, category=category, limit=limit)))

        # KEH (world's largest used camera dealer — professional grading)
        if self._keh.configured and should_use_adapter(region, "keh") and (category is None or category == "vintage_cameras"):
            total_sources += 1
            tasks.append(("keh", self._keh.search(query, category=category, limit=limit)))

        # MPB (major used camera marketplace — US + EU)
        if self._mpb.configured and should_use_adapter(region, "mpb") and (category is None or category == "vintage_cameras"):
            total_sources += 1
            tasks.append(("mpb", self._mpb.search(query, category=category, limit=limit, region=region)))

        # Drop.com (artisan keycap marketplace — US + EU)
        if self._drop.configured and should_use_adapter(region, "drop") and (category is None or category == "keycaps"):
            total_sources += 1
            tasks.append(("drop", self._drop.search(query, category=category, limit=limit)))

        # GouletPens (leading fountain pen retailer — US)
        if self._gouletpens.configured and should_use_adapter(region, "gouletpens") and (category is None or category == "pens"):
            total_sources += 1
            tasks.append(("gouletpens", self._gouletpens.search(query, category=category, limit=limit)))

        # BrickEconomy (LEGO value tracker — global)
        if self._brickeconomy.configured and should_use_adapter(region, "brickeconomy") and (category is None or category == "lego"):
            total_sources += 1
            tasks.append(("brickeconomy", self._brickeconomy.search(query, category=category, limit=limit)))

        # PopMart (leading blind box / designer toy marketplace — global)
        popmart_categories = {"blind_box", "designer_toys"}
        if self._popmart.configured and should_use_adapter(region, "popmart") and (category is None or category in popmart_categories):
            total_sources += 1
            tasks.append(("popmart", self._popmart.search(query, category=category, limit=limit)))

        # Booth.pm (Japanese indie/doujin marketplace — JP-focused)
        booth_categories = {"vtuber", "jp_event", "designer_toys", "kpop_lightsticks"}
        if self._booth.configured and should_use_adapter(region, "booth") and (category is None or category in booth_categories):
            total_sources += 1
            tasks.append(("booth", self._booth.search(query, category=category, limit=limit)))

        # ScaleMates (definitive scale model database — global)
        scalemates_categories = {"scale_models", "gunpla", "diecast"}
        if self._scalemates.configured and should_use_adapter(region, "scalemates") and (category is None or category in scalemates_categories):
            total_sources += 1
            tasks.append(("scalemates", self._scalemates.search(query, category=category, limit=limit)))

        # KTown4U (leading Korean K-pop merchandise retailer — KR-focused)
        ktown4u_categories = {"kpop", "kpop_lightsticks", "blind_box"}
        if self._ktown4u.configured and should_use_adapter(region, "ktown4u") and (category is None or category in ktown4u_categories):
            total_sources += 1
            tasks.append(("ktown4u", self._ktown4u.search(query, category=category, limit=limit)))

        # ComicBookRealm (comic book price guide — global)
        if self._comicbookrealm.configured and should_use_adapter(region, "comicbookrealm") and (category is None or category == "comic_books"):
            total_sources += 1
            tasks.append(("comicbookrealm", self._comicbookrealm.search(query, category=category, limit=limit)))

        # Master of Malt (UK whisky retailer — EU-focused)
        if self._masterofmalt.configured and should_use_adapter(region, "masterofmalt") and (category is None or category == "whiskey"):
            total_sources += 1
            tasks.append(("masterofmalt", self._masterofmalt.search(query, category=category, limit=limit)))

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

        # Deduplicate by content hash
        seen_hashes: set[str] = set()
        unique_hits: List[Dict[str, Any]] = []
        dedup_count = 0

        for hit in all_hits:
            ch = _content_hash(hit.get("source", ""), hit.get("raw_id", ""))
            if ch in seen_hashes:
                dedup_count += 1
                continue
            seen_hashes.add(ch)
            hit["content_hash"] = ch
            unique_hits.append(hit)

        # Score each hit
        scored_hits: List[ScoredMarketHit] = []
        for hit in unique_hits:
            prov, reliability, recency, is_sold = _compute_provenance_score(
                hit, query_condition=condition,
            )
            scored_hits.append(ScoredMarketHit(
                hit=hit,
                provenance_score=prov,
                source_reliability=reliability,
                recency_score=recency,
                is_sold=is_sold,
            ))

        # Sort by provenance score descending, then by price descending
        scored_hits.sort(key=lambda h: (h.provenance_score, h.hit.get("price", 0)), reverse=True)

        # Compute aggregate confidence
        aggregate_confidence = _compute_aggregate_confidence(
            scored_hits, total_sources, successful_sources,
        )

        result = AggregationResult(
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
            cache_set_fn(cache_key, result, cache_ttl)

        return result

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

        all_hits: List[Dict[str, Any]] = []
        total_sources = 0
        successful_sources = 0
        source_errors: List[str] = []

        ebay_mktplace = get_ebay_marketplace_id(region)
        fc_sites = get_firecrawl_sites(region, category)
        c4_sites = get_crawl4ai_sites(region, category)

        tasks = []

        # eBay sold comps
        if self._ebay.configured and should_use_adapter(region, "ebay"):
            total_sources += 1
            tasks.append(("ebay_sold", self._ebay.sold_comps(query, category=category, limit=limit, marketplace_id=ebay_mktplace)))

        # TCGPlayer sold comps
        tcg_categories = {"pokemon", "mtg", "yugioh", "lorcana"}
        if self._tcgplayer.configured and should_use_adapter(region, "tcgplayer") and (category is None or category in tcg_categories):
            total_sources += 1
            tasks.append(("tcgplayer_sold", self._tcgplayer.sold_comps(query, category=category, limit=limit)))

        # Firecrawl sold comps (web search)
        if self._firecrawl.configured and should_use_adapter(region, "firecrawl"):
            total_sources += 1
            tasks.append(("firecrawl_sold", self._firecrawl.sold_comps(query, category=category, limit=limit, region_sites=fc_sites)))

        # Crawl4AI sold comps (local web crawler)
        if self._crawl4ai.configured and should_use_adapter(region, "crawl4ai"):
            total_sources += 1
            tasks.append(("crawl4ai_sold", self._crawl4ai.sold_comps(query, category=category, limit=limit, region_sites=c4_sites)))

        # Mercari US sold comps
        if self._mercari_us.configured and should_use_adapter(region, "mercari_us"):
            total_sources += 1
            tasks.append(("mercari_us_sold", self._mercari_us.sold_comps(query, category=category, limit=limit)))

        # WhatNot sold comps (auction results)
        whatnot_categories = {"pokemon", "mtg", "yugioh", "lorcana", "funko", "sportscards", "designer_toys", "hot_toys", "anime_figures", "kpop_merch"}
        if self._whatnot.configured and should_use_adapter(region, "whatnot") and (category is None or category in whatnot_categories):
            total_sources += 1
            tasks.append(("whatnot_sold", self._whatnot.sold_comps(query, category=category, limit=limit)))

        # Vinted sold comps (European secondhand)
        if self._vinted.configured and should_use_adapter(region, "vinted"):
            total_sources += 1
            tasks.append(("vinted_sold", self._vinted.sold_comps(query, category=category, limit=limit, region=region)))

        # Mavin.io sold comps (aggregated sold data — highest quality)
        if self._mavin.configured and should_use_adapter(region, "mavin"):
            total_sources += 1
            tasks.append(("mavin_sold", self._mavin.sold_comps(query, category=category, limit=limit)))

        # Catawiki sold comps (European auction hammer prices)
        catawiki_categories = {"whiskey", "vintage_cameras", "watches", "pens", "designer_toys", "comic_books"}
        if self._catawiki.configured and should_use_adapter(region, "catawiki") and (category is None or category in catawiki_categories):
            total_sources += 1
            tasks.append(("catawiki_sold", self._catawiki.sold_comps(query, category=category, limit=limit)))

        # Whisky Auctioneer sold comps (real auction hammer prices — highest reliability for whisky)
        if self._whisky_auctioneer.configured and should_use_adapter(region, "whisky_auctioneer") and (category is None or category == "whiskey"):
            total_sources += 1
            tasks.append(("whisky_auctioneer_sold", self._whisky_auctioneer.sold_comps(query, category=category, limit=limit)))

        # Bezel sold comps (trusted watch marketplace)
        if self._bezel.configured and should_use_adapter(region, "bezel") and (category is None or category == "watches"):
            total_sources += 1
            tasks.append(("bezel_sold", self._bezel.sold_comps(query, category=category, limit=limit)))

        # Chrono24 sold comps (world's largest watch marketplace)
        if self._chrono24.configured and should_use_adapter(region, "chrono24") and (category is None or category == "watches"):
            total_sources += 1
            tasks.append(("chrono24_sold", self._chrono24.sold_comps(query, category=category, limit=limit)))

        # KEH sold comps (no sold history — returns empty)
        if self._keh.configured and should_use_adapter(region, "keh") and (category is None or category == "vintage_cameras"):
            total_sources += 1
            tasks.append(("keh_sold", self._keh.sold_comps(query, category=category, limit=limit)))

        # MPB sold comps (no sold history — returns empty)
        if self._mpb.configured and should_use_adapter(region, "mpb") and (category is None or category == "vintage_cameras"):
            total_sources += 1
            tasks.append(("mpb_sold", self._mpb.sold_comps(query, category=category, limit=limit, region=region)))

        # Drop sold comps (no sold history — returns empty)
        if self._drop.configured and should_use_adapter(region, "drop") and (category is None or category == "keycaps"):
            total_sources += 1
            tasks.append(("drop_sold", self._drop.sold_comps(query, category=category, limit=limit)))

        # GouletPens sold comps (no sold history — returns empty)
        if self._gouletpens.configured and should_use_adapter(region, "gouletpens") and (category is None or category == "pens"):
            total_sources += 1
            tasks.append(("gouletpens_sold", self._gouletpens.sold_comps(query, category=category, limit=limit)))

        # BrickEconomy sold comps (price history data — high quality for LEGO)
        if self._brickeconomy.configured and should_use_adapter(region, "brickeconomy") and (category is None or category == "lego"):
            total_sources += 1
            tasks.append(("brickeconomy_sold", self._brickeconomy.sold_comps(query, category=category, limit=limit)))

        # PopMart sold comps (retail site — no sold history, returns empty)
        popmart_categories = {"blind_box", "designer_toys"}
        if self._popmart.configured and should_use_adapter(region, "popmart") and (category is None or category in popmart_categories):
            total_sources += 1
            tasks.append(("popmart_sold", self._popmart.sold_comps(query, category=category, limit=limit)))

        # Booth sold comps (indie marketplace — no sold history, returns empty)
        booth_categories = {"vtuber", "jp_event", "designer_toys", "kpop_lightsticks"}
        if self._booth.configured and should_use_adapter(region, "booth") and (category is None or category in booth_categories):
            total_sources += 1
            tasks.append(("booth_sold", self._booth.sold_comps(query, category=category, limit=limit)))

        # ScaleMates sold comps (reference site — no sold history, returns empty)
        scalemates_categories = {"scale_models", "gunpla", "diecast"}
        if self._scalemates.configured and should_use_adapter(region, "scalemates") and (category is None or category in scalemates_categories):
            total_sources += 1
            tasks.append(("scalemates_sold", self._scalemates.sold_comps(query, category=category, limit=limit)))

        # KTown4U sold comps (retail storefront — no sold history, returns empty)
        ktown4u_categories = {"kpop", "kpop_lightsticks", "blind_box"}
        if self._ktown4u.configured and should_use_adapter(region, "ktown4u") and (category is None or category in ktown4u_categories):
            total_sources += 1
            tasks.append(("ktown4u_sold", self._ktown4u.sold_comps(query, category=category, limit=limit)))

        # ComicBookRealm sold comps (guide values as reference pricing)
        if self._comicbookrealm.configured and should_use_adapter(region, "comicbookrealm") and (category is None or category == "comic_books"):
            total_sources += 1
            tasks.append(("comicbookrealm_sold", self._comicbookrealm.sold_comps(query, category=category, limit=limit)))

        # Master of Malt sold comps (retail storefront — no sold history, returns empty)
        if self._masterofmalt.configured and should_use_adapter(region, "masterofmalt") and (category is None or category == "whiskey"):
            total_sources += 1
            tasks.append(("masterofmalt_sold", self._masterofmalt.sold_comps(query, category=category, limit=limit)))

        if not tasks:
            return AggregationResult(
                hits=[],
                total_sources_queried=0,
                successful_sources=0,
                aggregate_confidence=0.0,
                dedup_count=0,
                query_metadata={"query": query, "category": category, "region": region, "mode": "sold_comps"},
            )

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

        # Deduplicate
        seen_hashes: set[str] = set()
        unique_hits: List[Dict[str, Any]] = []
        dedup_count = 0

        for hit in all_hits:
            ch = _content_hash(hit.get("source", ""), hit.get("raw_id", ""))
            if ch in seen_hashes:
                dedup_count += 1
                continue
            seen_hashes.add(ch)
            hit["content_hash"] = ch
            unique_hits.append(hit)

        # Score
        scored_hits: List[ScoredMarketHit] = []
        for hit in unique_hits:
            prov, reliability, recency, is_sold = _compute_provenance_score(
                hit, query_condition=condition,
            )
            scored_hits.append(ScoredMarketHit(
                hit=hit,
                provenance_score=prov,
                source_reliability=reliability,
                recency_score=recency,
                is_sold=is_sold,
            ))

        scored_hits.sort(key=lambda h: (h.provenance_score, h.hit.get("price", 0)), reverse=True)

        aggregate_confidence = _compute_aggregate_confidence(
            scored_hits, total_sources, successful_sources,
        )

        result = AggregationResult(
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
            cache_set(cache_key, result, _COMPS_CACHE_TTL)

        return result

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
                                 condition, ended_at, url, normalized_key, features_json)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
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
                            {
                                "content_hash": hit.get("content_hash", ""),
                                "provenance_score": scored.provenance_score,
                                "source_reliability": scored.source_reliability,
                                "is_sold": scored.is_sold,
                            },
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
        if self._ebay.configured:
            tasks.append(("ebay", self._ebay.health_check()))
        else:
            checks["ebay"] = {"configured": False, "healthy": False}

        if self._tcgplayer.configured:
            tasks.append(("tcgplayer", self._tcgplayer.health_check()))
        else:
            checks["tcgplayer"] = {"configured": False, "healthy": False}

        if self._firecrawl.configured:
            tasks.append(("firecrawl", self._firecrawl.health_check()))
        else:
            checks["firecrawl"] = {"configured": False, "healthy": False}

        if self._crawl4ai.configured:
            tasks.append(("crawl4ai", self._crawl4ai.health_check()))
        else:
            checks["crawl4ai"] = {"configured": False, "healthy": False}

        if self._mercari_us.configured:
            tasks.append(("mercari_us", self._mercari_us.health_check()))
        else:
            checks["mercari_us"] = {"configured": False, "healthy": False}

        if self._whatnot.configured:
            tasks.append(("whatnot", self._whatnot.health_check()))
        else:
            checks["whatnot"] = {"configured": False, "healthy": False}

        if self._vinted.configured:
            tasks.append(("vinted", self._vinted.health_check()))
        else:
            checks["vinted"] = {"configured": False, "healthy": False}

        if self._mavin.configured:
            tasks.append(("mavin", self._mavin.health_check()))
        else:
            checks["mavin"] = {"configured": False, "healthy": False}

        if self._catawiki.configured:
            tasks.append(("catawiki", self._catawiki.health_check()))
        else:
            checks["catawiki"] = {"configured": False, "healthy": False}

        if self._whisky_auctioneer.configured:
            tasks.append(("whisky_auctioneer", self._whisky_auctioneer.health_check()))
        else:
            checks["whisky_auctioneer"] = {"configured": False, "healthy": False}

        if self._mandarake.configured:
            tasks.append(("mandarake", self._mandarake.health_check()))
        else:
            checks["mandarake"] = {"configured": False, "healthy": False}

        if self._bezel.configured:
            tasks.append(("bezel", self._bezel.health_check()))
        else:
            checks["bezel"] = {"configured": False, "healthy": False}

        if self._chrono24.configured:
            tasks.append(("chrono24", self._chrono24.health_check()))
        else:
            checks["chrono24"] = {"configured": False, "healthy": False}

        if self._keh.configured:
            tasks.append(("keh", self._keh.health_check()))
        else:
            checks["keh"] = {"configured": False, "healthy": False}

        if self._mpb.configured:
            tasks.append(("mpb", self._mpb.health_check()))
        else:
            checks["mpb"] = {"configured": False, "healthy": False}

        if self._drop.configured:
            tasks.append(("drop", self._drop.health_check()))
        else:
            checks["drop"] = {"configured": False, "healthy": False}

        if self._gouletpens.configured:
            tasks.append(("gouletpens", self._gouletpens.health_check()))
        else:
            checks["gouletpens"] = {"configured": False, "healthy": False}

        if self._brickeconomy.configured:
            tasks.append(("brickeconomy", self._brickeconomy.health_check()))
        else:
            checks["brickeconomy"] = {"configured": False, "healthy": False}

        if self._ktown4u.configured:
            tasks.append(("ktown4u", self._ktown4u.health_check()))
        else:
            checks["ktown4u"] = {"configured": False, "healthy": False}

        if self._comicbookrealm.configured:
            tasks.append(("comicbookrealm", self._comicbookrealm.health_check()))
        else:
            checks["comicbookrealm"] = {"configured": False, "healthy": False}

        if self._masterofmalt.configured:
            tasks.append(("masterofmalt", self._masterofmalt.health_check()))
        else:
            checks["masterofmalt"] = {"configured": False, "healthy": False}

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
