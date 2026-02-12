import asyncio
import gzip
import json
import logging
import os
from datetime import datetime, timezone

import asyncpg
import boto3

logger = logging.getLogger(__name__)

BUCKET = os.environ["SPOOL_S3_BUCKET"]
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-north-1")
MAN_PREFIX = os.environ.get("SPOOL_MANIFEST_PREFIX", "spool/_manifests/")
DB_URL = os.environ.get("DATABASE_URL", "")


async def insert_rows(pool, rows):
    q = "insert into public.agent_ingest (source, kind, payload) values ($1,$2,$3)"
    async with pool.acquire() as con:
        async with con.transaction():
            await con.executemany(q, rows)


def list_latest_manifest():
    s3 = boto3.client("s3", region_name=REGION)
    # list manifests for today first, fallback to all
    prefixes = [datetime.now(timezone.utc).strftime(MAN_PREFIX + "%Y/%m/%d/"), MAN_PREFIX]
    for pref in prefixes:
        resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=pref)
        keys = [o["Key"] for o in resp.get("Contents", []) if o["Key"].endswith(".json")]
        if keys:
            keys.sort()
            return s3, keys[-1]
    raise SystemExit("No manifests found.")


def stream_jsonl_from_s3(s3, key):
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    body = obj["Body"].read()
    if key.endswith(".gz"):
        body = gzip.decompress(body)
    for line in body.splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


async def main():
    if not DB_URL:
        raise SystemExit("DATABASE_URL not set.")
    s3, man_key = list_latest_manifest()
    manifest = json.loads(s3.get_object(Bucket=BUCKET, Key=man_key)["Body"].read())
    # Expect {"files":[{"key": ".../agent_ingest_*.jsonl", ...}, ...]}
    file_keys = [f["key"] for f in manifest.get("files", []) if f["key"].endswith(".jsonl")]
    if not file_keys:
        logger.info("No files listed in manifest.")
        return
    logger.info("Draining %d files from manifest: s3://%s/%s", len(file_keys), BUCKET, man_key)

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)
    try:
        for fk in file_keys:
            logger.info("-> %s", fk)
            rows = []
            for rec in stream_jsonl_from_s3(s3, fk):
                src = rec.get("source", "unknown")
                kind = rec.get("kind", "unknown")
                data = rec.get("data", rec)
                rows.append((src, kind, json.dumps(data)))
                if len(rows) >= 1000:
                    await insert_rows(pool, rows)
                    rows.clear()
            if rows:
                await insert_rows(pool, rows)
    finally:
        await pool.close()
    logger.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
