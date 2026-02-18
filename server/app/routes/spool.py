from fastapi import APIRouter

router = APIRouter(prefix="/spool", tags=["spool"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "spool stub"}
