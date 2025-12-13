#!/usr/bin/env bash
set -euo pipefail

# If src/app/(tabs) differs from HEAD, warn loudly.
if git diff --name-only | rg -q '^src/app/\(tabs\)/'; then
  echo "❌ Guardrail: You have changes in src/app/(tabs)/"
  echo "This tree is NOT active. Do not edit it."
  echo
  echo "Changed files:"
  git diff --name-only | rg '^src/app/\(tabs\)/' || true
  exit 1
fi

echo "✅ Guardrail OK: no changes in src/app/(tabs)/"
