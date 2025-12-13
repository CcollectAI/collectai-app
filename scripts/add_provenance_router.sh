#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/features

##############################################
# 1) Create provenance_router.py
##############################################

if [ -f app/features/provenance_router.py ]; then
  echo "app/features/provenance_router.py already exists, skipping creation."
else
  cat > app/features/provenance_router.py <<'PY'
from __future__ import annotations

from datetime import datetime
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)
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
        now = datetime.utcnow()
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
    user_id: str
    event_type: str
    note: Optional[str] = None
    source: Optional[str] = None
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
PY
fi

##############################################
# 2) Ensure app/features/__init__.py exports it
##############################################

if [ ! -f app/features/__init__.py ]; then
  cat > app/features/__init__.py <<'PY'
"""
Feature routers package.
"""

from . import alerts_feature_router  # noqa: F401
from . import trends_and_deepdive_router  # noqa: F401
from . import provenance_router  # noqa: F401
PY
else
  python <<'PY'
from pathlib import Path

init_path = Path("app/features/__init__.py")
text = init_path.read_text()
changed = False

if "alerts_feature_router" not in text:
    text += "\nfrom . import alerts_feature_router  # noqa: F401\n"
    changed = True

if "trends_and_deepdive_router" not in text:
    text += "from . import trends_and_deepdive_router  # noqa: F401\n"
    changed = True

if "provenance_router" not in text:
    text += "from . import provenance_router  # noqa: F401\n"
    changed = True

if changed:
    init_path.write_text(text)
    print("Updated app/features/__init__.py")
else:
    print("app/features/__init__.py already exports provenance_router")
PY
fi

##############################################
# 3) Wire router into main.py or app/main.py
##############################################

if [ -f "main.py" ]; then
  MAIN_FILE="main.py"
elif [ -f "app/main.py" ]; then
  MAIN_FILE="app/main.py"
else
  echo "ERROR: Could not find main.py or app/main.py" >&2
  exit 1
fi

echo "Using main file: $MAIN_FILE"
cp "$MAIN_FILE" "$MAIN_FILE.bak.provenance.$(date +%s)"

python <<'PY'
from pathlib import Path

candidates = ["main.py", "app/main.py"]
main_path = None
for c in candidates:
    p = Path(c)
    if p.exists():
        main_path = p
        break

if main_path is None:
    raise SystemExit("No main file found.")

text = main_path.read_text()

import_line = "from app.features import provenance_router\n"
include_line = "app.include_router(provenance_router.router)\n"

if "provenance_router" not in text:
    text = import_line + text

if "app.include_router(provenance_router.router)" not in text:
    if not text.endswith("\n"):
        text += "\n"
    text += "\n# Auto-wired provenance router\n" + include_line

main_path.write_text(text)
print(f"provenance_router wired into {main_path}")
PY

echo "Done: provenance router added and wired."
