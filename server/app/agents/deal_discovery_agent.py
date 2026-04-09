"""
Deal Discovery Agent — orchestrates marketplace scanning for purchase mandates.

Reuses MarketplaceAgent.aggregate_search() to find listings, then runs each
through the PolicyEngine to filter and score. Persists qualifying deals to
mandate_deals and updates mandate counters.

Usage:
    agent = DealDiscoveryAgent()
    new_deals = await agent.scan_mandate(mandate_row, conn)
    total = await agent.scan_all_active(conn)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.marketplace_agent import MarketplaceAgent
from app.agents.policy_engine import evaluate as policy_evaluate
from app.lib.affiliate import build_affiliate_url
from app.lib.shipping_service import detect_listing_region, estimate_shipping

logger = logging.getLogger(__name__)


class DealDiscoveryAgent:
    """Scans marketplaces against active purchase mandates."""

    def __init__(self) -> None:
        self._marketplace = MarketplaceAgent()

    async def close(self) -> None:
        await self._marketplace.close()

    # ------------------------------------------------------------------
    # Scan a single mandate
    # ------------------------------------------------------------------

    async def scan_mandate(self, mandate: Dict[str, Any], conn) -> List[Dict[str, Any]]:
        """Scan marketplaces for a single mandate and persist qualifying deals.

        Args:
            mandate: Row from purchase_mandates as a dict.
            conn: asyncpg connection.

        Returns:
            List of new deal dicts (ready for push notification).
        """
        mandate_id = str(mandate["id"])
        user_id = str(mandate["user_id"])
        query = mandate["search_query"]
        category = mandate.get("category")
        region = mandate.get("region")

        logger.info(
            "[DealDiscovery] Scanning mandate %s: query=%r category=%s",
            mandate_id, query, category,
        )

        # 1. Search marketplace
        try:
            result = await self._marketplace.aggregate_search(
                query=query,
                category=category,
                region=region,
                limit=20,
                include_sold=False,  # only active listings for deals
            )
        except Exception as exc:
            logger.error("[DealDiscovery] MarketplaceAgent failed for mandate %s: %s", mandate_id, exc)
            return []

        if not result.hits:
            logger.info("[DealDiscovery] No hits for mandate %s", mandate_id)
            await self._update_last_scan(conn, mandate_id)
            return []

        # 1b. Filter price outliers (> 3 std from median)
        filtered_hits = self._filter_outliers(result.hits)
        if len(filtered_hits) < len(result.hits):
            logger.info(
                "[DealDiscovery] Filtered %d outlier(s) from %d hits",
                len(result.hits) - len(filtered_hits), len(result.hits),
            )
            result = type(result)(
                hits=filtered_hits,
                total_sources_queried=result.total_sources_queried,
                successful_sources=result.successful_sources,
                aggregate_confidence=result.aggregate_confidence,
                dedup_count=result.dedup_count,
                query_metadata=result.query_metadata,
            )

        # 1c. Enrich hits with shipping estimates
        for scored_hit in result.hits:
            hit = scored_hit.hit
            listing_region = detect_listing_region(
                source=hit.get("source"),
                ships_from=hit.get("ships_from"),
                url=hit.get("url"),
            )
            hit["listing_region"] = listing_region

            # Use adapter shipping if available, otherwise estimate midpoint
            if hit.get("shipping_cost") is None and listing_region:
                est = estimate_shipping(listing_region, region)
                midpoint = (est.min_cost_eur + est.max_cost_eur) / 2.0
                hit["shipping_cost"] = round(midpoint, 2)
                hit["shipping_estimated"] = True

        # 2. Fetch price prediction (if available)
        prediction = await self._get_prediction(conn, query, category)

        # 3. Get existing deal URLs for dedup (mandate-level + user-level cooldown)
        existing_urls = await self._get_existing_urls(conn, mandate_id)

        # 3b. Item-level cooldown: skip URLs notified to this user across ANY mandate
        #     within the cooldown window (prevents same listing triggering multiple mandates)
        user_cooldown_urls = await self._get_user_recent_deal_urls(
            conn, user_id, cooldown_hours=int(mandate.get("cooldown_hours", 24) or 24)
        )
        existing_urls = existing_urls | user_cooldown_urls

        new_deals: List[Dict[str, Any]] = []
        batch_rows: List[tuple] = []

        for scored_hit in result.hits:
            hit = scored_hit.hit
            hit_url = hit.get("url", "")

            # Dedup: skip if we already have a deal for this URL
            if hit_url and hit_url in existing_urls:
                continue

            # Inject provenance score from ScoredMarketHit into the hit dict
            hit_with_provenance = {
                **hit,
                "provenance_score": scored_hit.provenance_score,
            }

            # 4. Run policy engine
            verdict = policy_evaluate(mandate, hit_with_provenance, prediction)

            # 5. Build affiliate URL
            source = hit.get("source", "")
            affiliate_url, affiliate_source = build_affiliate_url(hit_url, source)

            # 6. Prepare deal row for batch insert
            deal_id = str(uuid.uuid4())
            batch_rows.append(self._build_deal_row(
                deal_id=deal_id,
                mandate_id=mandate_id,
                user_id=user_id,
                hit=hit,
                scored_hit=scored_hit,
                verdict=verdict,
                prediction=prediction,
                affiliate_url=affiliate_url,
                affiliate_source=affiliate_source,
            ))

            if verdict.passed:
                new_deals.append({
                    "id": deal_id,
                    "mandate_id": mandate_id,
                    "user_id": user_id,
                    "listing_title": hit.get("title", ""),
                    "listing_price": float(hit.get("price", 0) or 0),
                    "listing_url": hit_url,
                    "affiliate_url": affiliate_url,
                    "deal_score": verdict.deal_score,
                    "price_vs_q50_pct": verdict.price_vs_q50_pct,
                })

        # 6b. Batch persist all deals at once
        if batch_rows:
            await self._persist_deals_batch(conn, batch_rows)

        # 6c. Cache listing images to S3 (non-blocking, best-effort)
        if batch_rows:
            await self._cache_deal_images(conn, batch_rows, category)

        # 6d. Feed discovered listings into market_hits for future price predictions
        if result.hits:
            await self._feed_market_hits(conn, result.hits, query, category)

        # 6e. Record supply snapshot (data moat: listing count per query)
        if result.hits:
            try:
                from app.features.data_moat import record_supply_snapshot
                prices = [
                    float(h.hit.get("price", 0) or 0)
                    for h in result.hits
                    if float(h.hit.get("price", 0) or 0) > 0
                ]
                avg_p = sum(prices) / len(prices) if prices else None
                min_p = min(prices) if prices else None
                max_p = max(prices) if prices else None
                await record_supply_snapshot(
                    category=category or "unknown",
                    item_key=query,
                    listing_count=len(result.hits),
                    avg_price_eur=avg_p,
                    min_price_eur=min_p,
                    max_price_eur=max_p,
                    source=result.hits[0].hit.get("source", "firecrawl"),
                )
            except Exception as exc:
                logger.debug("[DealDiscovery] Supply snapshot failed: %s", exc)

        # 7. Update mandate counters
        await self._update_mandate_counters(conn, mandate_id, len(new_deals))

        logger.info(
            "[DealDiscovery] Mandate %s: %d hits, %d new deals",
            mandate_id, len(result.hits), len(new_deals),
        )

        return new_deals

    # ------------------------------------------------------------------
    # Scan all active mandates
    # ------------------------------------------------------------------

    # Maximum mandates processed per scan cycle to prevent OOM / runaway queries
    MAX_MANDATES_PER_CYCLE = 50

    async def scan_all_active(self, conn) -> List[Dict[str, Any]]:
        """Fetch active mandates due for scan (bounded) and process each.

        Only scans mandates belonging to users on pro or premium plans
        (deal_discovery is a paid feature).

        Returns a flat list of all new deals across all mandates.
        """
        rows = await conn.fetch(
            """
            SELECT pm.*
            FROM public.purchase_mandates pm
            -- Both subscriptions.user_id and purchase_mandates.user_id are uuid;
            -- the previous ::text cast caused "operator does not exist: uuid = text" (R46.11)
            JOIN public.subscriptions s ON s.user_id = pm.user_id
            WHERE pm.status = 'active'
              AND (pm.expires_at IS NULL OR pm.expires_at > now())
              AND s.plan IN ('pro', 'premium')
              AND s.status IN ('active', 'trialing')
            ORDER BY pm.last_scan_at ASC NULLS FIRST
            LIMIT $1
            """,
            self.MAX_MANDATES_PER_CYCLE,
        )

        if not rows:
            logger.info("[DealDiscovery] No active mandates to scan")
            return []

        logger.info("[DealDiscovery] Scanning %d active mandates", len(rows))

        all_new_deals: List[Dict[str, Any]] = []

        for row in rows:
            mandate = dict(row)
            try:
                new_deals = await self.scan_mandate(mandate, conn)
                all_new_deals.extend(new_deals)
            except Exception as exc:
                logger.error(
                    "[DealDiscovery] Failed to scan mandate %s: %s",
                    mandate["id"], exc, exc_info=True,
                )

        return all_new_deals

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_outliers(hits, mad_threshold: float = 3.0):
        """Remove price outliers using Median Absolute Deviation (MAD).

        MAD is more robust than standard deviation because outliers don't
        inflate the spread metric itself.
        """
        if len(hits) < 3:
            return hits

        prices = [float(h.hit.get("price", 0) or 0) for h in hits]
        prices_valid = [p for p in prices if p > 0]

        if len(prices_valid) < 3:
            return hits

        sorted_p = sorted(prices_valid)
        mid = len(sorted_p) // 2
        median = (sorted_p[mid] + sorted_p[~mid]) / 2.0

        # MAD = median of absolute deviations from median
        abs_devs = sorted(abs(p - median) for p in prices_valid)
        mad_mid = len(abs_devs) // 2
        mad = (abs_devs[mad_mid] + abs_devs[~mad_mid]) / 2.0

        if mad == 0:
            return hits

        low = median - mad_threshold * mad
        high = median + mad_threshold * mad

        filtered = []
        dropped = 0
        for h in hits:
            price = float(h.hit.get("price", 0) or 0)
            if price <= 0:
                dropped += 1
                continue
            if low <= price <= high:
                filtered.append(h)
            else:
                dropped += 1
        if dropped:
            logger.debug(
                "[outlier_filter] Dropped %d/%d hits (range %.2f–%.2f, median %.2f)",
                dropped, len(hits), low, high, median,
            )
        return filtered

    async def _get_prediction(
        self, conn, query: str, category: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Try to fetch a price prediction for the mandate's search query.

        Falls back to category median if no direct match is found.
        """
        try:
            # Escape ILIKE special chars to prevent wildcard injection
            escaped_q = query[:50].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            row = await conn.fetchrow(
                """
                SELECT q10, q50, q90
                FROM public.price_predictions
                WHERE normalized_key ILIKE $1
                ORDER BY asof DESC
                LIMIT 1
                """,
                f"%{escaped_q}%",
            )
            if row and row["q50"] is not None:
                return {
                    "q10": float(row["q10"]) if row["q10"] else None,
                    "q50": float(row["q50"]),
                    "q90": float(row["q90"]) if row["q90"] else None,
                }
        except Exception as exc:
            logger.debug("[DealDiscovery] Prediction lookup failed: %s", exc)

        # Fallback: category median from price_predictions
        if category:
            try:
                row = await conn.fetchrow(
                    """
                    SELECT
                        percentile_cont(0.10) WITHIN GROUP (ORDER BY q50) AS cat_q10,
                        percentile_cont(0.50) WITHIN GROUP (ORDER BY q50) AS cat_q50,
                        percentile_cont(0.90) WITHIN GROUP (ORDER BY q50) AS cat_q90
                    FROM public.price_predictions
                    WHERE normalized_key ILIKE $1
                      AND q50 IS NOT NULL
                    """,
                    f"%{category}%",
                )
                if row and row["cat_q50"] is not None:
                    logger.debug(
                        "[DealDiscovery] Using category median fallback for %s: q50=%.2f",
                        category, float(row["cat_q50"]),
                    )
                    return {
                        "q10": float(row["cat_q10"]) if row["cat_q10"] else None,
                        "q50": float(row["cat_q50"]),
                        "q90": float(row["cat_q90"]) if row["cat_q90"] else None,
                    }
            except Exception as exc:
                logger.debug("[DealDiscovery] Category median fallback failed: %s", exc)

        return None

    async def _get_existing_urls(self, conn, mandate_id: str) -> set[str]:
        """Return set of listing URLs already tracked for this mandate."""
        rows = await conn.fetch(
            """
            SELECT listing_url
            FROM public.mandate_deals
            WHERE mandate_id = $1
              AND status NOT IN ('expired', 'declined')
            """,
            uuid.UUID(mandate_id),
        )
        return {r["listing_url"] for r in rows}

    async def _get_user_recent_deal_urls(
        self, conn, user_id: str, cooldown_hours: int = 24
    ) -> set[str]:
        """Return listing URLs notified to this user across all mandates within cooldown window.

        This implements item-level cooldown: the same listing URL won't trigger
        notifications from multiple mandates within the cooldown period.
        """
        try:
            uid = uuid.UUID(user_id) if _is_uuid(user_id) else user_id
            rows = await conn.fetch(
                """
                SELECT listing_url
                FROM public.mandate_deals
                WHERE user_id = $1
                  AND status NOT IN ('expired', 'declined')
                  AND discovered_at >= now() - ($2 || ' hours')::interval
                """,
                uid,
                str(cooldown_hours),
            )
            return {r["listing_url"] for r in rows}
        except Exception as exc:
            logger.debug("[DealDiscovery] User URL cooldown lookup failed: %s", exc)
            return set()

    def _build_deal_row(
        self,
        deal_id: str,
        mandate_id: str,
        user_id: str,
        hit: Dict[str, Any],
        scored_hit,
        verdict,
        prediction: Optional[Dict[str, Any]],
        affiliate_url: str,
        affiliate_source: str,
    ) -> tuple:
        """Build a tuple of values for batch insert."""
        return (
            uuid.UUID(deal_id),
            uuid.UUID(mandate_id),
            uuid.UUID(user_id) if _is_uuid(user_id) else user_id,
            hit.get("source", ""),
            hit.get("url", ""),
            affiliate_url,
            hit.get("title", "")[:500],
            float(hit.get("price", 0) or 0),
            hit.get("currency", "EUR"),
            hit.get("condition"),
            hit.get("image_url") or hit.get("imageUrl"),
            hit.get("seller"),
            scored_hit.provenance_score,
            verdict.deal_score,
            verdict.price_vs_q50_pct,
            prediction.get("q50") if prediction else None,
            prediction.get("q10") if prediction else None,
            prediction.get("q90") if prediction else None,
            verdict.passed,
            json.dumps(verdict.reasons),
            affiliate_source or None,
        )

    async def _persist_deals_batch(self, conn, rows: List[tuple]) -> None:
        """Batch INSERT all deal rows in a single executemany call."""
        try:
            await conn.executemany(
                """
                INSERT INTO public.mandate_deals (
                    id, mandate_id, user_id,
                    listing_source, listing_url, affiliate_url,
                    listing_title, listing_price, listing_currency,
                    listing_condition, listing_image_url, listing_seller,
                    provenance_score, deal_score, price_vs_q50_pct,
                    predicted_q50, predicted_q10, predicted_q90,
                    policy_passed, policy_reasons,
                    affiliate_source
                ) VALUES (
                    $1, $2, $3,
                    $4, $5, $6,
                    $7, $8, $9,
                    $10, $11, $12,
                    $13, $14, $15,
                    $16, $17, $18,
                    $19, $20::jsonb,
                    $21
                )
                """,
                rows,
            )
        except Exception as exc:
            logger.warning("[DealDiscovery] Batch persist failed: %s", exc)

    async def _feed_market_hits(self, conn, hits, query: str, category: Optional[str]) -> None:
        """Persist deal discoveries into market_hits for future price predictions.

        Uses ON CONFLICT to skip duplicates (same provider + listing_id).
        """
        rows = []
        for scored_hit in hits:
            hit = scored_hit.hit
            url = hit.get("url", "")
            source = hit.get("source", "unknown")
            price = float(hit.get("price", 0) or 0)
            if not url or price <= 0:
                continue

            # Use URL as listing_id since marketplace listing IDs may not be available
            listing_id = url[:500]
            normalized_key = f"{category or ''}/{query[:100]}" if query else None

            rows.append((
                source,
                listing_id,
                hit.get("title", "")[:500],
                price,
                hit.get("currency", "EUR"),
                hit.get("condition"),
                url,
                normalized_key,
                hit.get("shipping_cost"),
                hit.get("ships_from"),
                hit.get("domestic_only", False),
            ))

        if not rows:
            return

        try:
            await conn.executemany(
                """
                INSERT INTO public.market_hits
                    (provider, listing_id, title, price, currency, condition, url, normalized_key,
                     shipping, ships_from, domestic_only)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (provider, listing_id) DO NOTHING
                """,
                rows,
            )
            logger.info("[DealDiscovery] Fed %d listings into market_hits", len(rows))
        except Exception as exc:
            logger.debug("[DealDiscovery] market_hits feed failed (non-critical): %s", exc)

    async def _cache_deal_images(
        self, conn, batch_rows: List[tuple], category: Optional[str]
    ) -> None:
        """Cache deal listing images to S3 for reliable serving.

        Runs the synchronous S3ImageCache in a thread pool to avoid blocking
        the event loop. Updates listing_image_url with cached CDN/S3 URLs.
        Best-effort: failures are logged but don't break the deal flow.
        """
        try:
            from pipelines.s3_image_cache import S3ImageCache
        except ImportError:
            return

        cache = S3ImageCache()
        if not cache.enabled:
            cache.close()
            return

        # Build (image_url, category, item_key) tuples from batch_rows
        # batch_rows layout: (deal_id, mandate_id, user_id, source, url, affiliate_url,
        #                     title, price, currency, condition, image_url, ...)
        items_to_cache: list[tuple[str, str, str]] = []
        deal_image_map: dict[str, str] = {}  # deal_id -> original_image_url

        for row in batch_rows:
            deal_id = str(row[0])
            image_url = row[10]  # listing_image_url position
            if not image_url:
                continue
            # Use deal_id as item_key for deterministic S3 path
            cat = category or "uncategorized"
            items_to_cache.append((image_url, cat, deal_id))
            deal_image_map[deal_id] = image_url

        if not items_to_cache:
            cache.close()
            return

        try:
            # Run synchronous cache_batch in thread pool
            url_map = await asyncio.to_thread(cache.cache_batch, items_to_cache, 0.05)

            # Update DB rows where image was successfully cached
            updates = []
            for deal_id, orig_url in deal_image_map.items():
                cached_url = url_map.get(orig_url)
                if cached_url and cached_url != orig_url:
                    updates.append((uuid.UUID(deal_id), cached_url))

            if updates:
                await conn.executemany(
                    """
                    UPDATE public.mandate_deals
                    SET listing_image_url = $2
                    WHERE id = $1
                    """,
                    updates,
                )
                logger.info("[DealDiscovery] Cached %d deal images to S3", len(updates))

        except Exception as exc:
            logger.debug("[DealDiscovery] Image caching failed (non-critical): %s", exc)
        finally:
            cache.close()

    async def _update_mandate_counters(self, conn, mandate_id: str, new_deal_count: int) -> None:
        """Update last_scan_at and increment deals_found."""
        try:
            now = datetime.now(timezone.utc)
            await conn.execute(
                """
                UPDATE public.purchase_mandates
                SET last_scan_at = $1,
                    deals_found = deals_found + $2,
                    updated_at = $1
                WHERE id = $3
                """,
                now,
                new_deal_count,
                uuid.UUID(mandate_id),
            )
            if new_deal_count > 0:
                await conn.execute(
                    """
                    UPDATE public.purchase_mandates
                    SET last_deal_at = $1
                    WHERE id = $2
                    """,
                    now,
                    uuid.UUID(mandate_id),
                )
        except Exception as exc:
            logger.warning("[DealDiscovery] Failed to update mandate counters: %s", exc)

    async def _update_last_scan(self, conn, mandate_id: str) -> None:
        """Update last_scan_at even when no deals are found."""
        try:
            await conn.execute(
                """
                UPDATE public.purchase_mandates
                SET last_scan_at = now(), updated_at = now()
                WHERE id = $1
                """,
                uuid.UUID(mandate_id),
            )
        except Exception as exc:
            logger.warning("[DealDiscovery] Failed to update last_scan: %s", exc)


def _is_uuid(s: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False
