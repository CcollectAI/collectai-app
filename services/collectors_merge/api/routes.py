from __future__ import annotations

# load .env early (but after the future import)
try:
    from services.collectors_merge.core.env import ensure_env as _ensure_env

    _ensure_env()
except Exception as _env_err:
    import logging as _logging
    _logging.getLogger(__name__).warning("Failed to load env: %s", _env_err)

import csv
import io
import json
import logging
import os
import pathlib
import statistics as _stats
from collections import defaultdict
from datetime import datetime, timedelta, date, timezone
from typing import Any

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/readyz")
def readyz() -> dict[str, Any]:
    try:
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("select 1")
            cur.close()
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


from contextlib import contextmanager

@contextmanager
def db_conn():
    """Context manager that guarantees connection cleanup."""
    conn = db()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------- Model inference ----------
def _load_model_artifact(category: str) -> dict | None:
    """Load the active model artifact for a category from Supabase model_registry."""
    try:
        with db_conn() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """SELECT artifact_json FROM public.model_registry
                   WHERE category=%s AND is_active=true
                   AND (is_canary IS NULL OR is_canary=false)
                   ORDER BY created_at DESC LIMIT 1""",
                (category,),
            )
            row = cur.fetchone()
            cur.close()
            if row and row.get("artifact_json"):
                art = row["artifact_json"]
                return json.loads(art) if isinstance(art, str) else art
    except Exception as e:
        logger.warning("Failed to load model artifact for %s: %s", category, e)
    return None


def _model_predict(category: str, attrs: dict[str, Any]) -> dict[str, float]:
    """
    Predict q10/q50/q90 using trained ridge model.
    Falls back to baseline model, then to simple heuristic.
    """
    # 1) Try trained ridge model
    artifact = _load_model_artifact(category)
    if artifact:
        try:
            from inference import ridge_infer_quantiles

            # Build features from attributes
            features = _attrs_to_features(attrs)
            quantiles = ridge_infer_quantiles(artifact, features)
            if quantiles:
                return quantiles
        except Exception as e:
            logger.warning("Ridge inference failed for %s: %s", category, e)

    # 2) Try baseline model file
    baseline_path = "models/baseline.json"
    if os.path.exists(baseline_path):
        try:
            with open(baseline_path) as _f:
                model = json.load(_f)
            med_by_group = model.get("median_by_group") or {}
            sealed = bool(attrs.get("sealed", False))
            g = (attrs.get("grade") or "").upper().strip()
            grade10 = 1 if ("PSA 10" in g or g == "10") else 0
            key = f"sealed={int(sealed)}|grade10={int(grade10)}"
            median = (
                med_by_group.get(key)
                or med_by_group.get(f"sealed={int(sealed)}|grade10=0")
                or med_by_group.get(f"sealed=0|grade10={int(grade10)}")
                or med_by_group.get("sealed=0|grade10=0")
            )
            if median is not None:
                q50 = float(median)
                return {"q10": round(max(0, q50 * 0.8), 2), "q50": round(q50, 2), "q90": round(q50 * 1.2, 2)}
        except Exception as e:
            logger.warning("Baseline model failed: %s", e)

    # 3) Simple heuristic fallback
    base = 120.0
    m = 1.0
    if attrs.get("grade") == "PSA 10":
        m *= 1.4
    if not attrs.get("sealed"):
        m *= 0.9
    q50 = base * m
    return {"q10": round(q50 * 0.75, 2), "q50": round(q50, 2), "q90": round(q50 * 1.25, 2)}


