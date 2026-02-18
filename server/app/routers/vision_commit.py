from fastapi import APIRouter

router = APIRouter(prefix="/vision-commit", tags=["vision-commit"])

@router.get("/health")
async def vision_commit_health():
    """
    Stub endpoint so `from app.routers.vision_commit import router`
    works and the app can start. Replace with the real implementation later.
    """
    return {"ok": True, "source": "stub vision_commit router"}
