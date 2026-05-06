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
from app.agents.adapters.suruga_ya_caller import SurugaYaCaller
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
        self._suruga_ya = SurugaYaCaller()
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
            # "vinted": self._vinted,  # DE-REGISTERED 2026-04-28 — circuit
            # OPEN >24h, structurally bot-blocked (HTTP 403 every call). Cooldown
            # was bumped to 6h on 2026-04-27 (commit 0571fa6) to stop flap noise,
            # but the OPEN-monitor still pages at 24h. Removing from the adapter
            # map stops dispatch entirely. Re-enable if Vinted's bot detection
            # ever lifts our IP block — verify by `curl https://www.vinted.fr/api/v2/catalog/items?search_text=test`
            # and only un-comment when that returns 200.
            "mavin": self._mavin,
            "catawiki": self._catawiki,
            "whisky_auctioneer": self._whisky_auctioneer,
            "suruga_ya": self._suruga_ya,
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
        category: Optional[str] = None,
    ) -> int:
        """Persist scored market hits to the market_hits table.

        Populates `market_hits.attrs` with structured listing attributes
        (normalized via attribute_normalizer) so the data flywheel can
        aggregate them into category_items.attributes_json.market_observed.

        Returns the number of rows inserted.
        """
        try:
            from app.db import db_configured
        except ImportError:
            logger.warning("[MarketplaceAgent] DB module not available")
            return 0

        if not db_configured():
            logger.info("[MarketplaceAgent] DB not configured, skipping persistence")
            return 0

        # Attribute normalizer (optional — import lazily to avoid hard coupling)
        try:
            from app.ml.attribute_normalizer import normalize_attributes
        except Exception:
            normalize_attributes = None

        inserted = 0
        # Use DB_DSN_DIRECT instead of the pooler to bypass the 30s
        # statement timeout. The per-row INSERT ... WHERE NOT EXISTS has to
        # probe across all market_hits partitions; with growing partition
        # count + occasionally stale stats, even a single hit can exceed the
        # pooler cap and silently fail (verified 2026-04-27 — every row in
        # a 152s marketplace_scrape cycle hit TimeoutError, leading to
        # `Persisted 0/N` on every batch and tripping the silent-writer probe).
        # Same pattern marketplace_scrape_scheduler adopted on 2026-04-25.
        import asyncpg as _asyncpg
        import os as _os
        _direct_dsn = _os.getenv("DB_DSN_DIRECT") or _os.getenv("DB_DSN")
        try:
            # Import FX conversion — all prices stored as EUR
            try:
                from app.lib.fx_service import convert_to_eur
            except ImportError:
                convert_to_eur = None

            conn = await _asyncpg.connect(_direct_dsn)
            try:
                # Writer-side sanity filter — reject crawler garbage BEFORE it
                # pollutes market_hits. Seen 2026-04-20: 289 rows of Crawl4AI
                # scraping "Site Statistics" pages on LEGO category pages and
                # parsing the trending-stats number ($1,546,171,702.71) as a
                # product price. Same class of bug as learning #25. The €20M
                # sanity_probe catches these AFTER ingestion, but the fix
                # belongs at the writer: listings above €1M are extraordinary
                # outliers and almost always parse errors for our categories.
                _WRITE_PRICE_CEILING_EUR = 1_000_000
                _GARBAGE_TITLES = {
                    "site statistics", "statistics", "trending", "new listings",
                    "recently sold", "most watched", "unknown", "n/a",
                }

                for scored in result.hits:
                    hit = scored.hit
                    # Skip zero/null prices — these skew training and valuations
                    if not hit.get("price") or float(hit.get("price", 0)) <= 0:
                        continue
                    # Skip crawler-garbage titles — parsed from metadata pages
                    # rather than real product listings.
                    _title_norm = str(hit.get("title") or "").strip().lower()
                    if _title_norm in _GARBAGE_TITLES or not _title_norm:
                        continue
                    # Normalize price to EUR
                    raw_price = hit.get("price")
                    raw_currency = hit.get("currency", "EUR")
                    if raw_price and raw_currency != "EUR" and convert_to_eur:
                        try:
                            # convert_to_eur is async — missing await meant
                            # price_eur was a coroutine that serialised into
                            # JSON as "Object of type coroutine is not JSON
                            # serializable" and dropped whole batches (learning
                            # 2026-04-18).
                            price_eur = await convert_to_eur(float(raw_price), raw_currency)
                        except Exception:
                            price_eur = raw_price  # fallback: store as-is
                    else:
                        price_eur = raw_price

                    # Writer-side price ceiling — see _WRITE_PRICE_CEILING_EUR
                    # comment above. Drop obvious parse errors before they
                    # reach market_hits.
                    try:
                        if price_eur is not None and float(price_eur) > _WRITE_PRICE_CEILING_EUR:
                            logger.warning(
                                "[MarketplaceAgent] Dropping hit: price_eur=%s > €%d ceiling (title=%r provider=%s)",
                                price_eur, _WRITE_PRICE_CEILING_EUR, hit.get("title"), hit.get("provider"),
                            )
                            continue
                    except (TypeError, ValueError):
                        continue

                    # Structured attributes — normalize to canonical vocab
                    raw_attrs = hit.get("attributes") or {}
                    if not isinstance(raw_attrs, dict):
                        raw_attrs = {}
                    if normalize_attributes and category and raw_attrs:
                        try:
                            normed, _log = normalize_attributes(category, raw_attrs)
                            if isinstance(normed, dict):
                                raw_attrs = normed
                        except Exception:
                            pass

                    # Category defaults from the caller arg, but fall back to
                    # the item_ref prefix when caller didn't pass one. Without
                    # this, eBay/Vinted/Crawl4AI cycles persisted 59k rows
                    # with NULL category (2026-04-19 audit: 15.7% null_category_rate)
                    # even though item_ref had the `category:` prefix.
                    resolved_category = category
                    if not resolved_category and normalized_key and ":" in normalized_key:
                        resolved_category = normalized_key.split(":", 1)[0]

                    # item_ref must be the canonical `{category}:{key}` form
                    # (learnings.md §22, §64, root-cause essay post-write rule).
                    # Callers are inconsistent: marketplace_scrape_scheduler
                    # passes pre-prefixed normalized_key; adapter sites pass
                    # bare keys. Until 2026-04-21 this column was assigned
                    # `normalized_key` verbatim, producing 2,039 malformed
                    # rows/day from bare-key callers. Accept either shape and
                    # always emit the prefixed form.
                    if normalized_key and ":" in normalized_key:
                        item_ref = normalized_key
                    elif resolved_category and normalized_key:
                        item_ref = f"{resolved_category}:{normalized_key}"
                    else:
                        item_ref = None

                    try:
                        # WHERE NOT EXISTS (not ON CONFLICT) because market_hits
                        # was partitioned by seen_at on 2026-04-19 and Postgres
                        # requires partition-key columns in any unique index on
                        # a partitioned table — so ON CONFLICT (provider,
                        # listing_id) raises 42P10 "no matching unique or
                        # exclusion constraint" every time. WHERE NOT EXISTS
                        # uses the (provider, listing_id, seen_at) composite
                        # index for a fast existence probe that works across
                        # partitions.
                        # source + marketplace mirror provider so downstream
                        # filters ("show me only ebay") and intelligence
                        # queries don't silently match nothing. Both were
                        # NULL on every row for weeks until 2026-04-29.
                        adapter_id = hit.get("source", "") or ""
                        await conn.execute(
                            """
                            INSERT INTO market_hits
                                (provider, source, marketplace,
                                 listing_id, title, price, currency,
                                 price_eur,
                                 condition, ended_at, url, normalized_key, item_ref,
                                 category,
                                 features_json,
                                 attrs,
                                 observed_at,
                                 is_listing)
                            -- observed_at = sold_at when present, else now() — readers
                            -- (valuation_worker, explainer, train_price) order/decay on
                            -- this column. Pre-2026-05-02 it was NULL on every row →
                            -- temporal-decay weighting collapsed to a constant.
                            -- is_listing = (no sold_at) — listings are asking prices,
                            -- sold rows have ended_at populated. Pre-2026-05-02 this
                            -- was NULL on every per-row INSERT (only the bulk RPC set
                            -- it), so valuation_worker filter `is_listing IS NOT TRUE`
                            -- treated all NULLs as sold. Mostly harmless but
                            -- semantically wrong; downstream `_build_evidence`
                            -- couldn't distinguish.
                            SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                                   COALESCE($10, now()),
                                   ($10 IS NULL)
                            WHERE NOT EXISTS (
                              SELECT 1 FROM market_hits
                              WHERE provider = $1 AND listing_id = $4
                            )
                            """,
                            adapter_id,          # provider (canonical adapter id)
                            adapter_id,          # source (mirror — analytics filter on this)
                            adapter_id,          # marketplace (mirror — customer-facing facet)
                            hit.get("raw_id", ""),
                            hit.get("title", ""),
                            raw_price,           # original price in original currency
                            raw_currency,        # original currency (USD, EUR, JPY, etc.)
                            price_eur,           # normalized EUR for training/valuation
                            hit.get("condition"),
                            _parse_sold_date(hit.get("sold_at")),
                            hit.get("url"),
                            normalized_key,
                            item_ref,
                            resolved_category,
                            json.dumps({
                                "content_hash": hit.get("content_hash", ""),
                                "provenance_score": scored.provenance_score,
                                "source_reliability": scored.source_reliability,
                                "is_sold": scored.is_sold,
                            }),
                            json.dumps(raw_attrs),  # asyncpg jsonb needs str (learnings #18)
                        )
                        inserted += 1
                    except Exception:
                        logger.warning(
                            "[MarketplaceAgent] Failed to insert hit %s:%s",
                            hit.get("source"), hit.get("raw_id"),
                            exc_info=True,
                        )
            finally:
                try:
                    await conn.close()
                except Exception:
                    pass
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