def _attrs_to_features(attrs: dict[str, Any]) -> dict[str, float]:
    """Convert item attributes dict to numeric features for ridge model."""
    features: dict[str, float] = {}

    # Condition score
    cond = (attrs.get("condition") or attrs.get("condition_guess") or "").lower()
    cond_map = {
        "mint": 0.95, "gem mint": 0.98, "near mint": 0.85, "nm": 0.85,
        "excellent": 0.75, "ex": 0.75, "good": 0.6, "lp": 0.6, "light play": 0.6,
        "played": 0.45, "mp": 0.45, "moderate play": 0.45,
        "poor": 0.25, "hp": 0.25, "heavy play": 0.25, "damaged": 0.15,
    }
    # Match longest key first to prevent "mint" matching before "near mint"
    features["condition_score"] = next(
        (v for k, v in sorted(cond_map.items(), key=lambda x: -len(x[0])) if k in cond), 0.5
    )

    # Grade score (PSA/BGS/CGC)
    grade_str = (attrs.get("grade") or "").upper().strip()
    if grade_str:
        try:
            grade_num = float(grade_str.split()[-1])
            features["condition_score"] = min(1.0, grade_num / 10.0)
        except (ValueError, IndexError):
            pass

    # Rarity score
    features["rarity_score"] = float(attrs.get("rarity_score", 0.5))

    # Edition score
    edition = (attrs.get("edition") or attrs.get("edition_guess") or "").lower()
    if "1st" in edition or "first" in edition or "alpha" in edition:
        features["edition_score"] = 0.95
    elif "shadowless" in edition:
        features["edition_score"] = 0.90
    elif "unlimited" in edition:
        features["edition_score"] = 0.70
    elif "promo" in edition:
        features["edition_score"] = 0.65
    else:
        features["edition_score"] = 0.5

    # Boolean features
    if attrs.get("sealed"):
        features["is_sealed"] = 1.0
    if attrs.get("is_foil"):
        features["is_foil"] = 1.0
    if attrs.get("is_graded") or grade_str:
        features["is_graded"] = 1.0

    return features


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
    import tempfile
    buf = await image.read()
    suffix = pathlib.Path(image.filename or "upload").suffix or ".bin"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="collectai_")
    try:
        os.write(fd, buf)
    finally:
        os.close(fd)
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
    with db_conn() as conn:
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
    return {"ok": True, "item_id": str(item_id)}


