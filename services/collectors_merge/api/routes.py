from __future__ import annotations

# load .env early (but after the future import)
try:
    from services.collectors_merge.core.env import ensure_env as _ensure_env

    _ensure_env()
except Exception:
    pass

import json
import os
import pathlib
from datetime import datetime
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile

router = APIRouter()


@router.get("/readyz")
def readyz() -> dict[str, Any]:
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("select 1")
        cur.close()
        conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True}


# ---------- DB ----------
def db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url)


# ---------- minimal helpers / fallbacks ----------
def fake_model_predict(attrs: dict[str, Any]) -> dict[str, float]:
    base = 120.0
    m = 1.0
    if attrs.get("grade") == "PSA 10":
        m *= 1.4
    if not attrs.get("sealed"):
        m *= 0.9
    q50 = base * m
    return {"q10": q50 * 0.75, "q50": q50, "q90": q50 * 1.25}


def normalized_key(category: str, attrs: dict[str, Any]) -> str:
    if category and category.lower() == "lego" and attrs.get("set_no"):
        s = f"lego|{attrs['set_no']}|pcs:{attrs.get('piece_count','?')}|ret:{1 if attrs.get('retired') else 0}|s:{1 if attrs.get('sealed') else 0}"
        return s
    return f"{(category or 'misc').lower()}|fallback"


def to_eur(amount, currency):
    return float(amount or 0.0)


def effective_price(provider, price, shipping):
    return float(price or 0) + float(shipping or 0)


# ---------- ingest/photo ----------
@router.post("/ingest/photo")
async def ingest_photo(
    image: UploadFile = File(...), to: str = Form("portfolio")
) -> dict[str, Any]:
    buf = await image.read()
    tmp_path = f"/tmp/{image.filename}"
    with open(tmp_path, "wb") as f:
        f.write(buf)
    attrs = {"sealed": False}
    return {"ok": True, "draft_item": {"attributes": attrs}, "to": to}


# ---------- items/upsert + predict_v2 ----------
@router.post("/items/upsert")
async def items_upsert(item: dict[str, Any]) -> dict[str, Any]:
    required = ["user_id", "category"]
    if not all(k in item for k in required):
        raise HTTPException(400, f"Missing fields: {required}")
    attrs = item.get("attributes_json") or {}
    if not item.get("normalized_key"):
        item["normalized_key"] = normalized_key(item["category"], attrs)
    q = """
    insert into public.items (user_id, category, normalized_key, title, condition, grade, graded_by, sealed, attributes_json, images)
    values (%(user_id)s, %(category)s, %(normalized_key)s, %(title)s, %(condition)s, %(grade)s, %(graded_by)s, %(sealed)s, %(attributes_json)s::jsonb, %(images)s::jsonb)
    on conflict do nothing
    returning id;
    """
    conn = db()
    cur = conn.cursor()
    cur.execute(
        q,
        {
            "user_id": item["user_id"],
            "category": item["category"].lower(),
            "normalized_key": item.get("normalized_key"),
            "title": item.get("title"),
            "condition": item.get("condition"),
            "grade": item.get("grade"),
            "graded_by": item.get("graded_by"),
            "sealed": item.get("sealed"),
            "attributes_json": json.dumps(attrs),
            "images": json.dumps(item.get("images") or []),
        },
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """select id from public.items
                       where user_id=%s and category=%s and coalesce(normalized_key,'')=coalesce(%s,'') and coalesce(title,'')=coalesce(%s,'')
                       order by created_at desc limit 1""",
            (
                item["user_id"],
                item["category"].lower(),
                item.get("normalized_key"),
                item.get("title"),
            ),
        )
        row = cur.fetchone()
    item_id = row[0]
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True, "item_id": str(item_id)}


