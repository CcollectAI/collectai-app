# Sparrow Collect — Production Incident Runbook

> Generated 2026-05-12. The "what to do first" reference for when something is on fire and you don't have time to think.
>
> Bookmark this. Read it once now while everything's calm so the muscle memory's there.

---

## 🚨 Triage decision tree

**Where did the failure surface?**

| Surface | Most likely cause | Jump to |
|---|---|---|
| App crash on iPhone (TestFlight or production) | Native bug, missing env var, network down | [§1 App crash](#1-app-crash-on-iphone) |
| App opens but features 404/timeout | Backend down or misconfigured | [§2 Backend down](#2-backend-down) |
| Sign-up fails | Supabase auth / RLS / email confirm broken | [§3 Auth failure](#3-auth-failure) |
| Scan times out / wrong identifications | AI provider rate limit, bake worker stuck | [§4 Scan failures](#4-scan-failures) |
| Subscription / Pro features locked when they shouldn't be | `BETA_UNLOCK_ALL` env not in build, or RC misconfig in store build | [§5 Paywall wrong state](#5-paywall-wrong-state) |
| App Store Connect rejection | Metadata / IAP / privacy issue | [§6 ASC rejection](#6-asc-rejection) |
| Slow performance on phone | Backend latency or DB pressure | [§7 Slowness](#7-slowness) |
| Sentry/PostHog flood of errors | Spike in production crashes or events | [§8 Telemetry spike](#8-telemetry-spike) |

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

# Check vision provider state
ssh collectai 'sudo journalctl -u collectai-bake --since "10 min ago" | grep -iE "openai|vision|prediction" | head'

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