@router.post("/predict_v2")
async def predict_v2(payload: dict[str, Any]) -> dict[str, Any]:
    attrs = payload.get("attributes") or {}
    item_id = payload.get("item_id")
    category = payload.get("category", "").lower()
    if item_id is None:
        raise HTTPException(400, "item_id is required")

    # If no category in payload, look it up from DB
    if not category:
        try:
            with db_conn() as conn:
                cur = conn.cursor()
                cur.execute("select category from public.items where id::text=%s limit 1", (str(item_id),))
                row = cur.fetchone()
                cur.close()
                if row:
                    category = row[0] or ""
        except Exception as e:
            logger.warning("predict_v2: category lookup failed for item_id=%s: %s", item_id, e)

    preds = _model_predict(category, attrs)

    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            insert into public.price_predictions (item_id, model_version, y_hat, q10, q50, q90, conf_score, features_used, asof)
            values (%s,%s,%s,%s,%s,%s,%s,%s::jsonb, now())
        """,
            (
                item_id,
                os.getenv("MODEL_VERSION", "ridge_v2"),
                preds["q50"],
                preds["q10"],
                preds["q50"],
                preds["q90"],
                0.80,
                json.dumps({"attrs": attrs, "category": category}),
            ),
        )
        conn.commit()
        cur.close()
    return {
        "q10": preds["q10"],
        "q50": preds["q50"],
        "q90": preds["q90"],
        "asof": datetime.now(timezone.utc).isoformat() + "Z",
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
    since_days = max(1, min(365, int(since_days)))
    limit = max(1, min(500, int(limit)))
    with db_conn() as conn:
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
    horizon_days = max(1, min(365, int(horizon_days)))
    with db_conn() as conn:
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

    buckets = defaultdict(list)
    for p in pts:
        d = p["ended_at"].date().isoformat()
        buckets[d].append(p["value"])
    series = []
    today = date.today()
    for i in range(horizon_days, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        values = buckets.get(d, [])
        m = median(values)
        if values:
            svals = sorted(values)
            series.append(
                {
                    "date": d,
                    "median": round(m, 2),
                    "count": len(values),
                    "volume": round(sum(values), 2),
                    "open": round(svals[0], 2),
                    "high": round(svals[-1], 2),
                    "low": round(svals[0], 2),
                    "close": round(svals[-1], 2),
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
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """insert into public.watchlist (user_id, normalized_key) values (%s,%s) on conflict do nothing""",
            (user_id, nk),
        )
        conn.commit()
        cur.close()
    return {"ok": True}


@router.post("/watchlist/remove")
async def watchlist_remove(payload: dict[str, Any]) -> dict[str, Any]:
    uid = payload.get("user_id")
    nk = payload.get("normalized_key")
    if not uid or not nk:
        raise HTTPException(400, "user_id and normalized_key required")
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """delete from public.watchlist where user_id=%s and normalized_key=%s""",
            (uid, nk),
        )
        conn.commit()
        cur.close()
    return {"ok": True}


@router.get("/watchlist/list")
async def watchlist_list(user_id: str) -> dict[str, Any]:
    with db_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """select normalized_key, created_at from public.watchlist where user_id=%s order by created_at desc""",
            (user_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return {"ok": True, "items": rows}


# ---------- sanity ----------
@router.get("/sanity/ready")
async def sanity_ready():
    out = {"ok": True, "checks": {}}
    try:
        with db_conn() as conn:
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
    with db_conn() as conn:
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
            preds = _model_predict(category, attrs)
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
    return report


# -------- Alerts preview (no DB writes) --------
@router.get("/alerts/preview")
async def alerts_preview(
    normalized_key: str, spike_pct: float = 15.0
) -> dict[str, Any]:
    spike_pct = max(1.0, min(100.0, float(spike_pct)))
    with db_conn() as conn:
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
    horizon_days = max(1, min(365, int(horizon_days)))
    with db_conn() as conn:
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

    buf = io.StringIO()
    fieldnames = (
        list(rows[0].keys())
        if rows
        else [
            "provider", "listing_id", "title", "price", "currency", "shipping",
            "condition", "graded", "ended_at", "url", "seller_score",
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
    horizon_days = max(1, min(365, int(horizon_days)))
    iqr_k = max(0.5, min(5.0, float(iqr_k)))
    with db_conn() as conn:
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
    qtiles = _stats.quantiles(prices, n=4)
    q1, q3 = qtiles[0], qtiles[-1]
    iqr = q3 - q1
    lo, hi = q1 - iqr_k * iqr, q3 + iqr_k * iqr
    filtered = [r for r in rows if lo <= eff(r) <= hi]

    series = [
        {
            "t": (
                r["ended_at"].isoformat()
                if hasattr(r["ended_at"], "isoformat")
                else str(r["ended_at"])
            ),
            "v": eff(r),
        }
        for r in sorted(filtered, key=lambda x: x["ended_at"] or datetime.now(timezone.utc))
    ]

    # per-condition buckets
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
    return {
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


# -------- Typo-tolerant search (pg_trgm) --------
@router.get("/market/search_smart")
async def market_search_smart(
    q: str, limit: int = 20, min_sim: float = 0.2
) -> dict[str, Any]:
    """Trigram similarity over recent market_hits.title."""
    q = (q or "").strip()
    if not q:
        return {"ok": True, "items": []}
    limit = max(1, min(100, limit))
    with db_conn() as conn:
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
              and mh.title %% %s
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
    return {"ok": True, "items": rows}


# -------- Resilient typo-tolerant search --------
@router.get("/market/search_any")
async def market_search_any(
    q: str, limit: int = 20, min_sim: float = 0.2
) -> dict[str, Any]:
    """Try pg_trgm similarity; on error, fallback to ILIKE."""
    q = (q or "").strip()
    if not q:
        return {"ok": True, "items": []}
    limit = max(1, min(100, limit))

    with db_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
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
            return {"ok": True, "items": rows, "engine": "trgm"}
        except Exception as e:
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
                return {
                    "ok": True,
                    "fallback": True,
                    "error": str(e),
                    "items": rows,
                    "engine": "ilike",
                }
            except Exception as e2:
                cur.close()
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
    except Exception as e:
        logger.warning("fastpass_v1: OCR failed: %s", e)

    # 3) NK candidates
    try:
        from services.collectors_merge.core.normalize.resolve import candidates_from_text
    except Exception as e:
        logger.warning("fastpass_v1: candidates_from_text unavailable, using fallback: %s", e)
        def candidates_from_text(text, category):
            return [f"{(category or 'misc').lower()}|fallback"]

    hint = f"{norm_name} {ocr_fields.get('cert','')} {ocr_fields.get('grade','')}".strip()
    candidates = candidates_from_text(hint, category)
    guess = candidates[0] if candidates else f"{(category or 'misc').lower()}|fallback"

    # 4) upsert item
    item: dict[str, Any] = {}
    inserted = False
    with db_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
              insert into public.items (user_id, category, title, normalized_key, sealed, attributes_json, images)
              values (%s,%s,%s,%s,false,%s::jsonb,%s::jsonb)
              returning id, user_id, category, title, normalized_key, sealed, attributes_json
            """,
                (user_id, category, norm_name, guess, json.dumps(ocr_fields), json.dumps([{"name": norm_name}])),
            )
            item = dict(cur.fetchone())
            inserted = True
        except Exception as e:
            logger.warning("fastpass_v1: insert with images failed, retrying without: %s", e)
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

        if int(watchlist or 0) == 1:
            try:
                cur2 = conn.cursor()
                cur2.execute(
                    """insert into public.watchlist(user_id, normalized_key)
                                values (%s,%s) on conflict do nothing""",
                    (user_id, guess),
                )
                cur2.close()
            except Exception as e:
                logger.warning("fastpass_v1: watchlist insert failed: %s", e)

        conn.commit()
        cur.close()

    # 5) prediction (best-effort)
    prediction: dict[str, Any] = {"ok": False, "error": "predict_v2 skipped"}
    try:
        import httpx

        base = os.getenv("BASE_URL", "http://localhost:8080")
        body = {
            "item_id": item["id"],
            "category": category,
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
        "meta": {"inserted": inserted, "at": datetime.now(timezone.utc).isoformat() + "Z"},
    }