@router.post("/predict_v2")
async def predict_v2(payload: dict[str, Any]) -> dict[str, Any]:
    attrs = payload.get("attributes") or {}
    item_id = payload.get("item_id")
    if item_id is None:
        raise HTTPException(400, "item_id is required")
    preds = fake_model_predict(attrs)
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        insert into public.price_predictions (item_id, model_version, y_hat, q10, q50, q90, conf_score, features_used, asof)
        values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb, now())
    """,
        (
            item_id,
            os.getenv("MODEL_VERSION", "v0"),
            preds["q50"],
            preds["q10"],
            preds["q50"],
            preds["q90"],
            0.80,
            json.dumps({"attrs": attrs}),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {
        "q10": round(preds["q10"], 2),
        "q50": round(preds["q50"], 2),
        "q90": round(preds["q90"], 2),
        "asof": datetime.utcnow().isoformat() + "Z",
    }


# ---------- market search + price-guide ----------
@router.get("/market/search")
async def market_search(
    category: str,
    normalized_key: str = None,
    query: str = None,
    since_days: int = 90,
    limit: int = 100,
):
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if normalized_key:
        cur.execute(
            """
            select provider, listing_id, title, price, currency, shipping, condition, graded, ended_at, url, seller_score
            from public.market_hits
            where normalized_key=%s and ended_at >= now() - (%s || ' days')::interval
            order by ended_at desc
            limit %s
        """,
            (normalized_key, since_days, limit),
        )
    else:
        q = (query or "").lower()
        cur.execute(
            """
            select provider, listing_id, title, price, currency, shipping, condition, graded, ended_at, url, seller_score
            from public.market_hits
            where lower(title) %s %% (%s) and ended_at >= now() - (%s || ' days')::interval
            order by similarity(lower(title), %s) desc, ended_at desc
            limit %s
        """,
            ("%%", q, since_days, q, limit),
        )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    enriched = []
    for r in rows:
        p = r.get("price")
        eur = to_eur(float(p), r.get("currency")) if p is not None else None
        eff = (
            effective_price(r.get("provider"), eur, r.get("shipping"))
            if eur is not None
            else None
        )
        r["eur_price"] = eur
        r["effective_price"] = eff
        enriched.append(r)
    return {"ok": True, "rows": enriched[:limit]}


@router.get("/market/price-guide")
async def market_price_guide(normalized_key: str, horizon_days: int = 90):
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        select price, currency, shipping, provider, ended_at
        from public.market_hits
        where normalized_key=%s and ended_at >= now() - interval '90 days'
    """,
        (normalized_key,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    pts = []
    for r in rows:
        eur = (
            to_eur(float(r["price"]), r["currency"]) if r["price"] is not None else None
        )
        eff = (
            effective_price(r["provider"], eur, r.get("shipping"))
            if eur is not None
            else None
        )
        if eff is None:
            continue
        pts.append({"ended_at": r["ended_at"], "value": eff})

    def median(values):
        if not values:
            return None
        s = sorted(values)
        n = len(s)
        mid = n // 2
        return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2

    import datetime as _dt
    from collections import defaultdict

    buckets = defaultdict(list)
    for p in pts:
        d = p["ended_at"].date().isoformat()
        buckets[d].append(p["value"])
    series = []
    today = _dt.date.today()
    for i in range(horizon_days, -1, -1):
        d = (today - _dt.timedelta(days=i)).isoformat()
        values = buckets.get(d, [])
        m = median(values)
        if values:
            svals = sorted(values)
            o = svals[0]
            h = svals[-1]
            l = svals[0]
            c = svals[-1]
            series.append(
                {
                    "date": d,
                    "median": round(m, 2),
                    "count": len(values),
                    "volume": round(sum(values), 2),
                    "open": round(o, 2),
                    "high": round(h, 2),
                    "low": round(l, 2),
                    "close": round(c, 2),
                }
            )
        else:
            series.append(
                {
                    "date": d,
                    "median": None,
                    "count": 0,
                    "volume": 0,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": None,
                }
            )
    return {"ok": True, "series": series, "count": len(pts)}


# ---------- watchlist ----------
@router.post("/watchlist/add")
async def watchlist_add(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = payload.get("user_id")
    nk = payload.get("normalized_key")
    if not user_id or not nk:
        raise HTTPException(400, "user_id and normalized_key required")
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """insert into public.watchlist (user_id, normalized_key) values (%s,%s) on conflict do nothing""",
        (user_id, nk),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


# ---------- sanity ----------
@router.get("/sanity/ready")
async def sanity_ready():
    out = {"ok": True, "checks": {}}
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(
            "select to_regclass('public.items'), to_regclass('public.market_hits'), to_regclass('public.price_predictions')"
        )
        items_tbl, hits_tbl, preds_tbl = cur.fetchone()
        out["checks"]["tables"] = bool(items_tbl and hits_tbl and preds_tbl)
        cur.execute(
            """select count(1) from pg_indexes 
                       where schemaname='public' and indexname in
                       ('idx_items_user','idx_items_category','idx_mh_provider_listing','idx_mh_ended_at','idx_mh_normkey','idx_mh_title_lower','idx_pp_item_asof')"""
        )
        out["checks"]["indexes"] = cur.fetchone()[0] >= 5
        cur.execute("select count(1) from public.market_hits")
        out["checks"]["market_hits_count"] = cur.fetchone()[0]
        cur.close()
        conn.close()
    except Exception as e:
        out["ok"] = False
        out["checks"]["db_error"] = str(e)
    out["checks"]["fts_sidecar"] = pathlib.Path("data/search.db").exists()
    out["checks"]["calibration_report"] = pathlib.Path(
        "calibration_report.json"
    ).exists()
    out["checks"]["redis"] = bool(os.getenv("REDIS_URL"))
    out["ok"] = (
        out["ok"] and out["checks"].get("tables") and out["checks"].get("indexes")
    )
    return out


@router.post("/sanity/e2e")
async def sanity_e2e(user_id: str, category: str = "lego", nk_hint: str = None):
    report = {"ok": True, "steps": {}}
    conn = db()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        attrs = (
            {"set_no": "10240", "sealed": True, "retired": True, "piece_count": 1559}
            if category.lower() == "lego"
            else {"sealed": False}
        )
        cur.execute(
            """insert into public.items (user_id, category, normalized_key, title, sealed, attributes_json)
                       values (%s,%s,%s,%s,%s,%s::jsonb) returning id""",
            (
                user_id,
                category,
                nk_hint or None,
                "Sanity Temp Item",
                attrs.get("sealed"),
                json.dumps(attrs),
            ),
        )
        item_id = cur.fetchone()[0]
        report["steps"]["item_created"] = True
        preds = fake_model_predict(attrs)
        report["steps"]["predicted"] = preds
        nk = nk_hint or normalized_key(category, attrs)
        cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur2.execute(
            """select title, price, currency, shipping, ended_at, provider from public.market_hits
                        where normalized_key=%s order by ended_at desc limit 5""",
            (nk,),
        )
        comps = cur2.fetchall()
        report["steps"]["comps_found"] = len(comps)
        prices = []
        for r in comps:
            eur = (
                to_eur(float(r["price"]), r["currency"])
                if r["price"] is not None
                else None
            )
            eff = (
                effective_price(r["provider"], eur, r.get("shipping"))
                if eur is not None
                else None
            )
            if eff is not None:
                prices.append(eff)
        report["steps"]["price_guide_median"] = (
            sorted(prices)[len(prices) // 2] if prices else None
        )
        report["steps"]["rolled_back"] = True
        conn.rollback()
    except Exception as e:
        conn.rollback()
        report["ok"] = False
        report["error"] = str(e)
    finally:
        conn.close()
    return report


# -------- Alerts preview (no DB writes) --------
@router.get("/alerts/preview")
async def alerts_preview(
    normalized_key: str, spike_pct: float = 15.0
) -> dict[str, Any]:
    conn = db()
    cur = conn.cursor()

    def med(days: int) -> float | None:
        cur.execute(
            """
            with vals as (
              select (mh.price + coalesce(mh.shipping,0))::numeric as v
              from public.market_hits mh
              where mh.normalized_key=%s and mh.ended_at >= now() - (%s || ' days')::interval
            )
            select percentile_disc(0.5) within group (order by v) from vals
        """,
            (normalized_key, days),
        )
        r = cur.fetchone()
        return float(r[0]) if r and r[0] is not None else None

    p30 = med(30)
    p7 = med(7)
    cur.close()
    conn.close()
    if p30 is None or p7 is None:
        return {
            "ok": True,
            "nk": normalized_key,
            "p7": p7,
            "p30": p30,
            "delta_pct": None,
            "trigger": False,
        }
    delta = (p7 - p30) / p30 * 100.0
    trigger = (delta >= spike_pct) or (delta <= -spike_pct)
    return {
        "ok": True,
        "nk": normalized_key,
        "p7": round(p7, 2),
        "p30": round(p30, 2),
        "delta_pct": round(delta, 2),
        "spike_pct": spike_pct,
        "trigger": trigger,
    }


# -------- CSV export of comps --------
@router.get("/market/export_csv")
async def market_export_csv(normalized_key: str, horizon_days: int = 90):
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        select provider, listing_id, title, price, currency, shipping, condition, graded, ended_at, url, seller_score
        from public.market_hits
        where normalized_key=%s and ended_at >= now() - (%s || ' days')::interval
        order by ended_at desc
    """,
        (normalized_key, horizon_days),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    import csv
    import io

    buf = io.StringIO()
    fieldnames = (
        list(rows[0].keys())
        if rows
        else [
            "provider",
            "listing_id",
            "title",
            "price",
            "currency",
            "shipping",
            "condition",
            "graded",
            "ended_at",
            "url",
            "seller_score",
        ]
    )
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {k: (str(v) if v is not None else "") for k, v in dict(r).items()}
        )
    return Response(content=buf.getvalue(), media_type="text/csv")


# -------- Price Guide V2 (IQR + per-condition) --------
@router.get("/market/price_guide_v2")
async def market_price_guide_v2(
    normalized_key: str, horizon_days: int = 90, iqr_k: float = 1.5
) -> dict[str, Any]:
    import statistics as _stats

    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        select provider, price, currency, shipping, condition, graded, ended_at
        from public.market_hits
        where normalized_key=%s and ended_at >= now() - (%s || ' days')::interval
        order by ended_at desc
    """,
        (normalized_key, horizon_days),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    def eff(r):
        return float(r["price"] or 0) + float(r.get("shipping") or 0)

    prices = [eff(r) for r in rows]
    if not prices:
        return {
            "ok": True,
            "count": 0,
            "series": [],
            "overall": {},
            "by_condition": {},
            "filters": {"iqr_k": iqr_k},
        }

    # IQR filtering
    qtiles = _stats.quantiles(prices, n=4)  # [Q1, Q2, Q3]
    q1, q3 = qtiles[0], qtiles[-1]
    iqr = q3 - q1
    lo, hi = q1 - iqr_k * iqr, q3 + iqr_k * iqr
    filtered = [r for r in rows if lo <= eff(r) <= hi]

    # chronological series
    from datetime import datetime

    series = [
        {
            "t": (
                r["ended_at"].isoformat()
                if hasattr(r["ended_at"], "isoformat")
                else str(r["ended_at"])
            ),
            "v": eff(r),
        }
        for r in sorted(filtered, key=lambda x: x["ended_at"] or datetime.utcnow())
    ]

    # per-condition/“sealed-ish” buckets
    buckets: dict[str, list] = {}
    for r in filtered:
        cond = (r.get("condition") or "unknown").lower()
        sealedish = "sealed" if (r.get("graded") or cond == "new") else "open"
        buckets.setdefault(f"{cond}|{sealedish}", []).append(eff(r))

    def pct(arr, p):
        if not arr:
            return None
        s = sorted(arr)
        idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[idx])

    by_condition = {
        k: {
            "count": len(v),
            "p10": round(pct(v, 10), 2),
            "q50": round(pct(v, 50), 2),
            "p90": round(pct(v, 90), 2),
        }
        for k, v in buckets.items()
    }
    overall = [eff(r) for r in filtered]
    out = {
        "ok": True,
        "count": len(filtered),
        "series": series,
        "overall": {
            "p10": round(pct(overall, 10), 2) if overall else None,
            "q50": round(pct(overall, 50), 2) if overall else None,
            "p90": round(pct(overall, 90), 2) if overall else None,
        },
        "by_condition": by_condition,
        "filters": {"iqr_k": iqr_k, "lo": round(lo, 2), "hi": round(hi, 2)},
    }
    return out


@router.post("/watchlist/remove")
async def watchlist_remove(payload: dict[str, Any]) -> dict[str, Any]:
    uid = payload.get("user_id")
    nk = payload.get("normalized_key")
    if not uid or not nk:
        raise HTTPException(400, "user_id and normalized_key required")
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """delete from public.watchlist where user_id=%s and normalized_key=%s""",
        (uid, nk),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


@router.get("/watchlist/list")
async def watchlist_list(user_id: str) -> dict[str, Any]:
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """select normalized_key, created_at from public.watchlist where user_id=%s order by created_at desc""",
        (user_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"ok": True, "items": rows}


# -------- Price Guide V2 (IQR + per-condition) --------
@router.get("/market/price_guide_v2")
async def market_price_guide_v2(
    normalized_key: str, horizon_days: int = 90, iqr_k: float = 1.5
) -> dict[str, Any]:
    import statistics as _stats

    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        select provider, price, currency, shipping, condition, graded, ended_at
        from public.market_hits
        where normalized_key=%s and ended_at >= now() - (%s || ' days')::interval
        order by ended_at desc
    """,
        (normalized_key, horizon_days),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    def eff(r):
        return float(r["price"] or 0) + float(r.get("shipping") or 0)

    prices = [eff(r) for r in rows]
    if not prices:
        return {
            "ok": True,
            "count": 0,
            "series": [],
            "overall": {},
            "by_condition": {},
            "filters": {"iqr_k": iqr_k},
        }

    qtiles = _stats.quantiles(prices, n=4)  # [Q1, Q2, Q3]
    q1, q3 = qtiles[0], qtiles[-1]
    iqr = q3 - q1
    lo, hi = q1 - iqr_k * iqr, q3 + iqr_k * iqr
    filtered = [r for r in rows if lo <= eff(r) <= hi]

    from datetime import datetime

    series = [
        {
            "t": (
                r["ended_at"].isoformat()
                if hasattr(r["ended_at"], "isoformat")
                else str(r["ended_at"])
            ),
            "v": eff(r),
        }
        for r in sorted(filtered, key=lambda x: x["ended_at"] or datetime.utcnow())
    ]

    buckets: dict[str, list] = {}
    for r in filtered:
        cond = (r.get("condition") or "unknown").lower()
        sealedish = "sealed" if (r.get("graded") or cond == "new") else "open"
        buckets.setdefault(f"{cond}|{sealedish}", []).append(eff(r))

    def pct(arr, p):
        if not arr:
            return None
        s = sorted(arr)
        idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[idx])

    by_condition = {
        k: {
            "count": len(v),
            "p10": round(pct(v, 10), 2),
            "q50": round(pct(v, 50), 2),
            "p90": round(pct(v, 90), 2),
        }
        for k, v in buckets.items()
    }
    overall = [eff(r) for r in filtered]
    out = {
        "ok": True,
        "count": len(filtered),
        "series": series,
        "overall": {
            "p10": round(pct(overall, 10), 2) if overall else None,
            "q50": round(pct(overall, 50), 2) if overall else None,
            "p90": round(pct(overall, 90), 2) if overall else None,
        },
        "by_condition": by_condition,
        "filters": {"iqr_k": iqr_k, "lo": round(lo, 2), "hi": round(hi, 2)},
    }
    return out


# -------- Typo-tolerant search (pg_trgm) --------
@router.get("/market/search_smart")
async def market_search_smart(
    q: str, limit: int = 20, min_sim: float = 0.2
) -> dict[str, Any]:
    """
    Trigram similarity over recent market_hits.title.
    Returns unique (normalized_key, best_title, best_price, sim) per NK.
    """
    q = (q or "").strip()
    if not q:
        return {"ok": True, "items": []}
    limit = max(1, min(100, limit))
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # prefer trigram index
    cur.execute("set local enable_seqscan = off;")
    cur.execute(
        """
      with scored as (
        select
          mh.normalized_key,
          mh.title,
          (mh.price + coalesce(mh.shipping,0))::numeric as v,
          similarity(mh.title, %s) as sim,
          mh.ended_at
        from public.market_hits mh
        where mh.ended_at >= now() - interval '365 days'
          and mh.title % %s
      ),
      filtered as (
        select * from scored where sim >= %s
      ),
      ranked as (
        select *,
          row_number() over (partition by normalized_key order by sim desc, ended_at desc) as rn
        from filtered
      )
      select normalized_key, title as best_title, v as best_price, sim
      from ranked
      where rn = 1
      order by sim desc
      limit %s
    """,
        (q, q, min_sim, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"ok": True, "items": rows}


# -------- Typo-tolerant search (pg_trgm) --------
@router.get("/market/search_smart")
async def market_search_smart(
    q: str, limit: int = 20, min_sim: float = 0.2
) -> dict[str, Any]:
    """
    Trigram similarity over recent market_hits.title.
    Returns unique (normalized_key, best_title, best_price, sim) per NK.
    """
    q = (q or "").strip()
    if not q:
        return {"ok": True, "items": []}
    limit = max(1, min(100, limit))
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("set local enable_seqscan = off;")
    cur.execute(
        """
      with scored as (
        select
          mh.normalized_key,
          mh.title,
          (mh.price + coalesce(mh.shipping,0))::numeric as v,
          similarity(mh.title, %s) as sim,
          mh.ended_at
        from public.market_hits mh
        where mh.ended_at >= now() - interval '365 days'
          and mh.title % %s
      ),
      filtered as (
        select * from scored where sim >= %s
      ),
      ranked as (
        select *,
          row_number() over (partition by normalized_key order by sim desc, ended_at desc) as rn
        from filtered
      )
      select normalized_key, title as best_title, v as best_price, sim
      from ranked
      where rn = 1
      order by sim desc
      limit %s
    """,
        (q, q, min_sim, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return {"ok": True, "items": rows}


# -------- Resilient typo-tolerant search --------
@router.get("/market/search_any")
async def market_search_any(
    q: str, limit: int = 20, min_sim: float = 0.2
) -> dict[str, Any]:
    """
    Try pg_trgm similarity; on error, fallback to ILIKE.
    Always returns JSON (ok / fallback / error).
    """
    q = (q or "").strip()
    if not q:
        return {"ok": True, "items": []}
    limit = max(1, min(100, limit))

    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Prefer trigram path
        cur.execute("set local enable_seqscan = off;")
        cur.execute(
            """
          with scored as (
            select
              mh.normalized_key,
              mh.title,
              (mh.price + coalesce(mh.shipping,0))::numeric as v,
              similarity(mh.title, %s) as sim,
              mh.ended_at
            from public.market_hits mh
            where mh.ended_at >= now() - interval '365 days'
          ),
          filtered as (select * from scored where sim >= %s),
          ranked as (
            select *, row_number() over (partition by normalized_key order by sim desc, ended_at desc) as rn
            from filtered
          )
          select normalized_key, title as best_title, v as best_price, sim
          from ranked
          where rn = 1
          order by sim desc
          limit %s
        """,
            (q, min_sim, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "items": rows, "engine": "trgm"}
    except Exception as e:
        # Fallback: ILIKE
        try:
            like = f"%{q}%"
            cur.execute(
                """
              with ranked as (
                select
                  mh.normalized_key,
                  mh.title,
                  (mh.price + coalesce(mh.shipping,0))::numeric as v,
                  mh.ended_at,
                  row_number() over (partition by mh.normalized_key order by mh.ended_at desc) as rn
                from public.market_hits mh
                where mh.ended_at >= now() - interval '365 days'
                  and mh.title ilike %s
              )
              select normalized_key, title as best_title, v as best_price, 1.0 as sim
              from ranked
              where rn = 1
              order by best_price desc
              limit %s
            """,
                (like, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()
            return {
                "ok": True,
                "fallback": True,
                "error": str(e),
                "items": rows,
                "engine": "ilike",
            }
        except Exception as e2:
            cur.close()
            conn.close()
            return {
                "ok": False,
                "error": f"search failed: {e}; fallback failed: {e2}",
                "items": [],
            }


# -------- Resilient typo-tolerant search --------
@router.get("/market/search_any")
async def market_search_any(
    q: str, limit: int = 20, min_sim: float = 0.2
) -> dict[str, Any]:
    """
    Try pg_trgm similarity; on error, fallback to ILIKE.
    Always returns JSON (ok / fallback / error).
    """
    q = (q or "").strip()
    if not q:
        return {"ok": True, "items": []}
    limit = max(1, min(100, limit))

    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Prefer trigram path
        cur.execute("set local enable_seqscan = off;")
        cur.execute(
            """
          with scored as (
            select
              mh.normalized_key,
              mh.title,
              (mh.price + coalesce(mh.shipping,0))::numeric as v,
              similarity(mh.title, %s) as sim,
              mh.ended_at
            from public.market_hits mh
            where mh.ended_at >= now() - interval '365 days'
          ),
          filtered as (select * from scored where sim >= %s),
          ranked as (
            select *, row_number() over (partition by normalized_key order by sim desc, ended_at desc) as rn
            from filtered
          )
          select normalized_key, title as best_title, v as best_price, sim
          from ranked
          where rn = 1
          order by sim desc
          limit %s
        """,
            (q, min_sim, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"ok": True, "items": rows, "engine": "trgm"}
    except Exception as e:
        # Fallback: ILIKE
        try:
            like = f"%{q}%"
            cur.execute(
                """
              with ranked as (
                select
                  mh.normalized_key,
                  mh.title,
                  (mh.price + coalesce(mh.shipping,0))::numeric as v,
                  mh.ended_at,
                  row_number() over (partition by mh.normalized_key order by mh.ended_at desc) as rn
                from public.market_hits mh
                where mh.ended_at >= now() - interval '365 days'
                  and mh.title ilike %s
              )
              select normalized_key, title as best_title, v as best_price, 1.0 as sim
              from ranked
              where rn = 1
              order by best_price desc
              limit %s
            """,
                (like, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            conn.close()
            return {
                "ok": True,
                "fallback": True,
                "error": str(e),
                "items": rows,
                "engine": "ilike",
            }
        except Exception as e2:
            cur.close()
            conn.close()
            return {
                "ok": False,
                "error": f"search failed: {e}; fallback failed: {e2}",
                "items": [],
            }


# -------- Photo Fastpass v1 (resilient) --------
@router.post("/ingest/fastpass_v1")
async def ingest_fastpass_v1(
    user_id: str = Form(...),
    category: str = Form(...),
    watchlist: int = Form(0),
    image: UploadFile = File(...),
) -> dict[str, Any]:
    import json
    import os
    from datetime import datetime

    # 1) normalize photo
    try:
        from services.collectors_merge.core.ocr.image_io import normalize_photo
    except Exception as e:
        raise HTTPException(500, f"image normalize unavailable: {e}")
    raw = await image.read()
    photo_bytes, norm_name = normalize_photo(raw, image.filename or "upload.jpg")

    # 2) OCR hints (best-effort)
    ocr_fields: dict[str, Any] = {}
    try:
        from services.collectors_merge.core.ocr.psa import ocr_psa_bytes

        r = ocr_psa_bytes(photo_bytes, norm_name)
        if r.get("ok"):
            ocr_fields = r.get("fields", {}) or {}
    except Exception:
        # fine — OCR optional
        pass

    # 3) NK candidates (filename + OCR hints)
    try:
        from services.collectors_merge.core.normalize.resolve import (
            candidates_from_text,
        )
    except Exception:

        def candidates_from_text(text, category):
            return [f"{(category or 'misc').lower()}|fallback"]

    hint = (
        f"{norm_name} {ocr_fields.get('cert','')} {ocr_fields.get('grade','')}".strip()
    )
    candidates = candidates_from_text(hint, category)
    guess = candidates[0] if candidates else f"{(category or 'misc').lower()}|fallback"

    # 4) upsert item (tolerates images column missing; will omit if needed)
    item: dict[str, Any] = {}
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    inserted = False
    try:
        cur.execute(
            """
          insert into public.items (user_id, category, title, normalized_key, sealed, attributes_json, images)
          values (%s,%s,%s,%s,false,%s::jsonb,%s::jsonb)
          returning id, user_id, category, title, normalized_key, sealed, attributes_json
        """,
            (
                user_id,
                category,
                norm_name,
                guess,
                json.dumps(ocr_fields),
                json.dumps([{"name": norm_name}]),
            ),
        )
        item = dict(cur.fetchone())
        inserted = True
    except Exception:
        # fallback: without images column
        cur.close()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
          insert into public.items (user_id, category, title, normalized_key, sealed, attributes_json)
          values (%s,%s,%s,%s,false,%s::jsonb)
          returning id, user_id, category, title, normalized_key, sealed, attributes_json
        """,
            (user_id, category, norm_name, guess, json.dumps(ocr_fields)),
        )
        item = dict(cur.fetchone())
        inserted = True

    # optional watchlist
    if int(watchlist or 0) == 1:
        try:
            cur2 = conn.cursor()
            cur2.execute(
                """insert into public.watchlist(user_id, normalized_key)
                            values (%s,%s) on conflict do nothing""",
                (user_id, guess),
            )
            cur2.close()
        except Exception:
            pass

    conn.commit()
    cur.close()
    conn.close()

    # 5) prediction (best-effort)
    prediction: dict[str, Any] = {"ok": False, "error": "predict_v2 skipped"}
    try:
        import httpx

        base = os.getenv("BASE_URL", "http://localhost:8080")
        body = {
            "item_id": item["id"],
            "attributes": {"grade": ocr_fields.get("grade"), "sealed": False},
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{base}/predict_v2", json=body)
        prediction = (
            resp.json()
            if resp.status_code == 200
            else {"ok": False, "error": f"HTTP {resp.status_code}"}
        )
    except Exception as e:
        prediction = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "item": item,
        "normalized_key": guess,
        "candidates": candidates,
        "ocr_fields": (ocr_fields or None),
        "prediction": prediction,
        "meta": {"inserted": inserted, "at": datetime.utcnow().isoformat() + "Z"},
    }


# -------- Baseline prediction (model file) --------
@router.post("/predict/baseline_v1")
async def predict_baseline_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload: {"item_id": "<int-or-uuid>", "attributes": {"grade": "PSA 10", "sealed": true/false}}
    Reads models/baseline.json and returns {ok, q10, q50, q90, used_bucket}.
    """
    import json
    import os

    item_id = str(payload.get("item_id"))
    attrs = payload.get("attributes") or {}
    sealed = bool(attrs.get("sealed", False))

    # grade10 bucket
    g = (attrs.get("grade") or "").upper().strip()
    grade10 = 1 if ("PSA 10" in g or g == "10") else 0

    # fetch item (works for int or uuid by casting to text)
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "select id, normalized_key, category, title from public.items where id::text=%s limit 1",
        (item_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"ok": False, "error": f"item_id not found: {item_id}"}

    # load model
    path = "models/baseline.json"
    if not os.path.exists(path):
        return {"ok": False, "error": "baseline model missing (models/baseline.json)"}
    model = json.load(open(path))
    med_by_group = model.get("median_by_group") or {}

    key = f"sealed={int(sealed)}|grade10={int(grade10)}"
    median = med_by_group.get(key)
    if median is None:
        # graceful backoffs
        median = (
            med_by_group.get(f"sealed={int(sealed)}|grade10=0")
            or med_by_group.get(f"sealed=0|grade10={int(grade10)}")
            or med_by_group.get("sealed=0|grade10=0")
        )
        if median is None:
            return {"ok": False, "error": "no median for any bucket"}

    # simple spread (you can swap to calibrated deltas later)
    q50 = float(median)
    q10 = round(max(0.0, q50 * 0.8), 2)
    q90 = round(q50 * 1.2, 2)

    return {
        "ok": True,
        "item_id": row["id"],
        "normalized_key": row["normalized_key"],
        "bucket_key": key,
        "q10": q10,
        "q50": round(q50, 2),
        "q90": q90,
    }


# -------- Baseline prediction (model file) --------
@router.post("/predict/baseline_v1")
async def predict_baseline_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload: {"item_id": "<int-or-uuid>", "attributes": {"grade": "PSA 10", "sealed": true/false}}
    Reads models/baseline.json and returns {ok, q10, q50, q90, used_bucket}.
    """
    import json
    import os

    item_id = str(payload.get("item_id"))
    attrs = payload.get("attributes") or {}
    sealed = bool(attrs.get("sealed", False))

    # grade10 bucket
    g = (attrs.get("grade") or "").upper().strip()
    grade10 = 1 if ("PSA 10" in g or g == "10") else 0

    # fetch item (works for int or uuid by casting to text)
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "select id, normalized_key, category, title from public.items where id::text=%s limit 1",
        (item_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"ok": False, "error": f"item_id not found: {item_id}"}

    # load model
    path = "models/baseline.json"
    if not os.path.exists(path):
        return {"ok": False, "error": "baseline model missing (models/baseline.json)"}
    model = json.load(open(path))
    med_by_group = model.get("median_by_group") or {}

    key = f"sealed={int(sealed)}|grade10={int(grade10)}"
    median = med_by_group.get(key)
    if median is None:
        # graceful backoffs
        median = (
            med_by_group.get(f"sealed={int(sealed)}|grade10=0")
            or med_by_group.get(f"sealed=0|grade10={int(grade10)}")
            or med_by_group.get("sealed=0|grade10=0")
        )
        if median is None:
            return {"ok": False, "error": "no median for any bucket"}

    # simple spread (you can swap to calibrated deltas later)
    q50 = float(median)
    q10 = round(max(0.0, q50 * 0.8), 2)
    q90 = round(q50 * 1.2, 2)

    return {
        "ok": True,
        "item_id": row["id"],
        "normalized_key": row["normalized_key"],
        "bucket_key": key,
        "q10": q10,
        "q50": round(q50, 2),
        "q90": q90,
    }


# -------- Baseline prediction (model file) --------
@router.post("/predict/baseline_v1")
async def predict_baseline_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload: {"item_id": "<int-or-uuid>", "attributes": {"grade": "PSA 10", "sealed": true/false}}
    Uses models/baseline.json (median_by_group) and returns q10/q50/q90.
    """
    import json
    import os

    item_id = str(payload.get("item_id"))
    attrs = payload.get("attributes") or {}
    sealed = bool(attrs.get("sealed", False))

    g = (attrs.get("grade") or "").upper().strip()
    grade10 = 1 if ("PSA 10" in g or g == "10") else 0

    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "select id, normalized_key from public.items where id::text=%s limit 1",
        (item_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"ok": False, "error": f"item_id not found: {item_id}"}

    path = "models/baseline.json"
    if not os.path.exists(path):
        return {"ok": False, "error": "baseline model missing (models/baseline.json)"}
    model = json.load(open(path))
    med_by_group = model.get("median_by_group") or {}

    key = f"sealed={int(sealed)}|grade10={int(grade10)}"
    median = (
        med_by_group.get(key)
        or med_by_group.get(f"sealed={int(sealed)}|grade10=0")
        or med_by_group.get(f"sealed=0|grade10={int(grade10)}")
        or med_by_group.get("sealed=0|grade10=0")
    )

    if median is None:
        return {"ok": False, "error": "no median for any bucket"}

    q50 = float(median)
    q10 = round(max(0.0, q50 * 0.8), 2)
    q90 = round(q50 * 1.2, 2)

    return {
        "ok": True,
        "item_id": row["id"],
        "normalized_key": row["normalized_key"],
        "bucket_key": key,
        "q10": q10,
        "q50": round(q50, 2),
        "q90": q90,
    }


# -------- Hybrid prediction v1 --------
@router.post("/predict/hybrid_v1")
async def predict_hybrid_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload: {"item_id": "<int-or-uuid>", "attributes": {"grade":"PSA 10","sealed":true/false}}
    Strategy:
      1) If enough recent comps for NK -> IQR filter -> p10/q50/p90 ("comps") with confidence by velocity.
      2) Else fall back to baseline buckets ("baseline").
    """
    import json
    import os
    import statistics as _stats
    from datetime import datetime

    item_id = str(payload.get("item_id"))
    attrs = payload.get("attributes") or {}
    sealed = bool(attrs.get("sealed", False))
    g = (attrs.get("grade") or "").upper().strip()
    grade10 = 1 if ("PSA 10" in g or g == "10") else 0

    def pct(arr, p):
        if not arr:
            return None
        s = sorted(arr)
        i = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[i])

    # fetch item + NK
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "select id, normalized_key from public.items where id::text=%s limit 1",
        (item_id,),
    )
    it = cur.fetchone()
    if not it:
        cur.close()
        conn.close()
        return {"ok": False, "error": f"item_id not found: {item_id}"}
    nk = it["normalized_key"]

    # 1) comps path
    cur.execute(
        """
      select (price + coalesce(shipping,0))::numeric as v, ended_at, seller_score
      from public.market_hits
      where normalized_key=%s and ended_at >= now() - interval '180 days'
      order by ended_at desc
    """,
        (nk,),
    )
    comps = [dict(r) for r in cur.fetchall()]

    def eff(r):
        return float(r["v"])

    prices = [eff(r) for r in comps]
    if len(prices) >= 6:
        q1 = _stats.quantiles(prices, n=4)[0]
        q3 = _stats.quantiles(prices, n=4)[-1]
        iqr = max(1e-9, q3 - q1)
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        filt = [r for r in comps if lo <= eff(r) <= hi]

        vals = [eff(r) for r in filt]
        if len(vals) >= 4:
            # velocity & seller quality nudge
            vel_60 = sum(
                1
                for r in filt
                if r["ended_at"] and (datetime.utcnow() - r["ended_at"]).days <= 60
            )
            sellers_ok = sum(1 for r in filt if (r.get("seller_score") or 0) >= 0.98)
            conf = min(0.95, 0.5 + 0.05 * vel_60 + 0.05 * sellers_ok)  # 0.5..0.95

            out = {
                "ok": True,
                "source": "comps",
                "normalized_key": nk,
                "q10": round(pct(vals, 10), 2),
                "q50": round(pct(vals, 50), 2),
                "q90": round(pct(vals, 90), 2),
                "n_raw": len(prices),
                "n_used": len(vals),
                "confidence": round(conf, 2),
            }
            cur.close()
            conn.close()
            return out

    # 2) baseline fallback
    cur.close()
    conn.close()
    path = "models/baseline.json"
    if not os.path.exists(path):
        return {"ok": False, "error": "baseline model missing (models/baseline.json)"}
    model = json.load(open(path))
    med = (model.get("median_by_group") or {}).get(
        f"sealed={int(sealed)}|grade10={int(grade10)}"
    )
    if med is None:
        med = (model.get("median_by_group") or {}).get("sealed=0|grade10=0")
    if med is None:
        return {"ok": False, "error": "no baseline bucket found"}

    q50 = float(med)
    q10 = max(0.0, q50 * 0.8)
    q90 = q50 * 1.2
    return {
        "ok": True,
        "source": "baseline",
        "normalized_key": nk,
        "q10": round(q10, 2),
        "q50": round(q50, 2),
        "q90": round(q90, 2),
        "confidence": 0.5,
    }


