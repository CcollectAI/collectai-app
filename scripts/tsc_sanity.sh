#!/usr/bin/env bash
set -euo pipefail

echo "[tsc_sanity] running TypeScript check..."
npx tsc --noEmit

echo "[tsc_sanity] OK"
