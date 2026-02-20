"""
Catalog Learning Router.

User-facing endpoint:
  POST /catalog/suggest  — submit a catalog suggestion (authenticated, rate-limited)

Admin/ops endpoints:
  GET  /ops/catalog-suggestions            — paginated, filterable list
  POST /ops/catalog-suggestions/{id}/action — approve/reject/map
  GET  /ops/category-candidates            — list category candidates
  POST /ops/category-candidates/{id}/action — approve/reject/merge
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user_id, require_ops_key
from app.config import CATALOG_LEARNING_ENABLED
from app.db import get_pool
from app.errors import error_response
from app.rate_limit import per_user_rate_limit

logger = logging.getLogger(__name__)

# Per-user: 10 suggestions per hour
_suggest_user_limit = per_user_rate_limit(10, window_seconds=3600, scope="catalog_suggest")

router = APIRouter(tags=["catalog-learning"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CatalogSuggestionRequest(BaseModel):
    source: str = Field(..., pattern=r"^(barcode|photo|manual|url)$")
    input_data: dict[str, Any] = Field(default_factory=dict)
    suggested_name: str = Field(..., min_length=1, max_length=500)
    suggested_category: Optional[str] = Field(None, max_length=100)


class CatalogSuggestionResponse(BaseModel):
    id: str
    status: str
    matched_existing: bool = False


class SuggestionListItem(BaseModel):
    id: str
    user_id: str
    source: str
    suggested_name: str
    suggested_category: Optional[str] = None
    matched_category: Optional[str] = None
    confidence: float = 0.0
    status: str
    created_at: str


class SuggestionActionRequest(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject|map)$")
    mapped_category: Optional[str] = Field(None, max_length=100)
    mapped_item_key: Optional[str] = Field(None, max_length=500)


class CandidateListItem(BaseModel):
    id: str
    proposed_name: str
    proposed_slug: str
    description: Optional[str] = None
    signal_count: int = 0
    unique_users: int = 0
    first_seen: str
    last_seen: str
    status: str
    admin_notes: Optional[str] = None


class CandidateActionRequest(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject|merge)$")
    admin_notes: Optional[str] = Field(None, max_length=1000)
    merge_into_slug: Optional[str] = Field(None, max_length=100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Convert a proposed category name to a slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s_-]", "", slug)
    slug = re.sub(r"[\s-]+", "_", slug).strip("_")
    return slug[:64]


# ---------------------------------------------------------------------------
# User endpoint: POST /catalog/suggest
# ---------------------------------------------------------------------------

@router.post(
    "/catalog/suggest",
    response_model=CatalogSuggestionResponse,
    status_code=201,
    dependencies=[Depends(_suggest_user_limit)],
)
async def submit_catalog_suggestion(
    req: CatalogSuggestionRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Submit a catalog suggestion for an unrecognized item."""
    if not CATALOG_LEARNING_ENABLED:
        raise error_response(503, "Catalog learning is not enabled", code="CATALOG_LEARNING_DISABLED")

    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    suggestion_id = str(uuid4())
    input_json = json.dumps(req.input_data, sort_keys=True)

    try:
        # Check for existing match (dedup by user+source+input_data hash)
        existing = await pool.fetchrow(
            """
            SELECT id, status FROM catalog_suggestions
            WHERE user_id = $1::uuid AND source = $2 AND md5(input_data::text) = md5($3)
            """,
            user_id,
            req.source,
            input_json,
        )

        if existing:
            return CatalogSuggestionResponse(
                id=str(existing["id"]),
                status=existing["status"],
                matched_existing=True,
            )

        await pool.execute(
            """
            INSERT INTO catalog_suggestions (
                id, user_id, source, input_data,
                suggested_name, suggested_category, status
            ) VALUES (
                $1::uuid, $2::uuid, $3, $4::jsonb,
                $5, $6, 'pending'
            )
            """,
            suggestion_id,
            user_id,
            req.source,
            input_json,
            req.suggested_name.strip(),
            req.suggested_category.strip() if req.suggested_category else None,
        )

        logger.info(
            "[catalog-learning] Suggestion %s from user %s (source=%s, name=%s)",
            suggestion_id, user_id, req.source, req.suggested_name[:50],
        )

        return CatalogSuggestionResponse(
            id=suggestion_id,
            status="pending",
            matched_existing=False,
        )

    except Exception as exc:
        if "uq_catalog_suggestions_dedup" in str(exc):
            # Race condition — concurrent insert of same dedup key
            existing = await pool.fetchrow(
                """
                SELECT id, status FROM catalog_suggestions
                WHERE user_id = $1::uuid AND source = $2 AND md5(input_data::text) = md5($3)
                """,
                user_id,
                req.source,
                input_json,
            )
            if existing:
                return CatalogSuggestionResponse(
                    id=str(existing["id"]),
                    status=existing["status"],
                    matched_existing=True,
                )
        logger.error("[catalog-learning] Failed to insert suggestion: %s", exc)
        raise error_response(500, "Failed to save suggestion", code="DB_ERROR")


