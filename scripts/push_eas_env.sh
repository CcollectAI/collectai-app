#!/usr/bin/env bash
# Pushes EXPO_PUBLIC_* env vars from local .env.beta to EAS production environment.
# Run ONCE before the first `eas build --platform ios --profile production`.
#
# The EAS cloud build needs these embedded in the JS bundle at compile time
# (Metro reads them at build time, not runtime). Without them, the resulting
# app would launch but fail to reach Supabase / Google Sign-In / etc.
#
# Usage:
#   ./scripts/push_eas_env.sh
#
# Verify after:
#   eas env:list --environment production
#
# Reversible:
#   eas env:delete --environment production --name VAR_NAME

set -euo pipefail

if [ ! -f .env.beta ]; then
  echo "ERROR: .env.beta not found in current dir. Run from repo root."
  exit 1
fi

# Source the env file (tolerates comments and empty lines)
set -a
# shellcheck disable=SC1091
source .env.beta
set +a

# Vars the FE actually reads (from grep of src/ + app/).
VARS=(
  EXPO_PUBLIC_API_BASE_URL
  EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID
  EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID
  EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID
  EXPO_PUBLIC_SUPABASE_ANON_KEY
  EXPO_PUBLIC_SUPABASE_URL
)

# Optional vars (build will succeed without these but features will be off):
OPTIONAL=(
  EXPO_PUBLIC_API_KEY
  EXPO_PUBLIC_POSTHOG_KEY
  EXPO_PUBLIC_SENTRY_DSN
  EXPO_PUBLIC_REVENUECAT_IOS_KEY
  EXPO_PUBLIC_REVENUECAT_ANDROID_KEY
)

echo "=== Required EXPO_PUBLIC_* vars ==="
for var in "${VARS[@]}"; do
  value="${!var:-}"
  if [ -z "$value" ]; then
    echo "  MISSING in .env.beta: $var (build will fail or app will crash)"
    continue
  fi
  echo "  Pushing: $var"
  eas env:create \
    --environment production \
    --name "$var" \
    --value "$value" \
    --visibility plaintext \
    --non-interactive 2>&1 | tail -3 || echo "    (variable may already exist; use 'eas env:update' to change)"
done

echo ""
echo "=== Optional EXPO_PUBLIC_* vars (skipped if missing) ==="
for var in "${OPTIONAL[@]}"; do
  value="${!var:-}"
  if [ -z "$value" ]; then
    echo "  not set: $var"
    continue
  fi
  echo "  Pushing: $var"
  eas env:create \
    --environment production \
    --name "$var" \
    --value "$value" \
    --visibility plaintext \
    --non-interactive 2>&1 | tail -3 || echo "    (variable may already exist)"
done

echo ""
echo "=== Verifying ==="
eas env:list --environment production | head -30

echo ""
echo "Done. If anything is still missing, set it manually with:"
echo "  eas env:create --environment production --name VAR_NAME --value VALUE --visibility plaintext"
