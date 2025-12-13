from fastapi import APIRouter

router = APIRouter(prefix="/vision-predict-log", tags=["vision-predict-log"])

@router.get("/health")
async def vision_predict_log_health():
    """
    Stub endpoint so `from app.routers.vision_predict_log import router`
    works and the app can start. Replace with real implementation later.
    """
    return {"ok": True, "source": "stub vision_predict_log router"}
