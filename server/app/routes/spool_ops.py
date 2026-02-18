from fastapi import APIRouter

router = APIRouter(prefix="/spool-ops", tags=["spool-ops"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "spool-ops stub"}
