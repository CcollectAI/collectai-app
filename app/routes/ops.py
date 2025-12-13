from fastapi import APIRouter

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "ops stub"}
