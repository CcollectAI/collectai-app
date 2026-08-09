#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Google Play release setup — Sparrow Collect
#
#   bash scripts/setup_play_store.sh          # guided walkthrough
#   bash scripts/setup_play_store.sh --check  # just report what is done
#
# android/fastlane/Fastfile has referenced this script since the Play scaffold
# was added, but it was never written. It creates the one artefact the whole
# Android release path is blocked on:
#
#     sparrow-play-service-account.json
#
# which eas.json (submit.production.android + submit.store.android) and
# android/fastlane/Appfile both expect at the repo root.
#
# The Play Console half is browser-only — Google offers no API to enrol a
# developer account or create an app listing. This script automates the GCP
# half via gcloud and prints the exact browser steps for the rest, in order,
# so nothing is done out of sequence.
#
# NOTE: the resulting JSON is a publishing credential. It is already covered by
# .gitignore — never commit it.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEY_PATH="$REPO/sparrow-play-service-account.json"
PACKAGE="io.sparrowcollect.app"
SA_NAME="sparrow-play-publisher"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
step() { printf "\n\033[1;36m%s\033[0m\n" "$1"; }
ok()   { printf "  \033[32mOK\033[0m   %s\n" "$1"; }
todo() { printf "  \033[33mTODO\033[0m %s\n" "$1"; }

# ─── Status ────────────────────────────────────────────────────────────────
bold "Google Play setup status for $PACKAGE"
echo

if [[ -f "$KEY_PATH" ]]; then
  ok "service account key present at sparrow-play-service-account.json"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$KEY_PATH" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(f"       client_email: {d.get('client_email','?')}")
    print(f"       project_id:   {d.get('project_id','?')}")
except Exception as e:
    print(f"       WARNING: not valid JSON ({e})")
PY
  fi
else
  todo "service account key missing — this is what the steps below produce"
fi

if command -v gcloud >/dev/null 2>&1; then
  ok "gcloud CLI installed"
  GCLOUD_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
  if [[ -n "$GCLOUD_ACCOUNT" && "$GCLOUD_ACCOUNT" != "(unset)" ]]; then
    ok "gcloud authenticated as $GCLOUD_ACCOUNT"
  else
    todo "gcloud not authenticated — run: gcloud auth login"
  fi
else
  todo "gcloud CLI not installed — brew install --cask google-cloud-sdk"
fi

if [[ "${1:-}" == "--check" ]]; then
  echo
  echo "Run without --check for the full walkthrough."
  exit 0
fi

# ─── Walkthrough ───────────────────────────────────────────────────────────
cat <<'INTRO'

────────────────────────────────────────────────────────────────────────────
The steps below are ordered because each depends on the one before it.
Do them in sequence; the script pauses between each.
────────────────────────────────────────────────────────────────────────────
INTRO

pause() { echo; read -r -p "  Press Enter when this step is done (Ctrl-C to stop)… " _; }

step "1. Enrol in the Google Play Developer Program (one-time, \$25)"
cat <<EOF
  https://play.google.com/console/signup

  Use the same identity as the Apple enrolment (KvK 99596326) so the two
  store listings agree. Verification can take a few days — start here.
EOF
pause

step "2. Create the app in Play Console"
cat <<EOF
  Play Console → All apps → Create app
    App name:        Sparrow Collect
    Default language: English (United States)
    App or game:     App
    Free or paid:    Free   (Pro is an in-app subscription, not a paid app)

  Then Play Console → your app → check the package name is:
    $PACKAGE

  The package is fixed at first upload and can never be changed, so confirm it
  matches app.json (expo.android.package) before uploading anything.
EOF
pause

step "3. Link a Google Cloud project and create the publishing service account"
cat <<EOF
  Play Console → Setup → API access → "Link a Google Cloud project".

  Note the project id it links, then run (substituting it):

    gcloud config set project <PROJECT_ID>
    gcloud services enable androidpublisher.googleapis.com
    gcloud iam service-accounts create $SA_NAME \\
        --display-name="Sparrow Collect Play publisher"
    gcloud iam service-accounts keys create "$KEY_PATH" \\
        --iam-account="$SA_NAME@<PROJECT_ID>.iam.gserviceaccount.com"

  That writes sparrow-play-service-account.json to the repo root, which is
  where eas.json and android/fastlane/Appfile expect it.
EOF
pause

step "4. Grant the service account permission to publish"
cat <<EOF
  Play Console → Setup → API access → find $SA_NAME → "Manage Play Console
  permissions" → grant:

    - Release to testing tracks
    - Release apps to production          (only when you are ready to go live)
    - Manage store presence               (needed for \`fastlane metadata\`)

  Creating the key is NOT enough — without these grants every upload 403s.
EOF
pause

step "5. RevenueCat Android app (required for subscriptions to work at all)"
cat <<EOF
  Play Console → Monetize → Products → Subscriptions → create:
    sparrow_pro_monthly   EUR 4.99 / month
    sparrow_pro_yearly    EUR 39.99 / year

  These identifiers must match the iOS ones so a single RevenueCat 'default'
  offering serves both — app/subscription.tsx reads the \$rc_monthly and
  \$rc_annual packages by exactly those names.

  Then revenuecat.com → Apps → Add app → Google Play:
    package name: $PACKAGE
    upload the same service-account JSON from step 3
  RevenueCat → API keys → copy the Google (goog_...) public SDK key, then:

    eas env:create --environment production \\
      --name EXPO_PUBLIC_REVENUECAT_ANDROID_KEY \\
      --value 'goog_...' --visibility sensitive

  Without this env var src/lib/purchases.ts cannot configure the SDK on
  Android and the paywall renders its unavailable state.
EOF
pause

step "6. Firebase / FCM (required for Android push notifications)"
cat <<EOF
  https://console.firebase.google.com → add project (reuse the GCP project
  from step 3) → Add app → Android:
    package name: $PACKAGE

  Download google-services.json to the repo root, then add to app.json:

    "android": { ..., "googleServicesFile": "./google-services.json" }

  Then upload the FCM V1 credential to EAS so the Expo push service can send:

    eas credentials -p android      → Push Notifications: FCM V1 → upload key

  Skipping this does not break the build. It makes getExpoPushTokenAsync()
  throw on Android, which usePushNotifications.ts catches — so push silently
  never works.
EOF
pause

step "7. Verify, build, submit"
cat <<EOF
  node scripts/preflight_android.mjs          # must exit 0

  npm run build:android:local                 # signed .aab for Play
  # or, to smoke-test the shipping config on a device/emulator first:
  npx eas-cli build -p android --profile android-apk --local \\
      --output ./builds/sparrow-android.apk

  eas submit -p android --profile store --path ./builds/sparrow-android-local.aab
  # or: cd android && bundle exec fastlane internal aab:../builds/sparrow-android-local.aab

  Both submit configs default to track "internal" with releaseStatus "draft",
  so nothing reaches the public store until you promote it in Play Console.
EOF

echo
bold "Done. Re-run 'node scripts/preflight_android.mjs' to confirm."
