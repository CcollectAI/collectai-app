#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."  # repo root

branch="autosave"
ts="$(date -u +%Y%m%d-%H%M%S)"
tag="autosave-$ts"

git init 2>/dev/null || true
git add -A
if ! git diff --cached --quiet; then
  git commit -m "autosave: snapshot $ts" || true
fi

git branch -f "$branch" 2>/dev/null || true
git tag -f "$tag" 2>/dev/null || true
git tag -f autosave-latest 2>/dev/null || true
echo "Nightly autosave completed → branch:$branch tag:$tag"
