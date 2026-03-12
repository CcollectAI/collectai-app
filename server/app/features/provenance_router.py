from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth import get_current_user_id
from app.rate_limit import per_user_rate_limit
from app.db import db_configured, get_conn
from app.errors import error_response
from app.features.pagination import pagination_params

router = APIRouter(prefix="/provenance", tags=["Provenance"])
logger = logging.getLogger(__name__)

# Per-user: 30 provenance requests per minute
_provenance_limit = per_user_rate_limit(30, window_seconds=60, scope="provenance")


class OwnershipEvent(BaseModel):
    event_id: str
    item_id: str
    user_id: str
    event_type: str = Field(
        ...,
        description="added | transferred_in | transferred_out | sale | purchase | graded | verified | updated",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: Optional[str] = None
    source: Optional[str] = Field(
        None, description="receipt | manual | marketplace | ocr | barcode | import | admin"
    )
    metadata: dict = Field(default_factory=dict)


class ProvenanceTimeline(BaseModel):
    item_id: str
    created_at: datetime
    events: List[OwnershipEvent]
    authenticity_signals: List[str] = Field(default_factory=list)


class OwnershipEventCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(
        ...,
        max_length=50,
        pattern=r"^(added|transferred_in|transferred_out|sale|purchase|graded|verified|updated)$",
    )
    note: Optional[str] = Field(None, max_length=2000)
    source: Optional[str] = Field(None, max_length=50)
    metadata: dict = Field(default_factory=dict)


# In-memory store fallback (DB_DISABLED mode)
_PROVENANCE: dict[str, ProvenanceTimeline] = {}


def _row_to_event(row) -> OwnershipEvent:
    """Convert a DB row from item_provenance_events to an OwnershipEvent model."""
    return OwnershipEvent(
        event_id=str(row["id"]),
        item_id=str(row["item_id"]),
        user_id=str(row["user_id"]),
        event_type=row["event_type"],
        timestamp=row["created_at"],
        note=row["note"],
        source=row["source"],
        metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
    )


@router.get("/items/{item_id}", response_model=ProvenanceTimeline)
async def get_provenance(
    item_id: str,
    user_id: str = Depends(get_current_user_id),
    pagination: tuple[int, int] = Depends(pagination_params),
    _rl: None = Depends(_provenance_limit),
):
    """
    Return provenance for an item.

    UI can show:
    - "Added by user X days ago"
    - "Transferred from another owner"
    - authenticity signals list
    """
    limit, offset = pagination

    if not db_configured():
        # Fallback: in-memory store
        if item_id not in _PROVENANCE:
            now = datetime.now(timezone.utc)
            timeline = ProvenanceTimeline(
                item_id=item_id,
                created_at=now,
                events=[
                    OwnershipEvent(
                        event_id=f"{item_id}-init",
                        item_id=item_id,
                        user_id=user_id,
                        event_type="added",
                        timestamp=now,
                        note="Item added to portfolio (demo)",
                    )
                ],
                authenticity_signals=[],
            )
            _PROVENANCE[item_id] = timeline
        timeline = _PROVENANCE[item_id]
        paginated_events = timeline.events[offset:offset + limit]
        return ProvenanceTimeline(
            item_id=timeline.item_id,
            created_at=timeline.created_at,
            events=paginated_events,
            authenticity_signals=timeline.authenticity_signals,
        )

    # DB mode: query item_provenance_events (only if item belongs to user)
    async with get_conn() as conn:
        # Verify item ownership first
        owner_check = await conn.fetchval(
            "SELECT 1 FROM public.items WHERE id = $1::uuid AND user_id = $2::uuid",
            item_id,
            user_id,
        )
        if owner_check is None:
            raise error_response(404, "Item not found", code="NOT_FOUND")

        rows = await conn.fetch(
            """
            SELECT id, item_id, user_id, event_type, note, source, metadata, created_at
            FROM public.item_provenance_events
            WHERE item_id = $1
            ORDER BY created_at ASC
            LIMIT $2 OFFSET $3
            """,
            item_id,
            limit,
            offset,
        )

    if not rows:
        # No provenance events yet - return an empty timeline
        # Use current time as created_at since there's no history
        now = datetime.now(timezone.utc)
        logger.info("[provenance] No events found for item=%s, returning empty timeline", item_id)
        return ProvenanceTimeline(
            item_id=item_id,
            created_at=now,
            events=[],
            authenticity_signals=[],
        )

    events = [_row_to_event(row) for row in rows]
    created_at = rows[0]["created_at"]  # earliest event timestamp

    # Derive authenticity signals from event types
    authenticity_signals = []
    event_types = {row["event_type"] for row in rows}
    if "verified" in event_types:
        authenticity_signals.append("owner_verified")
    if "graded" in event_types:
        authenticity_signals.append("professionally_graded")
    if any(row["source"] == "receipt" for row in rows):
        authenticity_signals.append("receipt_on_file")

    return ProvenanceTimeline(
        item_id=item_id,
        created_at=created_at,
        events=events,
        authenticity_signals=authenticity_signals,
    )


@router.post("/items/{item_id}/events", response_model=ProvenanceTimeline)
async def append_provenance_event(
    item_id: str,
    payload: OwnershipEventCreate,
    user_id: str = Depends(get_current_user_id),
    _rl: None = Depends(_provenance_limit),
):
    """
    Append a provenance/ownership event (transfer, sale, receipt scan, etc.).
    """
    if not db_configured():
        # Fallback: in-memory store
        timeline = _PROVENANCE.get(item_id)
        if not timeline:
            raise error_response(404, "Provenance not found", code="VALIDATION_ERROR")

        evt = OwnershipEvent(
            event_id=str(uuid4()),
            item_id=item_id,
            user_id=payload.user_id,
            event_type=payload.event_type,
            note=payload.note,
            source=payload.source,
            metadata=payload.metadata,
        )
        timeline.events.append(evt)
        _PROVENANCE[item_id] = timeline
        return timeline

    # DB mode: INSERT into item_provenance_events (verify ownership first)
    try:
        async with get_conn() as conn:
            # Verify item ownership
            owner_check = await conn.fetchval(
                "SELECT 1 FROM public.items WHERE id = $1::uuid AND user_id = $2::uuid",
                item_id,
                user_id,
            )
            if owner_check is None:
                raise error_response(404, "Item not found", code="NOT_FOUND")

            await conn.execute(
                """
                INSERT INTO public.item_provenance_events
                    (item_id, user_id, event_type, note, source, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                item_id,
                user_id,
                payload.event_type,
                payload.note,
                payload.source,
                json.dumps(payload.metadata or {}),
            )

        logger.info(
            "[provenance] Inserted event: item=%s, type=%s, user=%s",
            item_id, payload.event_type, payload.user_id,
        )

    except asyncpg.PostgresError as e:
        logger.error("[provenance] Error inserting event: %s", e)
        raise error_response(500, "Failed to save provenance event", code="DB_ERROR")

    # Return the full updated timeline (use default pagination to return first page)
    return await get_provenance(item_id, user_id, pagination=(50, 0))
