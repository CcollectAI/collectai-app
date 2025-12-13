from fastapi import APIRouter
from ..db import get_pool

router = APIRouter()

@router.get("/categories")
async def list_categories():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM collectai_categories ORDER BY wave, label")
        return [dict(r) for r in rows]
