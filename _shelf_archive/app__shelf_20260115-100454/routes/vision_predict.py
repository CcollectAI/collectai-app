from fastapi import APIRouter

router = APIRouter(prefix="/vision-predict", tags=["vision-predict"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "vision-predict stub"}
