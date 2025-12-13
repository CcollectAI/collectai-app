#!/usr/bin/env bash
set -e

echo "[ts-analytics] Running TypeScript check and filtering for analytics-related files…"
npx tsc --noEmit --pretty false 2>&1 | grep -i -E 'analytics|portfolio-analytics|status|leaderboard' -n || {
  echo "[ts-analytics] No analytics-related TS errors found (by name filter)."
}
