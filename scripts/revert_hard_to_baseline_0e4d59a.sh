#!/usr/bin/env bash
set -euo pipefail

BASE="0e4d59a"
TS="$(date +%Y%m%d_%H%M%S)"

echo "==> Safety branch (so nothing is lost)"
git switch -c "rescue/before_hard_revert_${TS}" >/dev/null 2>&1 || true
git add -A >/dev/null 2>&1 || true
git commit -m "RESCUE: before hard revert ${TS}" >/dev/null 2>&1 || true

echo "==> Hard reset tracked files to baseline commit: ${BASE}"
git reset --hard "${BASE}"

echo "==> Confirm key files are exactly from baseline"
git show --stat -1 "${BASE}" | sed -n '1,120p'
echo
ls -lah app/\(tabs\)/index.tsx app/\(tabs\)/_layout.tsx app/\(tabs\)/marketplace.tsx app/twitch.tsx 2>/dev/null || true
echo
echo "✅ Done. SANITY CHECK: npx expo start --tunnel"