# ---------------------------------------------------------------------------
# Admin: GET /ops/catalog-suggestions
# ---------------------------------------------------------------------------

@router.get("/ops/catalog-suggestions")
async def list_catalog_suggestions(
    _: bool = Depends(require_ops_key),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List catalog suggestions with optional filters."""
    pool = get_pool()
    if pool is None:
        return {"suggestions": [], "total": 0}

    conditions = []
    params: list[Any] = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if source:
        conditions.append(f"source = ${idx}")
        params.append(source)
        idx += 1
    if category:
        conditions.append(f"suggested_category = ${idx}")
        params.append(category)
        idx += 1

    where = " AND ".join(conditions)
    if where:
        where = "WHERE " + where

    total = await pool.fetchval(
        f"SELECT count(*) FROM catalog_suggestions {where}",
        *params,
    ) or 0

    offset = (page - 1) * per_page
    rows = await pool.fetch(
        f"""
        SELECT id, user_id, source, suggested_name, suggested_category,
               matched_category, confidence, status, created_at
        FROM catalog_suggestions {where}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
        per_page,
        offset,
    )

    suggestions = [
        SuggestionListItem(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            source=r["source"],
            suggested_name=r["suggested_name"],
            suggested_category=r["suggested_category"],
            matched_category=r["matched_category"],
            confidence=r["confidence"] or 0.0,
            status=r["status"],
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
        ).model_dump()
        for r in rows
    ]

    # Aggregation: top suggested names
    agg_rows = await pool.fetch(
        """
        SELECT lower(suggested_name) as name, count(*) as cnt,
               count(DISTINCT user_id) as users
        FROM catalog_suggestions
        WHERE status = 'pending'
        GROUP BY lower(suggested_name)
        ORDER BY users DESC, cnt DESC
        LIMIT 20
        """
    )
    aggregation = [
        {"name": r["name"], "count": r["cnt"], "unique_users": r["users"]}
        for r in agg_rows
    ]

    return {
        "suggestions": suggestions,
        "total": total,
        "page": page,
        "per_page": per_page,
        "aggregation": aggregation,
    }


# ---------------------------------------------------------------------------
# Admin: POST /ops/catalog-suggestions/{id}/action
# ---------------------------------------------------------------------------

