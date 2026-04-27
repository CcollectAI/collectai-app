#!/usr/bin/env bash
# preflight_app_store.sh — "am I ready to submit?" checklist.
#
# Runs every check that can fail an App Store / Play Store submission
# and prints a clear PASS/FAIL/PENDING list. Exits 0 only when nothing
# is FAIL or PENDING.
#
# Categorisation:
#   PASS    — verified ready
#   FAIL    — actively broken (must fix before submission)
#   PENDING — waiting on user action (Apple enrollment, Stripe live keys,
#             domain purchase, eBay API approval, etc.)
#
# Usage: bash scripts/preflight_app_store.sh
# No args. Run from repo root.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

# ANSI colors when stdout is a tty
if [[ -t 1 ]]; then
    GREEN=$'\e[32m'; RED=$'\e[31m'; YELLOW=$'\e[33m'; BLUE=$'\e[34m'; RESET=$'\e[0m'
else
    GREEN=""; RED=""; YELLOW=""; BLUE=""; RESET=""
fi

PASS_COUNT=0
FAIL_COUNT=0
PEND_COUNT=0

pass() { echo "  ${GREEN}PASS${RESET}  $1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo "  ${RED}FAIL${RESET}  $1"; FAIL_COUNT=$((FAIL_COUNT+1)); }
pend() { echo "  ${YELLOW}PEND${RESET}  $1"; PEND_COUNT=$((PEND_COUNT+1)); }
section() { echo; echo "${BLUE}== $1 ==${RESET}"; }

# ---------------------------------------------------------------------------
section "App identity (app.json + eas.json)"

NAME=$(python3 -c "import json; print(json.load(open('app.json'))['expo']['name'])" 2>/dev/null || echo "?")
SLUG=$(python3 -c "import json; print(json.load(open('app.json'))['expo']['slug'])" 2>/dev/null || echo "?")
VERSION=$(python3 -c "import json; print(json.load(open('app.json'))['expo']['version'])" 2>/dev/null || echo "?")
BUNDLE_IOS=$(python3 -c "import json; print(json.load(open('app.json'))['expo']['ios']['bundleIdentifier'])" 2>/dev/null || echo "?")
BUNDLE_AND=$(python3 -c "import json; print(json.load(open('app.json'))['expo']['android']['package'])" 2>/dev/null || echo "?")

if [[ "$NAME" == "Atlantis" ]]; then
    fail "app.json name is still 'Atlantis' — must change to 'CollectAI' before submission"
elif [[ "$NAME" == "CollectAI" ]]; then
    pass "app.json name = 'CollectAI'"
else
    fail "app.json name = '$NAME' (expected 'CollectAI')"
fi
[[ "$SLUG" == "collectai" ]] && pass "slug = collectai" || fail "slug = '$SLUG'"
pass "version = $VERSION"
[[ "$BUNDLE_IOS" == "com.collectai.app" ]] && pass "iOS bundleIdentifier = $BUNDLE_IOS" || fail "iOS bundleIdentifier = $BUNDLE_IOS"
[[ "$BUNDLE_AND" == "com.collectai.app" ]] && pass "Android package = $BUNDLE_AND" || fail "Android package = $BUNDLE_AND"

if grep -q "YOUR_APPLE_TEAM_ID" eas.json; then
    pend "eas.json appleTeamId = YOUR_APPLE_TEAM_ID (need Apple Developer enrollment)"
else
    pass "eas.json appleTeamId is set"
fi
if grep -q "YOUR_APP_STORE_CONNECT_APP_ID" eas.json; then
    pend "eas.json ascAppId = YOUR_APP_STORE_CONNECT_APP_ID (need App Store Connect entry)"
else
    pass "eas.json ascAppId is set"
fi

# ---------------------------------------------------------------------------
section "Backend env (EC2 .env)"

if ssh -o BatchMode=yes -o ConnectTimeout=5 collectai 'true' >/dev/null 2>&1; then
    ENV_DUMP=$(ssh collectai 'cat /opt/collectors/.env 2>/dev/null | grep -E "^(STRIPE_|EBAY_|SUPABASE_|OPENAI_|TELEGRAM_|SENTRY_|POSTHOG)" | cut -d= -f1' || echo "")

    grep -q "^STRIPE_SECRET_KEY$" <<<"$ENV_DUMP"  && pass "EC2 .env has STRIPE_SECRET_KEY" || fail "EC2 .env missing STRIPE_SECRET_KEY"

    if ssh collectai 'grep -q "^STRIPE_SECRET_KEY=sk_test_" /opt/collectors/.env' 2>/dev/null; then
        pend "STRIPE_SECRET_KEY is a TEST key — switch to live key (sk_live_*) before submission"
    elif ssh collectai 'grep -q "^STRIPE_SECRET_KEY=sk_live_" /opt/collectors/.env' 2>/dev/null; then
        pass "STRIPE_SECRET_KEY is a live key"
    fi

    grep -q "^STRIPE_WEBHOOK_SECRET$" <<<"$ENV_DUMP"  && pass "EC2 .env has STRIPE_WEBHOOK_SECRET" || pend "STRIPE_WEBHOOK_SECRET not set (needed for live billing webhooks)"
    grep -q "^EBAY_CLIENT_ID$"        <<<"$ENV_DUMP"  && pass "EBAY_CLIENT_ID set" || fail "EBAY_CLIENT_ID missing"
    grep -q "^SUPABASE_URL$"          <<<"$ENV_DUMP"  && pass "SUPABASE_URL set" || fail "SUPABASE_URL missing"
    grep -q "^OPENAI_API_KEY$"        <<<"$ENV_DUMP"  && pass "OPENAI_API_KEY set" || fail "OPENAI_API_KEY missing"
    grep -q "^TELEGRAM_BOT_TOKEN$"    <<<"$ENV_DUMP"  && pass "TELEGRAM_BOT_TOKEN set (ops alerts)" || pend "TELEGRAM_BOT_TOKEN missing"
else
    pend "Cannot SSH to collectai — env checks skipped (run `ssh collectai true` to verify connection)"
fi

# ---------------------------------------------------------------------------
section "Backend health (api.* response)"

# EC2 :8000 should NOT be externally reachable in production — UFW correctly
# blocks it. The API surface must be reached via nginx :443 (post-SSL).
# Verify the bake is healthy from inside the instance instead.
if ssh -o BatchMode=yes -o ConnectTimeout=5 collectai 'curl -sf -o /dev/null -m 3 http://localhost:8000/healthz' 2>/dev/null; then
    pass "EC2 bake healthy on internal :8000 (UFW correctly blocks external 8000 — this is intentional)"
else
    fail "EC2 bake NOT responding on internal :8000 — service down"
fi

DOMAIN_TARGET="${API_DOMAIN:-}"
if [[ -z "$DOMAIN_TARGET" ]]; then
    pend "API_DOMAIN env var unset — set it to your real domain when buying one (e.g. \`API_DOMAIN=api.yourdomain.tld bash $0\`). Domain purchase + DNS still pending."
elif dig +short "$DOMAIN_TARGET" 2>/dev/null | grep -q .; then
    if curl -sf -o /dev/null -m 5 "https://$DOMAIN_TARGET/healthz" 2>/dev/null; then
        pass "$DOMAIN_TARGET /healthz responding via HTTPS"
    else
        pend "$DOMAIN_TARGET resolves but HTTPS not yet — run scripts/setup_ssl.sh on EC2"
    fi
else
    pend "$DOMAIN_TARGET DNS not configured (need to point A record at 51.21.210.195)"
fi

# ---------------------------------------------------------------------------
section "Store assets"

if [[ -f docs/APP_REVIEW_NOTES.md ]]; then
    pass "docs/APP_REVIEW_NOTES.md exists"
    if grep -q "reviewer@collectai.app" docs/APP_REVIEW_NOTES.md; then
        pass "Reviewer demo account documented"
    else
        fail "APP_REVIEW_NOTES.md missing reviewer demo account"
    fi
else
    fail "docs/APP_REVIEW_NOTES.md missing"
fi
[[ -f docs/store-description.md ]]   && pass "docs/store-description.md exists"   || fail "docs/store-description.md missing"
[[ -f docs/APP_STORE_SUBMISSION.md ]] && pass "docs/APP_STORE_SUBMISSION.md exists" || fail "docs/APP_STORE_SUBMISSION.md missing"

if find collectai-admin/video -type f -name "*.tsx" 2>/dev/null | xargs grep -l "AppStoreScreenshot\|AppStore_Screenshot\|composition.*Screenshot" 2>/dev/null | head -1 | grep -q .; then
    pass "Remotion screenshot compositions present"
else
    pend "No Remotion App Store screenshot compositions found in collectai-admin/video/"
fi

# ---------------------------------------------------------------------------
section "Code health"

if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
    pass "Git working tree clean"
else
    fail "Git working tree dirty — commit or stash before submission build"
fi

if [[ -f scripts/check_asyncpg_interval_str_cast.py ]]; then
    if python3 scripts/check_asyncpg_interval_str_cast.py >/dev/null 2>&1; then
        pass "asyncpg interval-str-cast static check"
    else
        fail "asyncpg interval-str-cast check found issues — run \`python3 scripts/check_asyncpg_interval_str_cast.py\`"
    fi
fi

if command -v npx >/dev/null 2>&1; then
    if npx --no-install tsc --noEmit >/dev/null 2>&1; then
        pass "TypeScript: tsc --noEmit clean"
    else
        fail "TypeScript: tsc --noEmit has errors — run \`npx tsc --noEmit\`"
    fi
fi

# ---------------------------------------------------------------------------
section "Privacy + legal"
pend "Privacy policy URL must resolve at submission time"
pend "Terms of Service URL must resolve at submission time"
pend "Data Safety form completed in App Store Connect / Play Console"

# ---------------------------------------------------------------------------
echo
echo "${BLUE}=== Summary ===${RESET}"
echo "  ${GREEN}PASS${RESET}: $PASS_COUNT"
echo "  ${RED}FAIL${RESET}: $FAIL_COUNT"
echo "  ${YELLOW}PEND${RESET}: $PEND_COUNT"

if (( FAIL_COUNT > 0 )); then
    echo
    echo "${RED}Not ready: $FAIL_COUNT FAIL items must be fixed before submission.${RESET}"
    exit 1
fi
if (( PEND_COUNT > 0 )); then
    echo
    echo "${YELLOW}Pending on user action: $PEND_COUNT items.${RESET}"
    echo "Most blocking are: Apple Developer enrollment, Stripe live keys, domain purchase."
    exit 2
fi
echo
echo "${GREEN}All checks PASS — ready to build + submit.${RESET}"
exit 0
