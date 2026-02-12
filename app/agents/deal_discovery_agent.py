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

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.marketplace_agent import MarketplaceAgent
from app.agents.policy_engine import evaluate as policy_evaluate
from app.lib.affiliate import build_affiliate_url

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

        # 2. Fetch price prediction (if available)
        prediction = await self._get_prediction(conn, query, category)

        # 3. Get existing deal URLs for dedup
        existing_urls = await self._get_existing_urls(conn, mandate_id)

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

        Returns a flat list of all new deals across all mandates.
        """
        rows = await conn.fetch(
            """
            SELECT *
            FROM public.purchase_mandates
            WHERE status = 'active'
              AND (expires_at IS NULL OR expires_at > now())
            ORDER BY last_scan_at ASC NULLS FIRST
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

    async def _get_prediction(
        self, conn, query: str, category: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Try to fetch a price prediction for the mandate's search query."""
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
