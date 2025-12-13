from fastapi import APIRouter, HTTPException
from ..db import get_pool

router = APIRouter()

@router.get("/items/{item_id}/detail")
async def item_detail(item_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM v_item_detail_full
            WHERE id = $1
            """,
            item_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        return dict(row)
