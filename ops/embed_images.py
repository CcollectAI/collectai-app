import argparse
import asyncio
import hashlib
import io
import logging
import os

import asyncpg
import numpy as np
import requests
from PIL import Image
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

PG_DSN        = os.environ.get("PG_DSN")
SUPABASE_URL  = os.environ.get("SUPABASE_URL")
SUPABASE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY")
BUCKET_NAME   = os.environ.get("VISION_BUCKET", "uploads-item-vision")
MODEL_NAME    = os.environ.get("EMBED_MODEL", "sentence-transformers/clip-ViT-B-32")

if not PG_DSN:
    raise RuntimeError("PG_DSN is not set. Export PG_DSN=postgresql://user:pass@host:5432/db?sslmode=require")


def fetch_http(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=25, allow_redirects=True,
                         headers={"User-Agent": "collectors-merge/1.0"})
        if not r.ok:
            logger.debug("[skip] HTTP %d for %s", r.status_code, url)
            return None
        ctype = r.headers.get("Content-Type", "").lower()
        if "image" not in ctype and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")):
            logger.debug("[skip] Non-image content-type '%s' for %s", ctype, url)
            return None
        if not r.content:
            logger.debug("[skip] Empty body for %s", url)
            return None
        return r.content
    except Exception as e:
        logger.debug("[skip] Exception fetching %s: %s", url, e)
        return None


def to_embedding(model: SentenceTransformer, img_bytes: bytes) -> np.ndarray | None:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        emb = model.encode([img], batch_size=1, convert_to_numpy=True, show_progress_bar=False)[0]
        return emb.astype(np.float32)
    except Exception as e:
        logger.debug("[skip] PIL/encode error: %s", e)
        return None


async def upsert_embedding(conn: asyncpg.Connection, image_id, emb: np.ndarray):
    await conn.execute(
        "insert into public.item_image_embeddings(image_id, embedding) values($1, $2) "
        "on conflict (image_id) do update set embedding = excluded.embedding",
        image_id, emb.tolist()
    )


async def fetch_storage_signed_url(path: str) -> str | None:
    if not (SUPABASE_URL and SUPABASE_KEY and BUCKET_NAME):
        return None
    sign_api = f"{SUPABASE_URL}/storage/v1/object/sign/{BUCKET_NAME}/{path.lstrip('/')}"
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    try:
        r = requests.post(sign_api, headers=h, json={"expiresIn": 600}, timeout=10)
        if r.ok:
            return f"{SUPABASE_URL}{r.json()['signedURL']}"
        logger.debug("[skip] signed-url HTTP %d: %s", r.status_code, r.text)
    except Exception as e:
        logger.debug("[skip] signed-url exception: %s", e)
    return None


async def embed_single_url(dsn: str, url: str, image_id_hex: str | None):
    import uuid
    img_id = uuid.UUID(image_id_hex) if image_id_hex else uuid.UUID(bytes=hashlib.md5(url.encode()).digest())
    logger.info("[info] embedding single url -> image_id=%s url=%s", img_id, url)
    data = fetch_http(url)
    if not data:
        logger.info("[end] fetch failed")
        return 0
    model = SentenceTransformer(MODEL_NAME)
    emb = to_embedding(model, data)
    if emb is None:
        logger.info("[end] embedding failed")
        return 0
    conn = await asyncpg.connect(dsn)
    try:
        await upsert_embedding(conn, img_id, emb)
    finally:
        await conn.close()
    logger.info("[ok] upserted 1 embedding")
    return 1


async def embed_batch(dsn: str, limit_storage: int, limit_hits: int):
    model = SentenceTransformer(MODEL_NAME)
    conn = await asyncpg.connect(dsn)
    processed = 0
    try:
        # storage-like
        rows = await conn.fetch("""
            select image_id, path_like, coalesce(created_at, now()) as created_at
            from public.v_images_needing_embeddings
            where path_like is not null and trim(path_like) <> ''
            order by created_at asc
            limit $1;
        """, limit_storage)
        logger.info("[info] storage-like candidates: %d", len(rows))
        for r in rows:
            img_id = r["image_id"]
            path   = (r["path_like"] or "").strip()
            if path.lower().startswith("http://") or path.lower().startswith("https://"):
                data = fetch_http(path)
            else:
                signed = await fetch_storage_signed_url(path)
                data = fetch_http(signed) if signed else None
            if not data:
                logger.debug("[skip] fetch failed for %s", path)
                continue
            emb = to_embedding(model, data)
            if emb is None:
                logger.debug("[skip] embed failed for %s", path)
                continue
            await upsert_embedding(conn, img_id, emb)
            processed += 1

        if processed == 0 and limit_hits > 0:
            # market_hits fallback
            hit_rows = await conn.fetch("""
                select url_sig, image_url
                from public.v_market_hit_images_todo
                where image_url is not null and trim(image_url) <> ''
                limit $1;
            """, limit_hits)
            logger.info("[info] market_hits candidates: %d", len(hit_rows))
            import uuid
            for r in hit_rows:
                url = (r["image_url"] or "").strip()
                if not url:
                    continue
                data = fetch_http(url)
                if not data:
                    logger.debug("[skip] fetch failed for %s", url)
                    continue
                emb = to_embedding(model, data)
                if emb is None:
                    logger.debug("[skip] embed failed for %s", url)
                    continue
                img_id = uuid.UUID(bytes=hashlib.md5(r["url_sig"].encode()).digest())
                await upsert_embedding(conn, img_id, emb)
                processed += 1

        logger.info("embedded images: %d", processed)
        return processed
    finally:
        await conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="embed a single image URL (bypass DB views)")
    ap.add_argument("--image-id", help="uuid to use for --url (optional)")
    ap.add_argument("--limit-storage", type=int, default=20)
    ap.add_argument("--limit-hits", type=int, default=10)
    args = ap.parse_args()

    if args.url:
        asyncio.run(embed_single_url(PG_DSN, args.url, args.image_id))
    else:
        asyncio.run(embed_batch(PG_DSN, args.limit_storage, args.limit_hits))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
