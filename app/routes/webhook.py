from fastapi import APIRouter

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "webhook stub"}
