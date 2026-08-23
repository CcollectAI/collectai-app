# Sparrow Collect — Production Incident Runbook

> Generated 2026-05-12. The "what to do first" reference for when something is on fire and you don't have time to think.
>
> Bookmark this. Read it once now while everything's calm so the muscle memory's there.

---

## ⛔ Read this before you grep for anything

**Application logs do NOT go to journald.** `collectai-bake.service` sets
`StandardOutput=append:/opt/collectors/bake.log` (and the same for stderr), so:

```bash
# WRONG — returns systemd's own lines and none of the app's. Looks like silence.
ssh collectai 'sudo journalctl -u collectai-bake --since "10 min ago" | grep -i thing'

# RIGHT
ssh collectai 'grep -i thing /opt/collectors/bake.log | tail -20'
```

`journalctl` is still correct for **systemd-level** questions — did the unit
start, did a preflight fail, did it crash-loop:

```bash
ssh collectai 'sudo systemctl status collectai-bake.service'
ssh collectai 'sudo journalctl -u collectai-bake.service --since "5 min ago" --no-pager | tail -30'
```

This trap cost real time on 2026-08-07: a `logger.info` in the P2P supply hook
was greppable in `bake.log` the whole time, while `journalctl` showed nothing
and read as "the code never ran". Three separate wrong conclusions came out of
that before the unit file was checked. **An empty journal is not evidence.**

`bake.log` is ~90MB and append-only — always `tail` or `grep`, never `cat`.

---

## 🚨 Triage decision tree

**Where did the failure surface?**

