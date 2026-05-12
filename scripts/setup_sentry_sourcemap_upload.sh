#!/usr/bin/env bash
# Sentry source-map upload setup for EAS production builds.
#
# Sentry catches runtime crashes from the iOS/Android app. By default,
# the stack traces are minified (e.g. "TypeError at l._A:1234") which is
# useless for debugging. Uploading source maps at build time lets Sentry
# symbolicate them back to "TypeError at handlePurchase
# (src/lib/purchases.ts:48)".
#
# This script flips the EAS env from "disabled" to "enabled" by pushing
# the three secrets Sentry needs. After this runs, `eas build` will
# upload source maps to Sentry automatically as part of every release.
#
# Pre-launch we shipped with SENTRY_DISABLE_AUTO_UPLOAD=true because the
# build was erroring on missing SENTRY_ORG. This script is the proper
# fix — call it once when you're ready, after you've created a Sentry
# project + auth token.
#
# Usage:
#   ./scripts/setup_sentry_sourcemap_upload.sh
#
# Pre-reqs (do these in Sentry dashboard first):
#   1. Sign up / log in at https://sentry.io
#   2. Create a new project: Platform = React Native, Name = "sparrow-collect"
#   3. Note your Org slug (top-left of Sentry URL: sentry.io/organizations/<ORG>/)
#   4. Note the Project slug (the project you just created)
#   5. Settings → Account → Auth Tokens → Create New Token →
#      scopes: project:read, project:releases, project:write,
#      org:read. Copy the token (shown once).
#
# Reversible:
#   eas env:delete --environment production --variable-name SENTRY_ORG
#   eas env:delete --environment production --variable-name SENTRY_PROJECT
#   eas env:delete --environment production --variable-name SENTRY_AUTH_TOKEN
#   eas env:update --environment production --variable-name SENTRY_DISABLE_AUTO_UPLOAD --value true

set -euo pipefail

cd "$(dirname "$0")/.."

echo "Sparrow Collect — Sentry source-map upload setup"
echo "================================================"
echo
echo "Make sure you have these three values from sentry.io ready:"
echo "  - Organization slug (e.g. 'sparrow-collect-org')"
echo "  - Project slug (e.g. 'sparrow-collect')"
echo "  - Auth token (sntrys_...)"
echo

read -rp "Sentry organization slug: " SENTRY_ORG
read -rp "Sentry project slug: " SENTRY_PROJECT
read -srp "Sentry auth token (input hidden): " SENTRY_AUTH_TOKEN
echo

if [ -z "$SENTRY_ORG" ] || [ -z "$SENTRY_PROJECT" ] || [ -z "$SENTRY_AUTH_TOKEN" ]; then
  echo "ERROR: all three values required. Aborting."
  exit 1
fi

echo
echo "Pushing to EAS production environment..."

eas env:create --environment production --variable-name SENTRY_ORG \
  --value "$SENTRY_ORG" --visibility plaintext --non-interactive 2>/dev/null \
  || eas env:update --environment production --variable-name SENTRY_ORG \
       --value "$SENTRY_ORG" --non-interactive

eas env:create --environment production --variable-name SENTRY_PROJECT \
  --value "$SENTRY_PROJECT" --visibility plaintext --non-interactive 2>/dev/null \
  || eas env:update --environment production --variable-name SENTRY_PROJECT \
       --value "$SENTRY_PROJECT" --non-interactive

eas env:create --environment production --variable-name SENTRY_AUTH_TOKEN \
  --value "$SENTRY_AUTH_TOKEN" --visibility sensitive --non-interactive 2>/dev/null \
  || eas env:update --environment production --variable-name SENTRY_AUTH_TOKEN \
       --value "$SENTRY_AUTH_TOKEN" --non-interactive

# Remove the bypass flag — source maps will now upload on every build.
eas env:delete --environment production --variable-name SENTRY_DISABLE_AUTO_UPLOAD \
  --non-interactive 2>/dev/null || true

# NOTE — we deliberately do NOT write ios/sentry.properties here anymore.
# eas-build-post-install.sh (in the repo root) generates that file at
# build time on EAS servers from the same env vars. That keeps secrets
# out of your local working tree and avoids drift between dev + CI.
#
# Make sure sentry.properties is gitignored so any stray local file (e.g.
# from a previous run of this script) doesn't end up committed.
if ! grep -q "^ios/sentry.properties$" .gitignore 2>/dev/null; then
  echo "ios/sentry.properties" >> .gitignore
  echo "Added ios/sentry.properties to .gitignore."
fi
if ! grep -q "^android/sentry.properties$" .gitignore 2>/dev/null; then
  echo "android/sentry.properties" >> .gitignore
fi

echo
echo "Done. Next steps:"
echo
echo "1. The next \`eas build\` will trigger eas-build-post-install.sh,"
echo "   which generates ios/sentry.properties from these env vars on"
echo "   the build VM. Source maps then upload during the build."
echo
echo "2. For commit→release tagging, also add the same secrets to GitHub"
echo "   Actions: Settings → Secrets and variables → Actions → New repository"
echo "   secret. Add SENTRY_ORG, SENTRY_PROJECT, SENTRY_AUTH_TOKEN."
echo "   The .github/workflows/sentry-release.yml workflow will then auto-tag"
echo "   a Sentry release on each push to main / feature/all-enhancements."
echo
echo "3. Verify after first build: sentry.io → your project → Releases."
