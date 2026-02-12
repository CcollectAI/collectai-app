from fastapi import APIRouter, Depends
from app.auth import require_ops_key

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/health")
async def health(_: bool = Depends(require_ops_key)):
    return {"ok": True, "source": "ops stub"}
