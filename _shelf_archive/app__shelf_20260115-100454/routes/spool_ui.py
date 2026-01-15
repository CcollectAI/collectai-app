from fastapi import APIRouter

router = APIRouter(prefix="/spool-ui", tags=["spool-ui"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "spool-ui stub"}
