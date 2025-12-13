#!/usr/bin/env python3
import os; print("[alert-delivery] DB_DSN host =", os.getenv("DB_DSN","").split("@")[-1].split(":")[0], flush=True)
import os, asyncio, json, time
import asyncpg, httpx

DB_HOST     = os.getenv("DB_HOST",     "db.ykqrruipzmrrvjcvwfgp.supabase.co")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME",     "postgres")
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_SSL      = os.getenv("DB_SSL",      "require")  # require|disable

CLAIM_SQL   = "select * from public.rpc_alert_attempt_start()"
FINISH_SQL  = "select public.rpc_alert_attempt_finish($1,$2,$3,$4,$5)"
TARGETS_SQL = "select url, auth_header from public.rpc_alert_targets($1)"

SLEEP_NOJOB = float(os.getenv("SLEEP_NOJOB", "5"))
TIMEOUT_S   = float(os.getenv("HTTP_TIMEOUT", "8"))
RETRIES     = int(os.getenv("DELIVERY_RETRIES", "3"))

def _sslmode():
    return "require" if DB_SSL.lower() == "require" else "disable"

async def _pool():
    import asyncio, time
    delay=1
    
    dsn = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode={_sslmode()}"
    while True:
        try:
            return await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5, command_timeout=30)
        except Exception as e:
            print(f"[alert-delivery] db pool connect failed: {e}; retrying in {delay}s", flush=True)
            await asyncio.sleep(delay)
            delay=min(delay*2, 30)

async def deliver_one(client, url, payload, auth_header):
    headers = {"content-type":"application/json"}
    if auth_header:
        # e.g. "Authorization: Bearer XXX"
        k, _, v = auth_header.partition(":")
        if v:
            headers[k.strip()] = v.strip()
        else:
            headers["Authorization"] = auth_header.strip()
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, RETRIES+1):
        ts = time.time()
        try:
            r = await client.post(url, content=data, headers=headers, timeout=TIMEOUT_S)
            elapsed_ms = int((time.time()-ts)*1000)
            ok = 200 <= r.status_code < 300
            snippet = (r.text or "")[:512]
            return ok, r.status_code, snippet, elapsed_ms
        except Exception as e:
            elapsed_ms = int((time.time()-ts)*1000)
            if attempt == RETRIES:
                return False, 599, str(e)[:512], elapsed_ms
            await asyncio.sleep(min(2**attempt, 10))  # jitterless backoff

async def worker_loop():
    pool = await _pool()
    async with httpx.AsyncClient() as client:
        while True:
            try:
                async with pool.acquire() as conn:
                    job = await conn.fetchrow(CLAIM_SQL)
                if not job:
                    await asyncio.sleep(SLEEP_NOJOB)
                    continue

                job_id   = job.get("id") or job.get("job_id")
                user_id  = job.get("user_id")
                payload  = job.get("payload") or job.get("body") or {}
                if isinstance(payload, str):
                    try: payload = json.loads(payload)
                    except: payload = {"raw": payload}

                # fetch targets
                async with pool.acquire() as conn:
                    targets = await conn.fetch(TARGETS_SQL, user_id)

                if not targets:
                    # no targets -> mark as delivered=false with 204 (no targets)
                    async with pool.acquire() as conn:
                        await conn.fetchval(FINISH_SQL, job_id, False, 204, "no targets", 0)
                    continue

                # deliver to all targets; success if ANY 2xx
                any_ok = False
                worst_code = 0
                msg_snip = ""
                total_ms = 0
                for t in targets:
                    ok, code, snip, ms = await deliver_one(client, t["url"], payload, t["auth_header"])
                    any_ok = any_ok or ok
                    worst_code = max(worst_code, code or 0)
                    total_ms += ms
                    if snip: msg_snip = snip  # last snippet kept

                async with pool.acquire() as conn:
                    await conn.fetchval(FINISH_SQL, job_id, any_ok, worst_code, msg_snip, total_ms)

            except Exception as e:
                # Keep running; log to stdout for journald scraping
                print(f"[alert-delivery] error: {e}", flush=True)
                await asyncio.sleep(2)

async def main():
    print("[alert-delivery] worker online", flush=True)
    await worker_loop()

if __name__ == "__main__":
    asyncio.run(main())
