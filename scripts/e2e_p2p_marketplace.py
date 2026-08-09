"""E2E for the member marketplace screen: real JWT -> real HTTP -> real DB.

Every request goes through the actual auth dependency and the actual router on a
staged uvicorn (port 8009), exactly as the app calls it. Asserts the RESPONSE
BODY, not just the status — a 200 with the wrong rows is the failure mode that
matters here.

Fixtures are prefixed and deleted in a finally block, with the residual count
asserted at the end.
"""
import json, os, time, urllib.request, urllib.error, uuid, asyncio, re
import jwt, asyncpg

# Defaults to the live API. Point it at a staged instance with
#   E2E_BASE=http://127.0.0.1:8009 python3 scripts/e2e_p2p_marketplace.py
# Run it FROM EC2 — it needs /opt/collectors/.env for the JWT secret and DSN.
BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8000")
PREFIX = "e2e-mkt-"

def env(k):
    for line in open("/opt/collectors/.env"):
        m = re.match(r"\s*" + k + r"\s*=\s*(.+)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("missing " + k)

DSN = env("DB_DSN_DIRECT")
SECRET = env("SUPABASE_JWT_SECRET")
ISSUER = env("SUPABASE_JWT_ISSUER")

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("  %s %-46s %s" % ("OK " if ok else "BAD", name, detail))

def token_for(uid):
    now = int(time.time())
    return jwt.encode({"sub": uid, "aud": "authenticated", "role": "authenticated",
                       "iat": now, "exp": now + 3600, "iss": ISSUER},
                      SECRET, algorithm="HS256")

def hit(path, tok, timeout=25):
    req = urllib.request.Request(BASE + path, method="GET", headers={
        "Accept": "application/json", "Authorization": "Bearer " + tok})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return 0, "%s: %s" % (type(e).__name__, e)

def titles(payload):
    return [l["title"].replace(PREFIX, "") for l in payload.get("listings", [])
            if l.get("title", "").startswith(PREFIX)]

FIXTURES = [
    # title,               price, currency, category, status
    ("Charizard Holo",       50, "EUR", "pokemon", "active"),
    ("Charizard Reverse",   120, "EUR", "pokemon", "active"),
    ("Blastoise",          8000, "JPY", "pokemon", "active"),   # ~48.80 EUR
    ("Millennium Falcon",   200, "EUR", "lego",    "active"),
    ("100% Complete Set",    30, "EUR", "lego",    "active"),
    ("Old Sold Thing",       10, "EUR", "comics",  "sold"),
]

async def main():
    conn = await asyncpg.connect(DSN)
    try:
        owner = await conn.fetchrow(
            "SELECT i.user_id, i.id AS item_id FROM public.items i LIMIT 1")
        uid = str(owner["user_id"])
        tok = token_for(uid)
        other = await conn.fetchval(
            "SELECT id FROM auth.users WHERE id <> $1::uuid LIMIT 1", uid)
        other_tok = token_for(str(other)) if other else None

        # ── auth must actually be enforced ────────────────────────────────
        st, _ = hit("/p2p/listings", "garbage.token.here")
        check("rejects a bad token", st == 401, "status=%s" % st)
        req = urllib.request.Request(BASE + "/p2p/listings")
        try:
            urllib.request.urlopen(req, timeout=15)
            st = 200
        except urllib.error.HTTPError as e:
            st = e.code
        check("rejects no token at all", st in (401, 403), "status=%s" % st)

        # ── seed ──────────────────────────────────────────────────────────
        await conn.execute("DELETE FROM public.marketplace_listings WHERE listing_title LIKE $1", PREFIX + "%")
        for t, price, cur, cat, status in FIXTURES:
            await conn.execute(
                """INSERT INTO public.marketplace_listings
                     (id,user_id,item_id,marketplace_id,listing_title,price,currency,
                      category,status,format,created_at)
                   VALUES ($1,$2,$3,'sparrow',$4,$5,$6,$7,$8,'fixed_price',now())""",
                uuid.uuid4(), owner["user_id"], owner["item_id"],
                PREFIX + t, price, cur, cat, status)

        # ── the screen's first call ────────────────────────────────────────
        st, body = hit("/p2p/listings?sort=newest&limit=24&offset=0", tok)
        got = sorted(titles(body))
        check("200 on the screen's initial load", st == 200, "status=%s" % st)
        check("shows the 5 ACTIVE listings, not the sold one",
              got == sorted(["Charizard Holo", "Charizard Reverse", "Blastoise",
                             "Millennium Falcon", "100% Complete Set"]), str(got))

        # response shape the FE reads
        row = next((l for l in body.get("listings", [])
                    if l.get("title", "").startswith(PREFIX)), None)
        needed = ["id", "title", "price", "currency", "watchers", "seller_name",
                  "is_mine", "status", "created_at", "image_url", "image_is_catalog",
                  "condition_label", "category"]
        missing = [k for k in needed if row is None or k not in row]
        check("payload carries every field the tile renders", not missing,
              "missing=%s" % missing)
        check("watchers is an int (tile does watchers > 0)",
              isinstance(row.get("watchers"), int), "type=%s" % type(row.get("watchers")).__name__)

        # ── facets (fix 6) ────────────────────────────────────────────────
        st, fbody = hit("/p2p/facets/categories", tok)
        fac = {f["category"]: f["count"] for f in fbody.get("facets", [])}
        check("facets endpoint returns 200", st == 200, "status=%s" % st)
        check("facet counts are right (pokemon 3, lego 2)",
              fac.get("pokemon") == 3 and fac.get("lego") == 2,
              "pokemon=%s lego=%s" % (fac.get("pokemon"), fac.get("lego")))
        check("facets EXCLUDE a sold-only category", "comics" not in fac,
              "comics=%s" % fac.get("comics"))

        # ── multi-category (fix 1) ────────────────────────────────────────
        st, b = hit("/p2p/listings?category=pokemon", tok)
        check("single category filters", sorted(titles(b)) ==
              sorted(["Charizard Holo", "Charizard Reverse", "Blastoise"]), str(sorted(titles(b))))
        st, b = hit("/p2p/listings?category=pokemon&category=lego", tok)
        check("TWO categories are OR'd, not overwritten", len(titles(b)) == 5,
              "n=%d %s" % (len(titles(b)), sorted(titles(b))))
        st, b = hit("/p2p/listings?category=lego", tok)
        check("other category returns only its own", sorted(titles(b)) ==
              sorted(["Millennium Falcon", "100% Complete Set"]), str(sorted(titles(b))))

        # ── search (needed for paging to be honest) ───────────────────────
        st, b = hit("/p2p/listings?q=chariz", tok)
        check("search matches a substring, case-insensitively",
              sorted(titles(b)) == sorted(["Charizard Holo", "Charizard Reverse"]), str(sorted(titles(b))))
        st, b = hit("/p2p/listings?q=CHARIZ", tok)
        check("search is case-insensitive on input", len(titles(b)) == 2, "n=%d" % len(titles(b)))
        st, b = hit("/p2p/listings?q=%25", tok)   # %25 == '%'
        check("'%' is a LITERAL, not a wildcard", titles(b) == ["100% Complete Set"], str(titles(b)))
        st, b = hit("/p2p/listings?q=Ch_riz", tok)
        check("'_' is a LITERAL, not any-char", titles(b) == [], str(titles(b)))
        st, b = hit("/p2p/listings?q=chariz&category=lego", tok)
        check("search AND category intersect", titles(b) == [], str(titles(b)))

        # ── price in mixed currencies (earlier fix, still holds over HTTP) ─
        # A EUR cap that the JPY 8000 card can only satisfy once converted.
        #
        # Deliberately NOT a tight window around its exact converted value: the
        # JPY rate is 0.005489 when the live ECB fetch has landed and 0.0061 from
        # the config fallback, so ¥8000 is anywhere in 43.9–48.8 EUR depending on
        # process state. A tight window makes this test fail on a correct server
        # (it did, on the first live run). 100 EUR holds for any rate below
        # 0.0125, while raw 8000 is excluded either way — so it still fails
        # loudly if the conversion stops happening.
        expect_under_100 = sorted(["100% Complete Set", "Blastoise", "Charizard Holo"])
        st, b = hit("/p2p/listings?price_max=100&price_currency=EUR", tok)
        check("under EUR 100 includes the JPY card (raw 8000 would not)",
              sorted(titles(b)) == expect_under_100, str(sorted(titles(b))))
        # The same cap expressed in JPY: 16000 JPY is ~88-98 EUR at either rate.
        st, b = hit("/p2p/listings?price_max=16000&price_currency=JPY", tok)
        check("the same cap expressed in JPY behaves identically",
              sorted(titles(b)) == expect_under_100, str(sorted(titles(b))))
        # Bounds are INCLUSIVE. Asserted on a EUR row priced exactly at the cap so
        # the check does not depend on the JPY rate: "max 50" must keep the 50.
        st, b = hit("/p2p/listings?price_max=50&price_currency=EUR", tok)
        check("an inclusive cap keeps the row priced exactly at it",
              "Charizard Holo" in titles(b), str(sorted(titles(b))))
        st, b = hit("/p2p/listings?price_min=50&price_max=50&price_currency=EUR", tok)
        check("min == max == 50 returns exactly that row",
              titles(b) == ["Charizard Holo"], str(titles(b)))
        # Ordering: 30, ~44-49 (JPY), 50, 120, 200. The JPY row lands SECOND at
        # either possible rate, whereas raw ordering puts it LAST at 8000 — so
        # this pins the whole sequence and is rate-independent.
        st, b = hit("/p2p/listings?sort=price_asc", tok)
        check("price_asc orders by EUR value across currencies",
              titles(b) == ["100% Complete Set", "Blastoise", "Charizard Holo",
                            "Charizard Reverse", "Millennium Falcon"], str(titles(b)))
        st, b = hit("/p2p/listings?sort=price_desc", tok)
        check("price_desc is the exact reverse",
              titles(b) == ["Millennium Falcon", "Charizard Reverse", "Charizard Holo",
                            "Blastoise", "100% Complete Set"], str(titles(b)))

        # ── paging (fix 4) ────────────────────────────────────────────────
        seen, pages = [], []
        for off in (0, 2, 4, 6):
            st, b = hit("/p2p/listings?sort=price_asc&limit=2&offset=%d" % off, tok)
            pages.append(titles(b))
            seen += titles(b)
        check("pages do not overlap", len(seen) == len(set(seen)), str(pages))
        check("pages cover every row", sorted(seen) == sorted(
            ["Charizard Holo", "Charizard Reverse", "Blastoise",
             "Millennium Falcon", "100% Complete Set"]), str(sorted(seen)))
        check("page past the end is empty (hasMore -> false)", pages[-1] == [], str(pages[-1]))

        # ── validation ────────────────────────────────────────────────────
        for qs, why in [("?sort=name_asc", "a sort the API cannot do"),
                        ("?price_min=-1", "a negative bound"),
                        ("?price_currency=eur", "a lowercase currency"),
                        ("?category=" + "x" * 65, "an overlong category")]:
            st, _ = hit("/p2p/listings" + qs, tok)
            check("rejects %s" % why, st in (400, 422), "status=%s" % st)

        # ── privacy: another member must not see these as THEIRS ──────────
        if other_tok:
            st, b = hit("/p2p/listings?mine=true", other_tok)
            check("mine=true for a different user excludes our fixtures",
                  titles(b) == [], str(titles(b)))
            st, b = hit("/p2p/listings", other_tok)
            mine_flags = [l["is_mine"] for l in b.get("listings", [])
                          if l.get("title", "").startswith(PREFIX)]
            check("is_mine is FALSE for the other member",
                  mine_flags and not any(mine_flags), str(mine_flags))

        st, b = hit("/p2p/listings?mine=true", tok)
        check("mine=true for the owner INCLUDES the sold one",
              "Old Sold Thing" in titles(b), str(sorted(titles(b))))
    finally:
        await conn.execute("DELETE FROM public.marketplace_listings WHERE listing_title LIKE $1", PREFIX + "%")
        left = await conn.fetchval(
            "SELECT count(*) FROM public.marketplace_listings WHERE marketplace_id='sparrow'")
        print("  sparrow rows after cleanup:", left)
        if left != 0:
            check("cleanup left no rows", False, "left=%d" % left)
        await conn.close()

    bad = [n for n, ok, _ in results if not ok]
    print("\n%d/%d checks passed" % (len(results) - len(bad), len(results)))
    print("RESULT:", "FAIL -> " + str(bad) if bad else "PASS")

asyncio.run(main())
