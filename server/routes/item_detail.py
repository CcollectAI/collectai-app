from fastapi import APIRouter, HTTPException
from ..db import get_pool

router = APIRouter()


@router.get("/items/{item_id}/detail")
async def item_detail(item_id: str):
    """Single-item detail view.

    The original handler queried `v_item_detail_full` — a view that
    never existed in the live schema, so every call 404'd with
    "Item not found" regardless of whether the row was real. Switched
    to a direct `items` SELECT with the columns the FE detail screen
    consumes; the view can be reintroduced later if cross-table joins
    are needed.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, title, category, condition, condition_grade,
                   image_url, notes, purchase_price, purchase_currency,
                   purchase_date, estimated_value, attrs, archived,
                   created_at, updated_at
            FROM items
            WHERE id = $1::uuid
            """,
            item_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)
