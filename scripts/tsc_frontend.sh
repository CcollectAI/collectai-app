#!/usr/bin/env bash
set -euo pipefail

echo "[tsc_frontend] running TypeScript check for app/ + theme only..."
npx tsc -p tsconfig.frontend.json

echo "[tsc_frontend] OK"