# -------- Item NK update --------
@router.post("/items/update_nk")
async def items_update_nk(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload: {"item_id":"<uuid-or-int>", "normalized_key":"lego|..."}
    """
    item_id = str(payload.get("item_id") or "")
    nk = str(payload.get("normalized_key") or "")
    if not item_id or not nk:
        raise HTTPException(400, "item_id and normalized_key required")

    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "update public.items set normalized_key=%s where id::text=%s returning id, normalized_key",
        (nk, item_id),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not row:
        return {"ok": False, "error": "item not found"}
    return {"ok": True, "item_id": row["id"], "normalized_key": row["normalized_key"]}


# -------- NK suggestions from text --------
@router.get("/market/suggest_nk")
async def market_suggest_nk(text: str, category: str) -> dict[str, Any]:
    try:
        from services.collectors_merge.core.normalize.resolve import (
            candidates_from_text,
        )
    except Exception:

        def candidates_from_text(t, c):
            return [f"{(c or 'misc').lower()}|fallback"]

    cands = candidates_from_text(text, category)
    return {"ok": True, "candidates": cands[:10]}


# -------- Hybrid prediction v1 (comps-first, baseline fallback) --------
@router.post("/predict/hybrid_v1")
async def predict_hybrid_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload: {"item_id": "<int-or-uuid>", "attributes": {"grade":"PSA 10","sealed":true/false}}
    Strategy:
      1) Use recent comps for the item's normalized_key (IQR filter) -> p10/q50/p90 + confidence.
      2) If not enough comps, fall back to baseline model (models/baseline.json).
    """
    import json
    import os
    import statistics as _stats
    from datetime import datetime

    item_id = str(payload.get("item_id") or "")
    attrs = payload.get("attributes") or {}
    sealed = bool(attrs.get("sealed", False))
    g = (attrs.get("grade") or "").upper().strip()
    grade10 = 1 if ("PSA 10" in g or g == "10") else 0

    # fetch item + nk (works for UUID or int by casting to text)
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "select id, normalized_key from public.items where id::text=%s limit 1",
        (item_id,),
    )
    it = cur.fetchone()
    if not it:
        cur.close()
        conn.close()
        return {"ok": False, "error": f"item_id not found: {item_id}"}
    nk = it["normalized_key"]

    # comps from last 180 days
    cur.execute(
        """
      select (price + coalesce(shipping,0))::numeric as v, ended_at, seller_score
      from public.market_hits
      where normalized_key=%s and ended_at >= now() - interval '180 days'
      order by ended_at desc
    """,
        (nk,),
    )
    comps = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    def eff(r):
        try:
            return float(r["v"])
        except:
            return None

    vals_raw = [eff(r) for r in comps if eff(r) is not None]

    # If enough comps, do IQR filter
    if len(vals_raw) >= 6:
        try:
            qs = _stats.quantiles(vals_raw, n=4)  # [Q1, Q2, Q3]
            q1, q3 = qs[0], qs[-1]
            iqr = max(1e-9, q3 - q1)
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            comps_used = [
                r for r in comps if (eff(r) is not None and lo <= eff(r) <= hi)
            ]
            vals = [eff(r) for r in comps_used]
        except Exception:
            comps_used = comps
            vals = vals_raw

        def pct(arr, p):
            if not arr:
                return None
            s = sorted(arr)
            idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
            return float(s[idx])

        # velocity & seller quality for a simple confidence score
        now = datetime.utcnow()
        vel_60 = sum(
            1
            for r in comps_used
            if r.get("ended_at")
            and isinstance(r["ended_at"], datetime)
            and (now - r["ended_at"]).days <= 60
        )
        sellers_ok = sum(1 for r in comps_used if (r.get("seller_score") or 0) >= 0.98)
        conf = min(0.95, 0.5 + 0.05 * vel_60 + 0.05 * sellers_ok)  # 0.5..0.95

        return {
            "ok": True,
            "source": "comps",
            "normalized_key": nk,
            "q10": round(pct(vals, 10), 2) if vals else None,
            "q50": round(pct(vals, 50), 2) if vals else None,
            "q90": round(pct(vals, 90), 2) if vals else None,
            "n_raw": len(vals_raw),
            "n_used": len(vals),
            "confidence": round(conf, 2),
        }

    # baseline fallback
    path = "models/baseline.json"
    if not os.path.exists(path):
        return {"ok": False, "error": "baseline model missing (models/baseline.json)"}
    try:
        model = json.load(open(path))
    except Exception as e:
        return {"ok": False, "error": f"bad baseline model: {e}"}

    med_by_group = model.get("median_by_group") or {}
    key = f"sealed={int(sealed)}|grade10={int(grade10)}"
    median = (
        med_by_group.get(key)
        or med_by_group.get(f"sealed={int(sealed)}|grade10=0")
        or med_by_group.get(f"sealed=0|grade10={int(grade10)}")
        or med_by_group.get("sealed=0|grade10=0")
    )

    if median is None:
        return {"ok": False, "error": "no baseline bucket found"}

    q50 = float(median)
    q10 = max(0.0, q50 * 0.8)
    q90 = q50 * 1.2
    return {
        "ok": True,
        "source": "baseline",
        "normalized_key": nk,
        "q10": round(q10, 2),
        "q50": round(q50, 2),
        "q90": round(q90, 2),
        "confidence": 0.5,
    }


