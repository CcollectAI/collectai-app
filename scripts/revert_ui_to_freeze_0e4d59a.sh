#!/usr/bin/env bash
set -euo pipefail

BASE="0e4d59a"
TS="$(date +%Y%m%d_%H%M%S)"

echo "==> Safety branch from current state (non-destructive)"
git switch -c "rescue/before_revert_${TS}" >/dev/null 2>&1 || git switch "rescue/before_revert_${TS}"
git add -A >/dev/null 2>&1 || true
git commit -m "RESCUE: before revert ${TS}" >/dev/null 2>&1 || true

echo "==> Switching back to your baseline branch if present"
git switch restore/baseline-1dc1d5d >/dev/null 2>&1 || true

echo "==> Restoring UI files from frozen baseline commit: ${BASE}"
# Restore ONLY the files we touched / that affect the current issue
git checkout "${BASE}" -- \
  app/(tabs)/index.tsx \
  app/(tabs)/_layout.tsx \
  app/(tabs)/search.tsx \
  app/(tabs)/marketplace.tsx \
  app/_layout.tsx \
  app/twitch.tsx \
  src/components/PortfolioLineChart.tsx \
  src/components/PortfolioHoverChart.tsx \
  src/hooks/useAppTheme.ts \
  src/theme/index.ts \
  src/theme/useAppTheme.ts \
  2>/dev/null || true

echo "==> Confirm restored versions (file sizes)"
ls -lah app/\(tabs\)/index.tsx app/\(tabs\)/_layout.tsx app/\(tabs\)/marketplace.tsx app/twitch.tsx | sed -n '1,120p'

echo "✅ UI files restored to frozen baseline state (0e4d59a)."
echo "🛑 SANITY CHECK NOW: npx expo start --tunnel"
