from fastapi import APIRouter

router = APIRouter(prefix="/manifests", tags=["manifests"])


@router.get("/health")
async def health():
    return {"ok": True, "source": "manifests stub"}