@router.post("/ops/catalog-suggestions/{suggestion_id}/action")
async def action_catalog_suggestion(
    suggestion_id: str,
    req: SuggestionActionRequest,
    _: bool = Depends(require_ops_key),
):
    """Approve, reject, or map a catalog suggestion."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    row = await pool.fetchrow(
        "SELECT id, status FROM catalog_suggestions WHERE id = $1::uuid",
        suggestion_id,
    )
    if not row:
        raise error_response(404, "Suggestion not found", code="NOT_FOUND")

    if req.action == "approve":
        await pool.execute(
            "UPDATE catalog_suggestions SET status = 'mapped', matched_category = $2, mapped_item_key = $3 WHERE id = $1::uuid",
            suggestion_id,
            req.mapped_category,
            req.mapped_item_key,
        )
    elif req.action == "reject":
        await pool.execute(
            "UPDATE catalog_suggestions SET status = 'rejected' WHERE id = $1::uuid",
            suggestion_id,
        )
    elif req.action == "map":
        if not req.mapped_category:
            raise error_response(400, "mapped_category required for map action", code="VALIDATION_ERROR")
        await pool.execute(
            "UPDATE catalog_suggestions SET status = 'mapped', matched_category = $2, mapped_item_key = $3 WHERE id = $1::uuid",
            suggestion_id,
            req.mapped_category,
            req.mapped_item_key,
        )

    return {"id": suggestion_id, "action": req.action, "ok": True}


# ---------------------------------------------------------------------------
# Admin: GET /ops/category-candidates
# ---------------------------------------------------------------------------

@router.get("/ops/category-candidates")
async def list_category_candidates(
    _: bool = Depends(require_ops_key),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List category candidates with optional status filter."""
    pool = get_pool()
    if pool is None:
        return {"candidates": [], "total": 0}

    where = ""
    params: list[Any] = []
    idx = 1

    if status:
        where = f"WHERE status = ${idx}"
        params.append(status)
        idx += 1

    total = await pool.fetchval(
        f"SELECT count(*) FROM category_candidates {where}",
        *params,
    ) or 0

    offset = (page - 1) * per_page
    rows = await pool.fetch(
        f"""
        SELECT id, proposed_name, proposed_slug, description,
               signal_count, unique_users, first_seen, last_seen,
               status, admin_notes
        FROM category_candidates {where}
        ORDER BY unique_users DESC, signal_count DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
        per_page,
        offset,
    )

    candidates = [
        CandidateListItem(
            id=str(r["id"]),
            proposed_name=r["proposed_name"],
            proposed_slug=r["proposed_slug"],
            description=r["description"],
            signal_count=r["signal_count"],
            unique_users=r["unique_users"],
            first_seen=r["first_seen"].isoformat() if r["first_seen"] else "",
            last_seen=r["last_seen"].isoformat() if r["last_seen"] else "",
            status=r["status"],
            admin_notes=r["admin_notes"],
        ).model_dump()
        for r in rows
    ]

    return {
        "candidates": candidates,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# Admin: POST /ops/category-candidates/{id}/action
# ---------------------------------------------------------------------------

@router.post("/ops/category-candidates/{candidate_id}/action")
async def action_category_candidate(
    candidate_id: str,
    req: CandidateActionRequest,
    _: bool = Depends(require_ops_key),
):
    """Approve, reject, or merge a category candidate."""
    pool = get_pool()
    if pool is None:
        raise error_response(503, "Database not available", code="DB_UNAVAILABLE")

    row = await pool.fetchrow(
        "SELECT id, proposed_slug, status FROM category_candidates WHERE id = $1::uuid",
        candidate_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if req.action == "approve":
        await pool.execute(
            "UPDATE category_candidates SET status = 'approved', admin_notes = COALESCE($2, admin_notes) WHERE id = $1::uuid",
            candidate_id,
            req.admin_notes,
        )
    elif req.action == "reject":
        await pool.execute(
            "UPDATE category_candidates SET status = 'rejected', admin_notes = COALESCE($2, admin_notes) WHERE id = $1::uuid",
            candidate_id,
            req.admin_notes,
        )
    elif req.action == "merge":
        if not req.merge_into_slug:
            raise HTTPException(status_code=400, detail="merge_into_slug required for merge action")
        # Update all suggestions with this category to point to the merge target
        await pool.execute(
            """
            UPDATE catalog_suggestions
            SET matched_category = $2, status = 'mapped'
            WHERE suggested_category = $1 AND status = 'pending'
            """,
            row["proposed_slug"],
            req.merge_into_slug,
        )
        await pool.execute(
            "UPDATE category_candidates SET status = 'rejected', admin_notes = COALESCE($2, '') || ' [merged into ' || $3 || ']' WHERE id = $1::uuid",
            candidate_id,
            req.admin_notes or "",
            req.merge_into_slug,
        )

    return {"id": candidate_id, "action": req.action, "ok": True}