# -------- Baseline prediction (model file) --------
@router.post("/predict/baseline_v1")
async def predict_baseline_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """Uses models/baseline.json (median_by_group) and returns q10/q50/q90."""
    item_id = str(payload.get("item_id"))
    attrs = payload.get("attributes") or {}
    sealed = bool(attrs.get("sealed", False))

    g = (attrs.get("grade") or "").upper().strip()
    grade10 = 1 if ("PSA 10" in g or g == "10") else 0

    with db_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "select id, normalized_key from public.items where id::text=%s limit 1",
            (item_id,),
        )
        row = cur.fetchone()
        cur.close()
    if not row:
        return {"ok": False, "error": f"item_id not found: {item_id}"}

    path = "models/baseline.json"
    if not os.path.exists(path):
        return {"ok": False, "error": "baseline model missing (models/baseline.json)"}
    with open(path) as _f:
        model = json.load(_f)
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


# -------- Hybrid prediction v1 (comps-first, baseline fallback) --------
@router.post("/predict/hybrid_v1")
async def predict_hybrid_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """Comps-first with IQR filter, baseline fallback."""
    item_id = str(payload.get("item_id") or "")
    attrs = payload.get("attributes") or {}
    sealed = bool(attrs.get("sealed", False))
    g = (attrs.get("grade") or "").upper().strip()
    grade10 = 1 if ("PSA 10" in g or g == "10") else 0

    with db_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "select id, normalized_key from public.items where id::text=%s limit 1",
            (item_id,),
        )
        it = cur.fetchone()
        if not it:
            cur.close()
            return {"ok": False, "error": f"item_id not found: {item_id}"}
        nk = it["normalized_key"]

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

    def eff(r):
        try:
            return float(r["v"])
        except (TypeError, ValueError, KeyError):
            return None

    def pct(arr, p):
        if not arr:
            return None
        s = sorted(arr)
        idx = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
        return float(s[idx])

    def days_ago(x):
        try:
            if hasattr(x, "isoformat"):
                return (datetime.now(timezone.utc) - x).days
            return (datetime.now(timezone.utc) - datetime.fromisoformat(str(x).split(".")[0])).days
        except (TypeError, ValueError) as e:
            logger.debug("days_ago parse error: %s", e)
            return 9999

    vals_raw = [eff(r) for r in comps if eff(r) is not None]

    if len(vals_raw) >= 6:
        try:
            qs = _stats.quantiles(vals_raw, n=4)
            q1, q3 = qs[0], qs[-1]
            iqr = max(1e-9, q3 - q1)
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            comps_used = [r for r in comps if (eff(r) is not None and lo <= eff(r) <= hi)]
            vals = [eff(r) for r in comps_used]
        except Exception as e:
            logger.warning("Outlier detection fallback: %s", e)
            comps_used = comps
            vals = vals_raw

        vel_60 = sum(1 for r in comps_used if days_ago(r.get("ended_at")) <= 60)
        sellers_ok = sum(1 for r in comps_used if (r.get("seller_score") or 0) >= 0.98)
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
        return {"ok": False, "error": "baseline model missing (models/baseline.json)"}
    try:
        with open(path) as _f:
            model = json.load(_f)
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
    return {
        "ok": True,
        "source": "baseline",
        "normalized_key": nk,
        "q10": round(max(0.0, q50 * 0.8), 2),
        "q50": round(q50, 2),
        "q90": round(q50 * 1.2, 2),
        "confidence": 0.5,
    }


