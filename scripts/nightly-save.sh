#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
STAMP=$(date +%Y%m%d-%H%M)
git add -A || true
git commit -m "nightly autosave $STAMP" || true
git tag -f autosave-nightly || true
