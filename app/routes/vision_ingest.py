from fastapi import APIRouter

router = APIRouter(prefix="/vision-ingest", tags=["vision-ingest"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "vision-ingest stub"}
