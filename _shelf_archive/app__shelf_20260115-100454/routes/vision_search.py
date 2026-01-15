from fastapi import APIRouter

router = APIRouter(prefix="/vision-search", tags=["vision-search"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "vision-search stub"}
