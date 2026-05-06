"""
Main intake orchestrator — the process_intake entry point.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.lib.db_helpers import get_db_pool

from .helpers import (
    IntakeResult,
    _fire_catalog_miss,
    _lookup_taxonomy_corrections,
)
from .field_extraction import (
    _barcode_lookup_internal,
    _vision_classify_internal,
)
from .catalog_matching import (
    _match_catalog_items,
    _validate_with_reprompt,
)
from .enrichment import _estimate_price
from .condition_grading import apply_condition_grading

logger = logging.getLogger(__name__)


async def _user_has_paid_plan(user_id: Optional[str]) -> bool:
    """True if user is on pro/premium. Free users skip paid intake steps.

    Inline import keeps this resilient if subscription module fails to load
    in degraded mode — we just default to free (skip paid steps).
    """
    if not user_id:
        return False
    try:
        from app.subscription import get_user_plan
        plan = await get_user_plan(user_id)
        return plan in ("pro", "premium")
    except Exception:
        return False


async def process_intake(
    image_bytes: Optional[bytes] = None,
    barcode: Optional[str] = None,
    barcode_type: Optional[str] = None,
    user_hints: Optional[dict[str, Any]] = None,
    user_id: Optional[str] = None,
    conn=None,
) -> IntakeResult:
    """
    Unified intake orchestrator.

    Flow:
      1. If barcode provided, try barcode lookup cascade
      2. If no barcode or barcode failed, try vision classification
      3. Resolve taxonomy with correction pattern awareness
      4. Estimate price from available sources
      5. Apply user hints (override if provided)

    Args:
        image_bytes: Raw image bytes for vision classification
        barcode: Scanned barcode string
        barcode_type: Barcode format (ean13, upc_a, isbn, etc.)
        user_hints: User-provided overrides (category, name, condition, etc.)
        conn: Database connection (unused, pool is fetched internally)

    Returns:
        IntakeResult with full provenance
    """
    result = IntakeResult()
    result.scan_session_id = str(uuid4())
    result.barcode = barcode
    result.barcode_type = barcode_type
    hints = user_hints or {}

    pool = get_db_pool()
    barcode_found = False
    barcode_partial = False

    try:
        # -----------------------------------------------------------------
        # Step 1: Barcode lookup
        # -----------------------------------------------------------------
        if barcode:
            result.rationale.append(f"Barcode provided: {barcode} (type: {barcode_type or 'auto'})")

            barcode_result = await _barcode_lookup_internal(barcode, barcode_type, pool)
            if barcode_result:
                result.name = barcode_result.get("title")
                result.category_id = barcode_result.get("category_id")
                result.subtype_id = barcode_result.get("subtype_id")
                result.attributes = barcode_result.get("attributes", {})
                result.image_url = barcode_result.get("image_url")
                result.identification_method = barcode_result.get(
                    "identification_method", "barcode_catalog"
                )
                result.rationale.extend(barcode_result.get("rationale", []))

                if barcode_result.get("price_band"):
                    result.price_band = barcode_result["price_band"]
                    result.estimated_price = barcode_result["price_band"].get("q50")
                    result.price_source = "market_hits"

                barcode_found = True

                # Check if it's a partial match (name but no category)
                if result.name and not result.category_id:
                    barcode_partial = True
                    result.rationale.append(
                        "Barcode found name but no category - supplementing with vision"
                    )

                # High confidence if both name and category found
                if result.name and result.category_id:
                    result.category_confidence = 0.9
                    result.taxonomy_confidence = 0.9
            else:
                result.rationale.append("Barcode not found in any source")

        # -----------------------------------------------------------------
        # Step 2: Vision classification (if no barcode or partial match)
        # -----------------------------------------------------------------
        if (not barcode_found or barcode_partial) and image_bytes:
            result.rationale.append("Attempting vision classification")

            vision_result = await _vision_classify_internal(image_bytes)

            if vision_result:
                vision_cat = vision_result.get("category_id")
                vision_conf = vision_result.get("category_confidence", 0.0)
                vision_method = vision_result.get("identification_method", "vision_heuristic")

                if barcode_partial:
                    # Supplement: use vision for category only
                    if vision_cat and vision_conf > 0.3:
                        result.category_id = vision_cat
                        result.category_confidence = vision_conf
                        result.identification_method = f"{result.identification_method}+{vision_method}"
                        result.rationale.append(
                            f"Vision supplemented category: {vision_cat} "
                            f"(confidence: {vision_conf:.2f})"
                        )
                else:
                    # Full vision result
                    result.category_id = vision_cat
                    result.category_confidence = vision_conf
                    result.identification_method = vision_method
                    result.name = vision_result.get("suggested_name") or result.name

                    # Merge vision attributes
                    vision_attrs = vision_result.get("attributes", {})
                    result.attributes.update(vision_attrs)

                    condition = vision_result.get("condition")
                    if condition:
                        result.attributes["condition"] = condition
                        result.attributes["condition_confidence"] = vision_result.get(
                            "condition_confidence", 0.0
                        )

                    # Extract defect annotations and suggested grade (F6)
                    result.defect_annotations = vision_result.get("defect_annotations", [])
                    result.suggested_grade = vision_result.get("suggested_grade")

                    # Enrich with condition_grader if defects present but no grade
                    # Paid feature (Pro+) — skip for free users so the FE
                    # paywall lines up with server-side gating.
                    if await _user_has_paid_plan(user_id):
                        apply_condition_grading(result, vision_cat)

                    result.rationale.append(
                        f"Vision classified as {vision_cat} via {vision_method} "
                        f"(confidence: {vision_conf:.2f})"
                    )
            else:
                result.rationale.append("Vision classification returned no result")

        elif not barcode_found and not image_bytes:
            result.rationale.append("No barcode or image provided - manual entry required")
            result.identification_method = "manual"

        # -----------------------------------------------------------------
        # Step 2.5: Catalog matching (RAG) — ground vision results against catalog
        # -----------------------------------------------------------------
        if result.category_id and result.name and not barcode_found:
            # Extract search keywords and brand/set from vision attributes
            search_kws: list[str] = result.attributes.get("search_keywords", [])
            vis_brand = result.attributes.get("brand") or result.attributes.get("manufacturer")
            vis_set = result.attributes.get("set_code") or result.attributes.get("set_name")

            catalog_matches = await _match_catalog_items(
                category_id=result.category_id,
                suggested_name=result.name,
                search_keywords=search_kws if isinstance(search_kws, list) else [],
                brand=str(vis_brand) if vis_brand else None,
                set_code=str(vis_set) if vis_set else None,
                pool=pool,
                extracted_attributes=result.attributes if isinstance(result.attributes, dict) else None,
            )

            if catalog_matches:
                best = catalog_matches[0]
                best_score = best["match_score"]

                if best_score >= 0.75:
                    # Strong match — adopt catalog title
                    result.catalog_match_id = best["catalog_item_id"]
                    result.catalog_match_key = best["item_key"]
                    result.name = best["title"] or result.name
                    # Merge catalog attributes into result
                    if best.get("brand"):
                        result.attributes["brand"] = best["brand"]
                    if best.get("rarity"):
                        result.attributes["rarity"] = best["rarity"]
                        result.subtype_id = best["rarity"]
                    if best.get("set_code"):
                        result.attributes["set_code"] = best["set_code"]
                    if best.get("image_url"):
                        result.image_url = result.image_url or best["image_url"]
                    result.rationale.append(
                        f"Catalog match (score={best_score:.2f}): adopted '{best['title']}'"
                    )
                elif best_score >= 0.6:
                    # Probable match — keep vision name but note the match
                    result.catalog_match_id = best["catalog_item_id"]
                    result.catalog_match_key = best["item_key"]
                    result.rationale.append(
                        f"Probable catalog match (score={best_score:.2f}): '{best['title']}'"
                    )

                # Build alternatives list (top 3)
                result.alternatives = catalog_matches[:3]

            else:
                result.catalog_miss = True
                result.rationale.append("No catalog matches found for vision result")

            # Build field_confidence from vision per-field scores
            name_conf = result.attributes.get("name_confidence")
            if name_conf is not None:
                result.field_confidence = {
                    "category": result.category_confidence,
                    "name": float(name_conf),
                    "condition": result.attributes.get("condition_confidence", 0.0),
                }

            # Extract chain_of_thought
            cot = result.attributes.get("chain_of_thought")
            if cot:
                result.chain_of_thought = str(cot)

        # -----------------------------------------------------------------
        # Step 2.6: Re-prompt validation — send image + candidates back to
        # the model for a focused visual comparison.
        # -----------------------------------------------------------------
        _fast_path_applied = False
        if (
            image_bytes
            and result.alternatives
            and len(result.alternatives) >= 1
        ):
            best_alt_score = max(
                a.get("match_score", 0) for a in result.alternatives
            )
            clip_conf = result.attributes.get("clip_confidence", 0.0)

            # Fast-path (F2): if CLIP confidence >= 0.90 AND best catalog
            # match >= 0.90, auto-select the best match and skip re-prompt.
            if clip_conf >= 0.90 and best_alt_score >= 0.90:
                _fast_path_applied = True
                best_alt = max(result.alternatives, key=lambda a: a.get("match_score", 0))
                result.catalog_match_id = best_alt.get("catalog_item_id")
                result.catalog_match_key = best_alt.get("item_key")
                result.name = best_alt.get("title") or result.name
                if best_alt.get("brand"):
                    result.attributes["brand"] = best_alt["brand"]
                if best_alt.get("rarity"):
                    result.attributes["rarity"] = best_alt["rarity"]
                    result.subtype_id = best_alt["rarity"]
                if best_alt.get("set_code"):
                    result.attributes["set_code"] = best_alt["set_code"]
                if result.field_confidence and result.field_confidence.get("name") is not None:
                    result.field_confidence["name"] = max(
                        result.field_confidence["name"], best_alt_score,
                    )
                result.rationale.append(
                    f"Fast-path: auto-selected '{best_alt.get('title')}' "
                    f"(clip_conf={clip_conf:.2f}, catalog_score={best_alt_score:.2f}) — "
                    f"skipped re-prompt"
                )
                logger.info(
                    "Fast-path activated: clip_conf=%.2f, catalog_score=%.2f — skipping reprompt",
                    clip_conf, best_alt_score,
                )

        if (
            not _fast_path_applied
            and image_bytes
            and result.alternatives
            and len(result.alternatives) >= 2
        ):
            best_alt_score = max(
                a.get("match_score", 0) for a in result.alternatives
            )
            # Only re-prompt when identification is uncertain — skip for
            # high-confidence matches to save an OpenAI Vision call (~40-60%
            # of scans).  The 0.60 threshold balances quality vs cost.
            name_conf = (result.field_confidence or {}).get("name", 0.5)
            if best_alt_score < 0.90 and name_conf < 0.60:
                reprompt = await _validate_with_reprompt(
                    image_bytes=image_bytes,
                    initial_name=result.name or "",
                    initial_category=result.category_id or "",
                    catalog_candidates=result.alternatives,
                )
                if reprompt is not None:
                    sel_idx = reprompt["selected_index"]
                    sel_conf = reprompt["confidence"]
                    sel_reason = reprompt["reasoning"]

                    if sel_idx == 0:
                        # Model re-confirmed original identification
                        if result.field_confidence and result.field_confidence.get("name") is not None:
                            result.field_confidence["name"] = max(
                                result.field_confidence["name"], sel_conf,
                            )
                        result.rationale.append(
                            f"Reprompt confirmed original '{result.name}' "
                            f"(conf={sel_conf:.2f}): {sel_reason}"
                        )
                    elif 1 <= sel_idx <= len(result.alternatives):
                        selected = result.alternatives[sel_idx - 1]
                        result.catalog_match_id = selected.get("catalog_item_id")
                        result.catalog_match_key = selected.get("item_key")
                        result.name = selected.get("title") or result.name
                        if selected.get("brand"):
                            result.attributes["brand"] = selected["brand"]
                        if selected.get("rarity"):
                            result.attributes["rarity"] = selected["rarity"]
                            result.subtype_id = selected["rarity"]
                        if selected.get("set_code"):
                            result.attributes["set_code"] = selected["set_code"]
                        if result.field_confidence and result.field_confidence.get("name") is not None:
                            result.field_confidence["name"] = max(
                                result.field_confidence["name"], sel_conf,
                            )
                        result.rationale.append(
                            f"Reprompt selected candidate #{sel_idx} "
                            f"'{selected.get('title')}' over original "
                            f"(conf={sel_conf:.2f}): {sel_reason}"
                        )

        # -----------------------------------------------------------------
        # Step 2.7: Duplicate/variant detection (needs user_id)
        # -----------------------------------------------------------------
        if user_id and result.category_id:
            try:
                from app.agents.intake_duplicate_check import check_user_duplicates
                import re as _re
                _norm_key = _re.sub(r"[^a-z0-9\s]", "", (result.name or "").lower().strip())[:100]
                result.duplicate_info = await check_user_duplicates(
                    user_id=user_id,
                    category_id=result.category_id,
                    normalized_key=_norm_key,
                    catalog_match_key=result.catalog_match_key,
                    pool=pool,
                )
                if result.duplicate_info.get("owned_count", 0) > 0:
                    result.rationale.append(
                        f"Duplicate detected: user already owns {result.duplicate_info['owned_count']} matching item(s)"
                    )
                elif result.duplicate_info.get("is_variant"):
                    result.rationale.append(
                        f"Variant detected: similar to owned '{result.duplicate_info['variant_of']}'"
                    )
            except Exception:
                pass

        # -----------------------------------------------------------------
        # Step 3: Taxonomy resolution
        # -----------------------------------------------------------------
        if result.category_id:
            result.taxonomy_confidence = result.category_confidence

            # Check for correction patterns
            corrections = await _lookup_taxonomy_corrections(result.category_id, pool)
            if corrections:
                result.suggested_corrections = corrections
                result.rationale.append(
                    f"Found {len(corrections)} taxonomy correction pattern(s) "
                    f"for category '{result.category_id}'"
                )

        # -----------------------------------------------------------------
        # Step 4: Price estimation (if not already set from barcode)
        # -----------------------------------------------------------------
        if result.estimated_price is None and result.category_id and result.name:
            price, source, band = await _estimate_price(
                result.category_id, result.name, pool,
                catalog_match_key=result.catalog_match_key,
            )
            if price is not None:
                result.estimated_price = price
                result.price_source = source
                if band:
                    result.price_band = band
                result.rationale.append(f"Price estimated from {source}: EUR {price:.2f}")

        # -----------------------------------------------------------------
        # Step 4.5: Social proof (best-effort)
        # -----------------------------------------------------------------
        try:
            from app.agents.intake_social_proof import get_social_proof
            result.social_proof = await get_social_proof(
                category=result.category_id,
                item_key=result.catalog_match_key or result.name,
                pool=pool,
            )
            if result.social_proof.get("collector_count", 0) > 0:
                result.rationale.append(
                    f"Social proof: {result.social_proof['collector_count']} collectors interested"
                )
        except Exception:
            pass

        # -----------------------------------------------------------------
        # Step 5: Apply user hints (trust user over automation)
        # -----------------------------------------------------------------
        if hints.get("category"):
            prev_cat = result.category_id
            result.category_id = hints["category"]
            result.category_confidence = 1.0
            result.taxonomy_confidence = 1.0
            if prev_cat and prev_cat != hints["category"]:
                result.rationale.append(
                    f"User overrode category from '{prev_cat}' to '{hints['category']}'"
                )
            else:
                result.rationale.append(f"User specified category: {hints['category']}")

        if hints.get("name"):
            result.name = hints["name"]
            result.rationale.append(f"User specified name: {hints['name']}")

        if hints.get("condition"):
            result.attributes["condition"] = hints["condition"]
            result.rationale.append(f"User specified condition: {hints['condition']}")

        # Timestamp the intake
        result.attributes["intake_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Mark as catalog miss if no category or low confidence
        # (check BEFORE user hints override, but after all automated steps)
        if not result.category_id or result.category_confidence < 0.3:
            result.catalog_miss = True
            miss_source = "barcode" if barcode else ("photo" if image_bytes else "manual")
            _fire_catalog_miss(
                user_id=user_id,
                source=miss_source,
                input_data={"barcode": barcode, "barcode_type": barcode_type, "name": result.name},
                suggested_name=result.name,
            )

    except Exception as e:
        logger.error("Intake agent error: %s", e, exc_info=True)
        result.rationale.append(f"Intake processing error - partial result returned")

    return result
