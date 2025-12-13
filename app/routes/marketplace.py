from fastapi import APIRouter

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "marketplace stub"}
