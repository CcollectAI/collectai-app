import os
import asyncpg
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DEFAULT_OWNER = "local_demo"

# CORS configuration from environment
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080"
).split(",")

app = FastAPI(title="CollectAI Signals API")

# CORS: configured via CORS_ORIGINS environment variable
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_conn():
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        raise RuntimeError("DB_DSN not set")
    return await asyncpg.connect(dsn)

from fastapi import Header, HTTPException, status


def verify_api_key(x_api_key: str = Header(alias="X-API-Key")):
    expected_key = os.environ.get("API_SHARED_SECRET")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured on server",
        )
    if x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    expected = os.environ.get("API_SHARED_SECRET")
    if not expected:
        # if misconfigured, block everything
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

class VisionLogIn(BaseModel):
    item_ref: str

class MarketHitIn(BaseModel):
    item_ref: str
    price_eur: float
    source: str | None = "api"

class PortfolioAddIn(BaseModel):
    item_ref: str
    quantity: int = 1
    acquisition_price_eur: float | None = None
    nickname: str | None = None
    notes: str | None = None
    owner_tag: str | None = None

class ScanAndAddIn(BaseModel):
    item_ref: str
    price_eur: float
    quantity: int = 1
    acquisition_price_eur: float | None = None
    nickname: str | None = None
    notes: str | None = None
    owner_tag: str | None = None
    source: str | None = "scan"

@app.post("/vision/log")
async def vision_log(body: VisionLogIn, _: bool = Depends(require_api_key)):
    conn = await get_conn()
    try:
        await conn.execute(
            "INSERT INTO public.vision_predict_log (item_ref) VALUES ($1)",
            body.item_ref,
        )
    finally:
        await conn.close()
    return {"ok": True, "item_ref": body.item_ref}

@app.post("/market_hit")
async def market_hit(body: MarketHitIn, _: bool = Depends(require_api_key)):
    conn = await get_conn()
    try:
        await conn.execute(
            """
            INSERT INTO public.market_hits (item_ref, source, price, currency, observed_at, processed)
            VALUES ($1, $2, $3, 'EUR', now(), false)
            """,
            body.item_ref,
            body.source or "api",
            body.price_eur,
        )
    finally:
        await conn.close()
    return {"ok": True, "item_ref": body.item_ref, "price_eur": body.price_eur}

@app.get("/items/signal")
async def item_signal(item_ref: str, _: bool = Depends(require_api_key)):
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM public.v_item_signal_with_category
            WHERE item_ref = $1
            ORDER BY vision_at DESC
            LIMIT 1
            """,
            item_ref,
        )
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="item_ref not found")
    return dict(row)

@app.get("/items/signal/recent")
async def recent_signals(limit: int = 20, _: bool = Depends(require_api_key)):
    if limit > 100:
        limit = 100
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT *
            FROM public.v_item_signal_with_category
            ORDER BY vision_at DESC
            LIMIT $1
            """,
            limit,
        )
    finally:
        await conn.close()
    return [dict(r) for r in rows]

@app.post("/portfolio/add")
async def portfolio_add(body: PortfolioAddIn, _: bool = Depends(require_api_key)):
    owner = body.owner_tag or DEFAULT_OWNER
    conn = await get_conn()
    try:
        await conn.execute(
            """
            INSERT INTO public.portfolio_items (
                owner_tag, item_ref, nickname, quantity, acquisition_price_eur, notes
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (owner_tag, item_ref)
            DO UPDATE SET
                nickname = COALESCE(EXCLUDED.nickname, public.portfolio_items.nickname),
                quantity = EXCLUDED.quantity,
                acquisition_price_eur = COALESCE(EXCLUDED.acquisition_price_eur, public.portfolio_items.acquisition_price_eur),
                notes = COALESCE(EXCLUDED.notes, public.portfolio_items.notes)
            """,
            owner,
            body.item_ref,
            body.nickname,
            body.quantity,
            body.acquisition_price_eur,
            body.notes,
        )
    finally:
        await conn.close()
    return {"ok": True, "owner_tag": owner, "item_ref": body.item_ref}