| Surface | Most likely cause | Jump to |
|---|---|---|
| App crash on iPhone (TestFlight or production) | Native bug, missing env var, network down | [§1 App crash](#1-app-crash-on-iphone) |
| Screen stuck on a loading skeleton | Unbounded Supabase read, or a fetch fired before auth hydrated | [§0 Stuck skeleton](#0-screen-stuck-on-a-skeleton) |
| App opens but features 404/timeout | Backend down or misconfigured | [§2 Backend down](#2-backend-down) |
| Sign-up fails | Supabase auth / RLS / email confirm broken | [§3 Auth failure](#3-auth-failure) |
| Scan times out / wrong identifications | AI provider rate limit, bake worker stuck | [§4 Scan failures](#4-scan-failures) |
| Subscription / Pro features locked when they shouldn't be | `BETA_UNLOCK_ALL` env not in build, or RC misconfig in store build | [§5 Paywall wrong state](#5-paywall-wrong-state) |
| App Store Connect rejection | Metadata / IAP / privacy issue | [§6 ASC rejection](#6-asc-rejection) |
| Slow performance on phone | Backend latency or DB pressure | [§7 Slowness](#7-slowness) |
| Sentry/PostHog flood of errors | Spike in production crashes or events | [§8 Telemetry spike](#8-telemetry-spike) |
| A screen says it has nothing ("no results", "none available") but the data exists | **Rate limit** — a 429 rendered as an empty state | [§9 Rate limiting](#9-rate-limiting) |

---

## 0. Screen stuck on a skeleton

**Symptoms:** Home and/or Items show grey placeholder blocks indefinitely. No
error toast. Nothing obviously wrong in the backend.

**First: is it actually stuck, or looping?** Screenshot twice, 15s apart. If they
are identical it is stuck; if the error count is climbing it is retrying.

```bash
# On the simulator
xcrun simctl io <UDID> screenshot /tmp/a.png    # wait 15s
xcrun simctl io <UDID> screenshot /tmp/b.png
grep -c "NO TOKEN after refresh" /tmp/expo_ios.log   # run twice — growing = loop
```

**Rule out the backend before touching the app** — it usually is not the cause:

```bash
# endpoint latency (FE gives up at ~5s)
ssh collectai '/opt/collectors/.venv/bin/python /tmp/timing.py'
# the Items query is a DIRECT PostgREST read, not the API — test it separately
```

**Most likely causes, in order:**

| Cause | Tell | Fix |
|---|---|---|
| **Signed out / session not hydrated** | `[DIAG auth] getAuthHeaders: NO TOKEN` in the log | Sign in. A fresh install has an empty SecureStore, and the app renders a logged-in-looking Portfolio while every request goes out tokenless |
| **Unbounded Supabase read** | No log line at all, skeleton never clears | The read is missing `withTimeout` — see `docs/ui-playbook.md` "Loading states" |
| **Fetch fired during auth hydration** | `listItems timed out after 8000ms` | The screen is not gating on `!authLoading` |

**Why the logs may be empty:** `logger.info`/`warn` are stripped in release
builds. Timeouts must be logged with `logger.error` to be visible in TestFlight.

**Regression guard:** `__tests__/hooks/usePaginatedList.test.ts` pins that a
hanging fetcher cannot pin the skeleton, and that a never-opening gate still
fetches. If those are green and a screen still hangs, the screen is not using
`usePaginatedList` — check its hand-rolled loader.

---

## 1. App crash on iPhone

**Symptoms:** TestFlight crashes immediately on open, mid-flow crash, or "Sparrow Collect needs to update" loop.

### First diagnose

```bash
# Get the latest TestFlight build state from EAS
eas build:list --limit 3 --json --non-interactive | \
  python3 -c "import sys, json; [print(f'{b[\"status\"]:12} {b[\"id\"]}') for b in json.load(sys.stdin)]"
```

If status is `ERRORED` — the build itself didn't compile. Look at:
- EAS build logs (URL in the JSON above)
- Most common causes: Sentry source-map (`SENTRY_DISABLE_AUTO_UPLOAD=true` should be set), missing env var, ATS violation (HTTP URL).

### Most common causes + fixes

| Cause | Symptom | Fix |
|---|---|---|
| Missing env var | App launches → blank screen / "API connection failed" | `eas env:list --environment production` → check all 5 vars set |
| HTTP API URL (ATS block) | Network failures in console | Confirm `EXPO_PUBLIC_API_BASE_URL=https://api.sparrowcollect.com` (HTTPS) |
| Stale build | Old buildNumber on phone | Force-reinstall via TestFlight → rebuild if needed |
| Native module crash | Hard crash with stack trace from Sentry | Look in Sentry, escalate based on trace |

### iOS device-log capture (when Sentry isn't telling you enough)

iPhone → Settings → Privacy & Security → Analytics & Improvements → Analytics Data → look for `Sparrow-{date}-ips`. Email yourself.

---

## 2. Backend down

**Symptoms:** API endpoints return 5xx or timeout. App shows error toasts everywhere.

### First diagnose

```bash
# Health check
curl -s https://api.sparrowcollect.com/healthz
# Expect: {"ok":true,"db_configured":true,"db_ms":X,"db":"up"}
```

If healthz is unreachable:
```bash
# DNS check
dig api.sparrowcollect.com +short
# Expect: 51.21.210.195

# Backend up?
ssh collectai 'systemctl status collectai-bake --no-pager | head -10'
```

If healthz is reachable but `db: "down"`:
- Supabase pooler issue → check [supabase.com/dashboard/project/ykqrruipzmrrvjcvwfgp](https://supabase.com/dashboard/project/ykqrruipzmrrvjcvwfgp) → Reports → Database
- DB connection pool exhausted → restart bake: `ssh collectai 'sudo systemctl restart collectai-bake'`

### Restart the bake service (last resort)

```bash
ssh collectai 'sudo systemctl restart collectai-bake'
# Wait 60 seconds, then verify:
curl -s https://api.sparrowcollect.com/healthz
```

Bake takes ~5 min to fully warm up (preflight + worker registration). The API endpoint comes up first; workers take longer.

### Cert expiry (api.sparrowcollect.com)

```bash
echo | openssl s_client -servername api.sparrowcollect.com -connect api.sparrowcollect.com:443 2>/dev/null | openssl x509 -noout -dates
# notBefore / notAfter — alert if notAfter is <30 days away
```

Renew with: `ssh collectai 'sudo certbot renew --nginx'`

---

## 3. Auth failure

**Symptoms:** Sign-up returns error. Confirmation email never arrives. Login throws.

### First diagnose

1. Check Supabase logs: [dashboard → Logs → Auth](https://supabase.com/dashboard/project/ykqrruipzmrrvjcvwfgp/logs/explorer)
2. Test with a fresh `+alias` email (Gmail aliases bypass dedup): `slendebroekmerle+sparrowdebug@gmail.com`

### Most common causes

| Cause | Fix |
|---|---|
| Email rate limit | Supabase free tier limits emails. Check Auth → Rate limits in dashboard. |
| Wrong Site URL | Auth → URL Configuration → must be `https://sparrowcollect.com` |
| Redirect URL missing | Auth → URL Configuration → allowlist is `sparrow://**, https://sparrowcollect.com/**, collectai://**`. Signup-confirm + password-reset links redirect to `https://sparrowcollect.com/auth/confirm` (an https Universal Link — a raw `sparrow://` redirect makes Safari show "address invalid"). |
| "Address is invalid" after tapping confirm | The confirm link is redirecting to `sparrow://` instead of `https://sparrowcollect.com/auth/confirm`. Ensure the build uses the https `emailRedirectTo` and that `web/auth/confirm` is deployed (see `AUTH_AND_WEB_DEPLOY.md`). |
| Apple/Google not configured | Login is **email-only** (`SOCIAL_LOGIN_ENABLED=false` in `src/config/featureFlags.ts`). Don't enable the Supabase providers (or show the buttons) without configuring Apple Services-ID/key + Google OAuth client first — broken-button + guideline 4.8 rejection risk. |
| RLS blocking sign-up | Database → Policies → ensure `auth.users` insertion isn't blocked |

---

## 4. Scan failures

**Symptoms:** Quick Scan spins forever, returns no identification, or returns wrong results.

### First diagnose

```bash
# Probe an authenticated scan endpoint (you need a bearer token first)
curl -s https://api.sparrowcollect.com/openapi.json | python3 -c "import sys, json; print([p for p in json.load(sys.stdin)['paths'] if 'scan' in p.lower() or 'predict' in p.lower()])"

# Check vision provider state — grep the LOG FILE, not journald (see below)
ssh collectai 'grep -iE "openai|vision|prediction" /opt/collectors/bake.log | tail -20'

# Check rate-limit / quota
ssh collectai 'grep -E "FIRECRAWL_ENABLED|SCRAPEDO_ENABLED|OPENAI_API_KEY" /opt/collectors/.env | head'
```

### Most common causes

| Cause | Symptom | Fix |
|---|---|---|
| OpenAI rate limit | All scans fail simultaneously | Wait, or scale up tier in OpenAI dashboard |
| Firecrawl/Scrape.do exhausted | Some scans fail, fallback paths take long | Check kill-switches in `/opt/collectors/.env` — both flagged off as of 2026-04-21 |
| Vision reclassifier loaded broken model | All identifications return same category | `ssh collectai 'ls -la /opt/collectors/server/artifacts/_vision_reclassifier/active/'` — rollback to last working pickle |
| Bake worker stuck | Scans complete but values are stale | Check `worker_runs` table for errors |

---

## 5. Paywall wrong state

**Symptoms:** During beta, paywalls show plan cards instead of "You're in the Sparrow beta" panel. OR in production, Pro features are unlocked for free users.

### Diagnose

```bash
# What does the build think it should do?
eas env:list --environment production | grep BETA_UNLOCK_ALL
# Expect: EXPO_PUBLIC_BETA_UNLOCK_ALL=true (beta) or =false (production)

# Which build profile produced the installed binary?
# Check the build's eas.json profile in the build details page
eas build:list --limit 1 --json --non-interactive | grep -i profile
```

### Fixes

| Scenario | Fix |
|---|---|
| Beta install shows paywall | `EXPO_PUBLIC_BETA_UNLOCK_ALL` wasn't in EAS env when build ran → re-push + rebuild |
| Production install unlocks Pro for everyone | `EXPO_PUBLIC_BETA_UNLOCK_ALL=true` leaked into store build → run `eas build -p ios --profile store` (not `production`) |
| RC offerings not loading in store build | RC dashboard not configured or `EXPO_PUBLIC_REVENUECAT_IOS_KEY` missing |

---

## 6. ASC rejection

**Symptoms:** App Store Connect emails you "Your app's been rejected" or "Your IAP submission failed."

### Common rejection reasons + fixes

| Rejection reason | Where to fix |
|---|---|
| App name >30 chars | `docs/app-store-aso.md` line 13 (currently "Sparrow Collect", 15 chars — should be fine) |
| Privacy URL doesn't load | `vercel --prod` from `web/` — and verify `https://sparrowcollect.com/privacy` returns 200 |
| Support URL doesn't load | Same as above (`/support`) |
| Demo account doesn't work | Re-test `apple-review@sparrowcollect.com` login on a fresh TestFlight install |
| IAP screenshot missing | Upload `~/Desktop/sparrow_paywall_1290x2796.png` |
| Privacy nutrition incomplete | `docs/app-store-aso.md` lines 620-672 — paste row-by-row |
| Bundle ID mismatch | Native iOS Info.plist + app.json + Apple Developer all must agree on `io.sparrowcollect.app` |
| HTTP networking detected (ATS) | `EXPO_PUBLIC_API_BASE_URL` must be HTTPS |
| "Build invalid binary" | Re-build with `--auto-submit` — buildNumber will auto-increment |
| IAP can't be tested | Reviewer notes need clear sandbox-tester instructions (see `docs/app-store-aso.md` line 707-727) |
| "Apps with subscriptions need …" | Add the auto-renewal disclosure (already in code: `app/subscription.tsx` legal copy) |

### How to respond to a rejection

1. Click the rejection in ASC → read the reviewer's specific reason
2. Fix the issue (most are config, not code)
3. Reply IN ASC, not via email — Apple's review queue requires their thread
4. Re-submit (no new build needed for metadata fixes; new build for code fixes)

### Pre-submission verification

Run BEFORE pasting metadata into ASC. Catches length-limit violations
that would cause an immediate auto-rejection:

```bash
node scripts/check-asc-listing.mjs
# Validates docs/app-store-aso.md against Apple + Play caps.
# Exit 0 if all good, 1 if any field is over-limit or missing.
```

Bundle size sanity check (Apple warns at 100 MB, WiFi-only-install at 200 MB):

```bash
node scripts/analyze-bundle.mjs --cached
# Or omit --cached to do a fresh `expo export` first.
```

---

## 7. Slowness

**Symptoms:** App is slow but not broken. Spinners run >5s. Scrolls stutter.

### Diagnose

```bash
# Backend latency
curl -s -o /dev/null -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" https://api.sparrowcollect.com/healthz

# DB query time
ssh collectai 'set -a; source /opt/collectors/.env; set +a; psql "$DB_DSN_DIRECT" -c "EXPLAIN ANALYZE SELECT 1"'

# Worker queue depth
ssh collectai 'set -a; source /opt/collectors/.env; set +a; psql "$DB_DSN_DIRECT" -c "SELECT worker_name, COUNT(*) AS in_progress FROM worker_runs WHERE finished_at IS NULL GROUP BY worker_name;"'
```

### Common slowness causes

- **Cold start after deploy** — first 5 minutes of any restart, expect slowness. Wait.
- **Bake worker overload** — t3.medium is the EC2 instance; if CPU > 80% sustained, throttle or upgrade.
- **DB IO throttled** — Supabase Pro instance has burst credits. Sustained writes drain them. Check Supabase → Reports → Database → IO Wait.
- **Single-region latency** — backend is `eu-north-1`. Users in US-West will see 200-300ms RTT to backend. Move to multi-region or accept.

---

## 8. Telemetry spike

**Symptoms:** Sentry sends you a flood of errors. PostHog shows a weird event spike.

### Triage

1. **Group by error name** in Sentry — is it ONE bug hitting many users, or many bugs? One-bug-many-users = production regression; revert or roll forward fast.
2. **Time-bound the spike** — if it started exactly when you shipped a build, that build is the cause. Reinstate the previous TestFlight build via ASC → TestFlight → Builds → drop the current one from external testing.
3. **Common spike patterns**:
   - Auth provider error → Supabase outage / rate limit
   - Network timeout flood → backend slow or down
   - Image load 4xx → S3 or imageUri host issue
   - Single function throwing → see the file:line in the trace, fix and rebuild

---

## 9. Rate limiting

**Symptoms:** features intermittently empty or failing ACROSS the app, with no
error and nothing wrong in the data. A card says "No marketplaces available", a
list says "no results", Pro entitlements read wrong — each on a screen whose
query, run by hand, returns rows.

**This is the one to check FIRST when a screen makes a confident negative claim.**
Every layer under a 429 is healthy and will survive any amount of inspection.

```bash
# How many rejections, and on which paths?
ssh collectai 'grep -c "Rate limit exceeded for" /opt/collectors/bake.log'
ssh collectai 'grep "\"status\": 429" /opt/collectors/bake.log | tail -400 \
  | sed -E "s/.*\"path\": \"([^\"]+)\".*/\1/" | sort | uniq -c | sort -rn | head -20'

# The device's OWN request, with its status — search by the query you can see on screen
ssh collectai 'grep "affiliate-links" /opt/collectors/bake.log | tail -15'

# Is the endpoint itself healthy? Ask it from the box, bypassing the client.
ssh collectai 'curl -s -m 20 -o /tmp/x.json -w "HTTP %{http_code}\n" \
  -H "Host: api.sparrowcollect.com" "http://127.0.0.1:8000/<path>?<params>"; head -c 400 /tmp/x.json'
```

**Two limiters, and they are easy to confuse:**

| limiter | scope | where |
|---|---|---|
| `rate_limit_middleware` | **GLOBAL per-IP, EVERY path, one bucket** | `rate_limit.py:~67`, logs `Rate limit exceeded for <ip> on <path>` |
| `per_user_rate_limit` / `per_ip_rate_limit` | one endpoint group, named `scope` | `Depends(...)`, logs `Per-user rate limit exceeded: user=… scope=…` |

**The log line tells you which fired** — match the message format, not the path.
On 2026-08-23 the affiliate endpoint's own 100/min scoped limit never fired; the
global one did, spent on unrelated screens.

### Fix

```bash
# Current value
ssh collectai 'grep "^RATE_LIMIT" /opt/collectors/.env'

# Raise it (back up first), then restart
ssh collectai 'sudo cp /opt/collectors/.env /opt/collectors/.env.bak.$(date +%Y%m%d%H%M%S) \
  && sudo sed -i "s/^RATE_LIMIT_RPM=.*/RATE_LIMIT_RPM=600/" /opt/collectors/.env'
```

⚠️ **Raising the DEFAULT in `config.py` fixes nothing while `.env` sets the
variable.** `RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "600"))` —
the literal is the fallback, and `/opt/collectors/.env` carried an explicit
`RATE_LIMIT_RPM=60`. Deploying the new default, restarting, and confirming the
new source line on the box would all have succeeded while the live limit stayed
at 60. **The `.env` is the value; the code literal is only what happens when the
`.env` is silent.** True of every setting read through `os.getenv` with a
default — check the `.env` before believing a config change shipped.

⚠️ **Run the nine preflight stages BEFORE restarting.** They are `ExecStartPre`
on the unit, so any one failing leaves the service DOWN, and a stale schema lock
only bites on the next restart — prod once sat ~1h unable to come back up for
exactly that reason.

```bash
ssh collectai 'cd /opt/collectors && set -a; . ./.env >/dev/null 2>&1; set +a
for s in preflight_deps preflight_env preflight_worker_imports schema_drift_check \
         preflight_rls_check preflight_models preflight_router_drift \
         preflight_schema_lock preflight_rpc_lock; do
  printf "%-28s " "$s"
  /opt/collectors/.venv/bin/python /opt/collectors/scripts/$s.py >/dev/null 2>&1 \
    && echo PASS || echo FAIL
done'

# Only when all nine PASS:
ssh collectai 'sudo systemctl restart collectai-bake'
sleep 60 && curl -s https://api.sparrowcollect.com/healthz
```

### Sizing it

Measure, do not guess. One member browsing normally peaked at **~55 req/min**
against a limit of 60, so the app sat permanently on the edge:

```bash
ssh collectai 'grep "<client-ip>" /opt/collectors/bake.log \
  | grep -oE "^[0-9-]+ [0-9]{2}:[0-9]{2}" | sort | uniq -c | sort -rn | head'
```

The bucket is **per IP, not per device or per user**, so everyone behind one NAT
shares it. Size it for the busiest screen times the number of people plausibly
on one address, and rely on the scoped per-endpoint limiters for actual abuse
protection — the global middleware is a blunt DoS guard, not the thing keeping
expensive routes safe.

---

## Reference: critical credentials index

If you need to log into something while you're triaging, the path is:

| What | Where |
|---|---|
| EAS dashboard | https://expo.dev/accounts/collectai |
| App Store Connect | https://appstoreconnect.apple.com/apps/6767359453 |
| Supabase dashboard | https://supabase.com/dashboard/project/ykqrruipzmrrvjcvwfgp |
| RevenueCat | https://app.revenuecat.com (Sparrow project) |
| Vercel | https://vercel.com/collectais-projects/sparrowcollect |
| Apple Developer Portal | https://developer.apple.com/account |
| EC2 SSH | `ssh collectai` (key at `~/.ssh/collectai-ec2`) |
| EC2 .env | `/opt/collectors/.env` (sensitive) |

---

## When in doubt

1. **Don't `git push --force`.** Memory: never destructive without explicit request.
2. **Don't `pg_terminate_backend` on prod queries.** Memory: long-running ≠ stuck.
3. **Don't `git reset --hard`.** Stash → branch → investigate first.
4. **Take a screenshot** of the issue before you start fixing — half the time the fix breaks something else and you need the before-state.
5. **If you've been at it >30 min and not making progress** — pause, write down what you've tried, get fresh eyes (text me / Slack the team if there's one).

Most production incidents resolve themselves within 15 minutes if you don't make them worse first.