# -------- Hybrid prediction safe (try/except wrapper) --------
@router.post("/predict/hybrid_safe_v1")
async def predict_hybrid_safe_v1(payload: dict[str, Any]) -> dict[str, Any]:
    """Same as hybrid_v1 but wrapped in try/except for resilience."""
    try:
        return await predict_hybrid_v1(payload)
    except Exception as e:
        return {"ok": False, "error": f"hybrid_safe_v1 failed: {str(e)}"}


# -------- Item NK update --------
@router.post("/items/update_nk")
async def items_update_nk(payload: dict[str, Any]) -> dict[str, Any]:
    item_id = str(payload.get("item_id") or "")
    nk = str(payload.get("normalized_key") or "")
    if not item_id or not nk:
        raise HTTPException(400, "item_id and normalized_key required")

    with db_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "update public.items set normalized_key=%s where id::text=%s returning id, normalized_key",
            (nk, item_id),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
    if not row:
        return {"ok": False, "error": "item not found"}
    return {"ok": True, "item_id": row["id"], "normalized_key": row["normalized_key"]}


# -------- NK suggestions from text --------
@router.get("/market/suggest_nk")
async def market_suggest_nk(text: str, category: str) -> dict[str, Any]:
    try:
        from services.collectors_merge.core.normalize.resolve import candidates_from_text
    except Exception as e:
        logger.warning("candidates_from_text import failed, using fallback: %s", e)
        def candidates_from_text(t, c):
            return [f"{(c or 'misc').lower()}|fallback"]

    cands = candidates_from_text(text, category)
    return {"ok": True, "candidates": cands[:10]}