@app.get("/portfolio/items")
async def portfolio_items(
    owner_tag: str | None = None,
    limit: int = 100,
    _: bool = Depends(require_api_key),
):
    owner = owner_tag or DEFAULT_OWNER
    if limit > 500:
        limit = 500
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT *
            FROM public.v_portfolio_with_signals
            WHERE owner_tag = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            owner,
            limit,
        )
    finally:
        await conn.close()
    return [dict(r) for r in rows]

@app.get("/portfolio/overview")
async def portfolio_overview(owner_tag: str | None = None, _: bool = Depends(require_api_key)):
    owner = owner_tag or DEFAULT_OWNER
    conn = await get_conn()
    try:
        summary = await conn.fetchrow(
            "SELECT * FROM public.v_portfolio_summary WHERE owner_tag = $1",
            owner,
        )
        categories = await conn.fetch(
            """
            SELECT *
            FROM public.v_portfolio_by_category
            WHERE owner_tag = $1
            ORDER BY category_name NULLS LAST
            """,
            owner,
        )
    finally:
        await conn.close()
    return {
        "owner_tag": owner,
        "summary": dict(summary) if summary else None,
        "by_category": [dict(c) for c in categories],
    }

@app.get("/portfolio/timeseries")
async def portfolio_timeseries(
    owner_tag: str | None = None,
    limit: int = 90,
    _: bool = Depends(require_api_key),
):
    owner = owner_tag or DEFAULT_OWNER
    if limit > 365:
        limit = 365
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """
            SELECT day, total_est_value_eur
            FROM public.v_portfolio_value_timeseries
            WHERE owner_tag = $1
            ORDER BY day DESC
            LIMIT $2
            """,
            owner,
            limit,
        )
    finally:
        await conn.close()
    data = [dict(r) for r in reversed(rows)]
    return {"owner_tag": owner, "points": data}

@app.post("/portfolio/scan_and_add")
async def portfolio_scan_and_add(body: ScanAndAddIn, _: bool = Depends(require_api_key)):
    owner = body.owner_tag or DEFAULT_OWNER
    source = body.source or "scan"
    conn = await get_conn()
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO public.vision_predict_log (item_ref) VALUES ($1) ON CONFLICT DO NOTHING",
                body.item_ref,
            )
            await conn.execute(
                """
                INSERT INTO public.market_hits (item_ref, source, price, currency, observed_at, processed)
                VALUES ($1, $2, $3, 'EUR', now(), false)
                """,
                body.item_ref,
                source,
                body.price_eur,
            )
            await conn.execute(
                """
                INSERT INTO public.portfolio_items (
                    owner_tag, item_ref, nickname, quantity, acquisition_price_eur, notes
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (owner_tag, item_ref)
                DO UPDATE SET
                    nickname = COALESCE(EXCLUDED.nickname, public.portfolio_items.nickname),
                    quantity = EXCLUDED.quantity,
                    acquisition_price_eur = COALESCE(EXCLUDED.acquisition_price_eur, public.portfolio_items.acquisition_price_eur),
                    notes = COALESCE(EXCLUDED.notes, public.portfolio_items.notes)
                """,
                owner,
                body.item_ref,
                body.nickname,
                body.quantity,
                body.acquisition_price_eur,
                body.notes,
            )
    finally:
        await conn.close()
    return {
        "ok": True,
        "owner_tag": owner,
        "item_ref": body.item_ref,
        "price_eur": body.price_eur,
        "quantity": body.quantity,
        "source": source,
    }

@app.get("/eval/summary")
async def eval_summary(_: bool = Depends(require_api_key)):
    conn = await get_conn()
    try:
        snap = await conn.fetchrow(
            """
            SELECT *
            FROM public.collectai_eval_snapshots
            ORDER BY taken_at DESC
            LIMIT 1;
            """
        )
    finally:
        await conn.close()

    if not snap:
        return {"ok": True, "snapshot": None}
    return {"ok": True, "snapshot": dict(snap)}
