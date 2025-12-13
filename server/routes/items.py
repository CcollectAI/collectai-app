
from fastapi import APIRouter, HTTPException
from ..db import get_pool
from ..models.items import ItemDetail

router = APIRouter()

@router.get("/items/{item_id}/detail", response_model=ItemDetail)
async def get_item_detail(item_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
              i.id,
              i.name,
              i.category,
              i.estimated_value,
              i.change_1d,

              c.slug,
              c.label,
              c.wave,
              c.active,
              c.avg_value,
              c.item_count,

              p.low,
              p.mid,
              p.high,
              p.currency,
              p.model_name,
              p.as_of,

              s.signals_json
            FROM v_item_detail i
            LEFT JOIN collectai_categories c ON c.slug = i.category
            LEFT JOIN v_item_predictions p ON p.item_id = i.id
            LEFT JOIN v_item_signals s ON s.item_id = i.id
            WHERE i.id = $1
            """,
            item_id,
        )

        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        return ItemDetail.from_record(row)

