#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/features

##############################################
# 1) Create marketplace_trust_router.py
##############################################

if [ -f app/features/marketplace_trust_router.py ]; then
  echo "app/features/marketplace_trust_router.py already exists, skipping creation."
else
  cat > app/features/marketplace_trust_router.py <<'PY'
from __future__ import annotations

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/marketplace/trust2", tags=["marketplace-trust"])


class SellerReputation(BaseModel):
    user_id: str
    score: float = Field(..., description="0-100 trust score")
    badge: str = Field(..., description="new | regular | power | verified")
    total_trades: int
    disputes: int
    dispute_rate: float


class ListingRiskFlag(BaseModel):
    listing_id: str
    risk_level: str = Field(..., description="low | medium | high")
    reasons: List[str]


class MarketplaceTrustSnapshot(BaseModel):
    seller: SellerReputation
    listing_flags: List[ListingRiskFlag] = Field(default_factory=list)


@router.get("/seller/{user_id}", response_model=SellerReputation)
async def get_seller_reputation(user_id: str):
    """
    Simple reputation endpoint, UI can show:
    - badge
    - score
    - total trades / disputes
    """
    # Demo logic; later replace with real stats from DB
    if user_id.startswith("pro"):
        badge = "power"
        score = 92.0
        trades = 80
        disputes = 1
    else:
        badge = "regular"
        score = 78.0
        trades = 37
        disputes = 1

    return SellerReputation(
        user_id=user_id,
        score=score,
        badge=badge,
        total_trades=trades,
        disputes=disputes,
        dispute_rate=disputes / trades if trades else 0.0,
    )


@router.get("/listing/{listing_id}", response_model=MarketplaceTrustSnapshot)
async def get_listing_trust_snapshot(listing_id: str):
    """
    Trust snapshot for a listing.

    Combine later with your marketplace-intel outputs.
    """
    seller = SellerReputation(
        user_id="demo-seller",
        score=88.0,
        badge="verified",
        total_trades=120,
        disputes=2,
        dispute_rate=2 / 120,
    )
    flags = [
        ListingRiskFlag(
            listing_id=listing_id,
            risk_level="low",
            reasons=["Seller verified", "Price within typical range"],
        )
    ]
    return MarketplaceTrustSnapshot(seller=seller, listing_flags=flags)
PY
fi

##############################################
# 2) Ensure app/features/__init__.py exports it
##############################################

python <<'PY'
from pathlib import Path

init_path = Path("app/features/__init__.py")
if not init_path.exists():
    init_path.write_text('from . import marketplace_trust_router  # noqa: F401\n')
    print("Created app/features/__init__.py with marketplace_trust_router only")
else:
    text = init_path.read_text()
    if "marketplace_trust_router" not in text:
        text += "from . import marketplace_trust_router  # noqa: F401\n"
        init_path.write_text(text)
        print("Updated app/features/__init__.py to export marketplace_trust_router")
    else:
        print("app/features/__init__.py already exports marketplace_trust_router")
PY

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
cp "$MAIN_FILE" "$MAIN_FILE.bak.marketplace.$(date +%s)"

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

import_line = "from app.features import marketplace_trust_router\n"
include_line = "app.include_router(marketplace_trust_router.router)\n"

if "marketplace_trust_router" not in text:
    text = import_line + text

if "app.include_router(marketplace_trust_router.router)" not in text:
    if not text.endswith("\n"):
        text += "\n"
    text += "\n# Auto-wired marketplace trust router\n" + include_line

main_path.write_text(text)
print(f"marketplace_trust_router wired into {main_path}")
PY

echo "Done: marketplace trust router added and wired."
