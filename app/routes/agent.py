from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "agent stub"}
