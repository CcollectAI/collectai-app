from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/provenance", tags=["provenance"])


class OwnershipEvent(BaseModel):
    event_id: str
    item_id: str
    user_id: str
    event_type: str = Field(
        ...,
        description="added | transferred_in | transferred_out | sale | purchase",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: Optional[str] = None
    source: Optional[str] = Field(
        None, description="receipt | manual | marketplace | ocr"
    )
    metadata: dict = Field(default_factory=dict)


class ProvenanceTimeline(BaseModel):
    item_id: str
    created_at: datetime
    events: List[OwnershipEvent]
    authenticity_signals: List[str] = Field(default_factory=list)


# In-memory store for now (DB disabled)
_PROVENANCE: dict[str, ProvenanceTimeline] = {}


@router.get("/items/{item_id}", response_model=ProvenanceTimeline)
async def get_provenance(item_id: str):
    """
    Return provenance for an item.

    UI can show:
    - "Added by user X days ago"
    - "Transferred from another owner"
    - authenticity signals list
    """
    if item_id not in _PROVENANCE:
        # create a minimal placeholder timeline
        now = datetime.now(timezone.utc)
        timeline = ProvenanceTimeline(
            item_id=item_id,
            created_at=now,
            events=[
                OwnershipEvent(
                    event_id=f"{item_id}-init",
                    item_id=item_id,
                    user_id="demo-user",
                    event_type="added",
                    timestamp=now,
                    note="Item added to portfolio (demo)",
                )
            ],
            authenticity_signals=[],
        )
        _PROVENANCE[item_id] = timeline

    return _PROVENANCE[item_id]


class OwnershipEventCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(
        ...,
        max_length=50,
        pattern=r"^(added|transferred_in|transferred_out|sale|purchase)$",
    )
    note: Optional[str] = Field(None, max_length=2000)
    source: Optional[str] = Field(None, max_length=50)
    metadata: dict = Field(default_factory=dict)


@router.post("/items/{item_id}/events", response_model=ProvenanceTimeline)
async def append_provenance_event(item_id: str, payload: OwnershipEventCreate):
    """
    Append a provenance/ownership event (transfer, sale, receipt scan, etc.).
    """
    from uuid import uuid4

    timeline = _PROVENANCE.get(item_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Provenance not found")

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
