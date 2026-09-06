"""Delete synthetic accounts from PRODUCTION auth. Dry-run by default.

    set -a; . /opt/collectors/.env; set +a
    python3 server/scripts/purge_test_accounts.py            # dry run
    python3 server/scripts/purge_test_accounts.py --apply    # delete

WHY THIS EXISTS. On 2026-09-06 prod held 30 auth users and 87 items, of which
**23 accounts and ~90% of the items were our own fixtures** — named things like
`QA Test Card`, `E2E Upload Test`, `DEMO Charizard Base Set Holo`. Every
product metric computed over `items` was therefore measuring test rows, and
three successive strategic conclusions were drawn from them before anyone
checked the population. After the purge: 6 users, 17 items, and exactly ONE
external user holding ONE item.

The tell was in the item NAMES, not the counts. A row count cannot tell you
whether the rows are real.

PROTECTED is checked twice — by membership and again by an assert before the
delete loop — because deleting `apple-review@sparrowcollect.com` would break
App Store review, and the cost of that mistake is asymmetric.

⚠️ A user who owns `marketplace_listings` rows will fail with HTTP 500
"Database error deleting user" until
supabase/migrations/20260906_sync_item_for_sale_security_definer.sql is
applied. That is not this script's bug — see docs/INGEST.md. Until then, clear
the listings first and re-run.

⚠️ Accounts with a NULL `created_at` are omitted from GoTrue's admin listing
entirely, so this script cannot see them (`e2e-buyer@test.local` is one).
*Listable* and *exists* are different sets.
"""
import json, os, subprocess, sys

SU  = os.environ["SUPABASE_URL"].rstrip("/")
SVC = os.environ["SUPABASE_SERVICE_KEY"]
DRY = "--apply" not in sys.argv

# Never delete these, whatever a pattern says.
PROTECTED = {
    "apple-review@sparrowcollect.com",      # Apple review depends on it
    "simcheck@sparrowcollect.test",         # documented simulator login
}
PROTECTED_DOMAINS = ("@gmail.com", "@rinkelberg.com")

SYNTH_PREFIX = ("ci-test@", "e2e-peer-", "smoke-test@", "android-qa", "qa-signup", "qa@", "qa-")
SYNTH_DOMAIN = ("@sparrowcollect.invalid", "@example.com", "@sparrowcollect-test.dev",
                "@test.local", "@sparrowcollect.test")

def http(url, method="GET", headers=None, t=45):
    cmd = ["curl","-sS","-X",method,url,"-w","\n<<%{http_code}>>","--max-time",str(t)]
    for k,v in (headers or {}).items(): cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=t+15)
    out = r.stdout; code = 0
    if "<<" in out:
        out,_,tail = out.rpartition("\n<<"); code = int(tail.strip(">>\n") or 0)
    try: return code, (json.loads(out) if out.strip() else {})
    except Exception: return code, {"_raw": out[:200]}

H = {"apikey": SVC, "Authorization": "Bearer " + SVC}
c, d = http(f"{SU}/auth/v1/admin/users?per_page=200", headers=H)
users = d.get("users", d if isinstance(d, list) else [])

todo, keep = [], []
for u in users:
    e = (u.get("email") or "").lower()
    if e in PROTECTED or any(e.endswith(x) for x in PROTECTED_DOMAINS):
        keep.append(e); continue
    if any(e.startswith(p) for p in SYNTH_PREFIX) or any(e.endswith(x) for x in SYNTH_DOMAIN):
        todo.append((u["id"], e)); continue
    keep.append(e)

print(f"{'DRY RUN — nothing deleted' if DRY else 'APPLYING'}\n")
print(f"KEEP ({len(keep)}):")
for e in sorted(keep): print("   ", e)
print(f"\nDELETE ({len(todo)}):")
for _, e in sorted(todo, key=lambda x: x[1]): print("   ", e)

# Belt and braces: a protected address must never reach the delete loop.
assert not (set(e for _, e in todo) & PROTECTED), "PROTECTED account in delete list — aborting"

if DRY:
    print("\nRe-run with --apply to execute."); sys.exit(0)

ok = fail = 0
for uid, e in todo:
    c, r = http(f"{SU}/auth/v1/admin/users/{uid}", "DELETE", H)
    if c in (200, 204): ok += 1; print(f"  deleted  {e}")
    else: fail += 1; print(f"  FAILED   {e} -> HTTP {c} {json.dumps(r)[:120]}")
print(f"\ndeleted {ok}, failed {fail}")
