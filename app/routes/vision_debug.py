from fastapi import APIRouter

router = APIRouter(prefix="/vision-debug", tags=["vision-debug"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "vision-debug stub"}