# -------- Photo Fastpass v2 (clean) --------
@router.post("/ingest/fastpass_v2")
async def ingest_fastpass_v2(
    user_id: str = Form(...),
    category: str = Form(...),
    watchlist: int = Form(0),
    image: UploadFile = File(...),
    guide_recent_days: int = Form(90),
    guide_min_seller_score: float = Form(0.98),
    guide_iqr_k: float = Form(1.5),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    # 1) normalize photo
    try:
        from services.collectors_merge.core.ocr.image_io import normalize_photo
    except Exception as e:
        raise HTTPException(500, f"image normalize unavailable: {e}")
    raw = await image.read()
    photo_bytes, norm_name = normalize_photo(raw, image.filename or "upload.jpg")

    # 2) OCR best-effort
    ocr_fields: dict[str, Any] = {}
    try:
        from services.collectors_merge.core.ocr.psa import ocr_psa_bytes

        r = ocr_psa_bytes(photo_bytes, norm_name)
        if r.get("ok"):
            ocr_fields = r.get("fields", {}) or {}
    except Exception as e:
        logger.warning("fastpass_v2: OCR failed: %s", e)

    # 3) NK candidates
    try:
        from services.collectors_merge.core.normalize.resolve import candidates_from_text
    except Exception as e:
        logger.warning("fastpass_v2: candidates_from_text unavailable, using fallback: %s", e)
        def candidates_from_text(text, category):
            return [f"{(category or 'misc').lower()}|fallback"]

    hint = f"{norm_name} {ocr_fields.get('cert','')} {ocr_fields.get('grade','')}".strip()
    candidates = candidates_from_text(hint, category)
    guess = candidates[0] if candidates else f"{(category or 'misc').lower()}|fallback"

    # 4) Upsert item
    with db_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """
              insert into public.items (user_id, category, title, normalized_key, sealed, attributes_json, images)
              values (%s,%s,%s,%s,false,%s::jsonb,%s::jsonb)
              returning id, user_id, category, title, normalized_key, sealed, attributes_json
            """,
                (user_id, category, norm_name, guess, json.dumps(ocr_fields), json.dumps([{"name": norm_name}])),
            )
        except Exception as e:
            logger.warning("fastpass_v2: insert with images failed, retrying without: %s", e)
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

        if int(watchlist or 0) == 1:
            try:
                cur2 = conn.cursor()
                cur2.execute(
                    """insert into public.watchlist(user_id, normalized_key)
                                values (%s,%s) on conflict do nothing""",
                    (user_id, guess),
                )
                cur2.close()
            except Exception as e:
                logger.warning("fastpass_v2: watchlist insert failed: %s", e)
        conn.commit()
        cur.close()

    # 5) Hybrid prediction + mini price guide
    pred: dict[str, Any] = {"ok": False, "error": "hybrid skipped"}
    guide: dict[str, Any] = {"ok": False, "error": "guide skipped"}
    try:
        import httpx

        base = os.getenv("BASE_URL", "http://localhost:8080")
        headers = {}
        if authorization:
            headers["authorization"] = authorization
        async with httpx.AsyncClient(timeout=6.0) as client:
            h_body = {
                "item_id": item["id"],
                "attributes": {"grade": ocr_fields.get("grade"), "sealed": False},
            }
            h = await client.post(f"{base}/predict/hybrid_safe_v1", json=h_body, headers=headers)
            pred = h.json() if h.status_code == 200 else {"ok": False, "error": f"hybrid HTTP {h.status_code}"}

            params = {
                "normalized_key": item["normalized_key"],
                "horizon_days": max(7, int(guide_recent_days)),
                "iqr_k": float(guide_iqr_k),
            }
            g = await client.get(f"{base}/market/price_guide_v2", params=params, headers=headers)
            guide = g.json() if g.status_code == 200 else {"ok": False, "error": f"guide HTTP {g.status_code}"}
    except Exception as e:
        pred = {"ok": False, "error": f"hybrid/guide error: {e}"}

    return {
        "ok": True,
        "item": item,
        "normalized_key": guess,
        "candidates": candidates,
        "ocr_fields": (ocr_fields or None),
        "prediction": pred if isinstance(pred, dict) else {"ok": False, "error": "pred-unexpected"},
        "guide": guide if isinstance(guide, dict) else {"ok": False, "error": "guide-unexpected"},
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