# -------- Hybrid prediction v1 (SAFE) --------
@router.post("/predict/hybrid_safe_v1")
async def predict_hybrid_safe_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload:
      {"item_id":"<uuid-or-int>",
       "attributes":{"grade":"PSA 10","sealed":true/false}}
    Returns JSON always: comps-first, baseline fallback, confidence.
    """
    try:
        import json
        import os
        import statistics as _stats
        from datetime import datetime

        item_id = str((payload or {}).get("item_id") or "")
        attrs = (payload or {}).get("attributes") or {}
        sealed = bool(attrs.get("sealed", False))
        g = (attrs.get("grade") or "").upper().strip()
        grade10 = 1 if ("PSA 10" in g or g == "10") else 0

        # fetch item -> nk
        conn = db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "select id, normalized_key from public.items where id::text=%s limit 1",
            (item_id,),
        )
        it = cur.fetchone()
        if not it:
            cur.close()
            conn.close()
            return {"ok": False, "error": f"item_id not found: {item_id}"}
        nk = it["normalized_key"]

        # pull comps last 180d
        cur.execute(
            """
          select (price + coalesce(shipping,0))::numeric as v, ended_at, seller_score
          from public.market_hits
          where normalized_key=%s and ended_at >= now() - interval '180 days'
          order by ended_at desc
        """,
            (nk,),
        )
        comps = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()

        def eff(r):
            try:
                return float(r["v"])
            except:
                return None

        vals_raw = [eff(r) for r in comps if eff(r) is not None]

        # helper: percentile
        def pct(arr, p):
            if not arr:
                return None
            s = sorted(arr)
            i = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
            return float(s[i])

        # helper: days ago tolerant to strings
        now = datetime.utcnow()

        def days_ago(x):
            try:
                if hasattr(x, "isoformat"):
                    return (now - x).days
                from datetime import datetime as _dt

                return (now - _dt.fromisoformat(str(x).split(".")[0])).days
            except Exception:
                return 9999

        # comps path with IQR filter if enough
        if len(vals_raw) >= 6:
            try:
                qs = _stats.quantiles(vals_raw, n=4)  # [Q1, Q2, Q3]
                q1, q3 = qs[0], qs[-1]
                iqr = max(1e-9, q3 - q1)
                lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                comps_used = [
                    r for r in comps if (eff(r) is not None and lo <= eff(r) <= hi)
                ]
                vals = [eff(r) for r in comps_used]
            except Exception:
                comps_used = comps
                vals = vals_raw

            vel_60 = sum(1 for r in comps_used if days_ago(r.get("ended_at")) <= 60)
            sellers_ok = sum(
                1 for r in comps_used if (r.get("seller_score") or 0) >= 0.98
            )
            conf = min(0.95, 0.5 + 0.05 * vel_60 + 0.05 * sellers_ok)

            return {
                "ok": True,
                "source": "comps",
                "normalized_key": nk,
                "q10": round(pct(vals, 10), 2) if vals else None,
                "q50": round(pct(vals, 50), 2) if vals else None,
                "q90": round(pct(vals, 90), 2) if vals else None,
                "n_raw": len(vals_raw),
                "n_used": len(vals),
                "confidence": round(conf, 2),
            }

        # baseline fallback
        path = "models/baseline.json"
        if not os.path.exists(path):
            return {
                "ok": False,
                "error": "baseline model missing (models/baseline.json)",
            }
        try:
            model = json.load(open(path))
        except Exception as e:
            return {"ok": False, "error": f"bad baseline model: {e}"}

        med_by_group = model.get("median_by_group") or {}
        key = f"sealed={int(sealed)}|grade10={int(grade10)}"
        median = (
            med_by_group.get(key)
            or med_by_group.get(f"sealed={int(sealed)}|grade10=0")
            or med_by_group.get(f"sealed=0|grade10={int(grade10)}")
            or med_by_group.get("sealed=0|grade10=0")
        )

        if median is None:
            return {"ok": False, "error": "no baseline bucket found"}

        q50 = float(median)
        q10 = max(0.0, q50 * 0.8)
        q90 = q50 * 1.2
        return {
            "ok": True,
            "source": "baseline",
            "normalized_key": nk,
            "q10": round(q10, 2),
            "q50": round(q50, 2),
            "q90": round(q90, 2),
            "confidence": 0.5,
        }

    except Exception as e:
        return {"ok": False, "error": f"hybrid_safe_v1 failed: {str(e)}"}


# -------- Photo Fastpass v2 (clean) --------
@router.post("/ingest/fastpass_v2")
async def ingest_fastpass_v2(
    user_id: str = Form(...),
    category: str = Form(...),
    watchlist: int = Form(0),
    image: UploadFile = File(...),
    # Optional tuning for the embedded guide
    guide_recent_days: int = Form(90),
    guide_min_seller_score: float = Form(0.98),
    guide_iqr_k: float = Form(1.5),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    import json
    import os

    # 1) normalize photo (dev-safe)
    try:
        from services.collectors_merge.core.ocr.image_io import normalize_photo
    except Exception as e:
        raise HTTPException(500, f"image normalize unavailable: {e}")
    raw = await image.read()
    photo_bytes, norm_name = normalize_photo(raw, image.filename or "upload.jpg")

    # 2) OCR best-effort (OK if not installed)
    ocr_fields: dict[str, Any] = {}
    try:
        from services.collectors_merge.core.ocr.psa import ocr_psa_bytes

        r = ocr_psa_bytes(photo_bytes, norm_name)
        if r.get("ok"):
            ocr_fields = r.get("fields", {}) or {}
    except Exception:
        pass

    # 3) NK candidates from text
    try:
        from services.collectors_merge.core.normalize.resolve import (
            candidates_from_text,
        )
    except Exception:

        def candidates_from_text(text, category):
            return [f"{(category or 'misc').lower()}|fallback"]

    hint = (
        f"{norm_name} {ocr_fields.get('cert','')} {ocr_fields.get('grade','')}".strip()
    )
    candidates = candidates_from_text(hint, category)
    guess = candidates[0] if candidates else f"{(category or 'misc').lower()}|fallback"

    # 4) Upsert item (images optional)
    conn = db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
          insert into public.items (user_id, category, title, normalized_key, sealed, attributes_json, images)
          values (%s,%s,%s,%s,false,%s::jsonb,%s::jsonb)
          returning id, user_id, category, title, normalized_key, sealed, attributes_json
        """,
            (
                user_id,
                category,
                norm_name,
                guess,
                json.dumps(ocr_fields),
                json.dumps([{"name": norm_name}]),
            ),
        )
    except Exception:
        cur.close()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
          insert into public.items (user_id, category, title, normalized_key, sealed, attributes_json)
          values (%s,%s,%s,%s,false,%s::jsonb)
          returning id, user_id, category, title, normalized_key, sealed, attributes_json
        """,
            (user_id, category, norm_name, guess, json.dumps(ocr_fields)),
        )
    item = dict(cur.fetchone())

    # watchlist
    if int(watchlist or 0) == 1:
        try:
            cur2 = conn.cursor()
            cur2.execute(
                """insert into public.watchlist(user_id, normalized_key)
                            values (%s,%s) on conflict do nothing""",
                (user_id, guess),
            )
            cur2.close()
        except Exception:
            pass
    conn.commit()
    cur.close()
    conn.close()

    # 5) Hybrid prediction + mini price guide (with auth forwarding)
    pred: dict[str, Any] = {"ok": False, "error": "hybrid skipped"}
    guide: dict[str, Any] = {"ok": False, "error": "guide skipped"}
    try:
        import httpx

        base = os.getenv("BASE_URL", "http://localhost:8080")
        headers = {}
        auth = authorization
        if auth:
            headers["authorization"] = auth
        async with httpx.AsyncClient(timeout=6.0) as client:
            h_body = {
                "item_id": item["id"],
                "attributes": {"grade": ocr_fields.get("grade"), "sealed": False},
            }
            h = await client.post(
                f"{base}/predict/hybrid_safe_v1", json=h_body, headers=headers
            )
            pred = (
                h.json()
                if h.status_code == 200
                else {"ok": False, "error": f"hybrid HTTP {h.status_code}"}
            )

            params = {
                "normalized_key": item["normalized_key"],
                "horizon_days": max(7, int(guide_recent_days)),
                "iqr_k": float(guide_iqr_k),
                "min_seller_score": float(guide_min_seller_score),
                "recent_days": max(7, int(guide_recent_days)),
            }
            g = await client.get(
                f"{base}/market/price_guide_v2", params=params, headers=headers
            )
            guide = (
                g.json()
                if g.status_code == 200
                else {"ok": False, "error": f"guide HTTP {g.status_code}"}
            )
    except Exception as e:
        pred = {"ok": False, "error": f"hybrid/guide error: {e}"}

    return {
        "ok": True,
        "item": item,
        "normalized_key": guess,
        "candidates": candidates,
        "ocr_fields": (ocr_fields or None),
        "prediction": (
            pred
            if isinstance(pred, dict)
            else (
                {"ok": False, "error": "pred-unexpected"}
                if isinstance(pred, dict)
                else (
                    {"ok": False, "error": "pred-unexpected"}
                    if isinstance(pred, dict)
                    else {"ok": False, "error": "pred-unexpected"}
                )
            )
        ),
        "guide": (
            guide
            if isinstance(guide, dict)
            else (
                {"ok": False, "error": "guide-unexpected"}
                if isinstance(guide, dict)
                else (
                    {"ok": False, "error": "guide-unexpected"}
                    if isinstance(guide, dict)
                    else {"ok": False, "error": "guide-unexpected"}
                )
            )
        ),
    }


@router.post("/ingest/fastpass")
async def ingest_fastpass_alias(
    user_id: str = Form(...),
    category: str = Form(...),
    watchlist: int = Form(0),
    image: UploadFile = File(...),
    guide_recent_days: int = Form(90),
    guide_min_seller_score: float = Form(0.98),
    guide_iqr_k: float = Form(1.5),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    return await ingest_fastpass_v2(
        user_id=user_id,
        category=category,
        watchlist=watchlist,
        image=image,
        guide_recent_days=guide_recent_days,
        guide_min_seller_score=guide_min_seller_score,
        guide_iqr_k=guide_iqr_k,
        authorization=authorization,
    )
