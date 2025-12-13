from fastapi import APIRouter

router = APIRouter(prefix="/vision-ops", tags=["vision-ops"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "vision-ops stub"}
