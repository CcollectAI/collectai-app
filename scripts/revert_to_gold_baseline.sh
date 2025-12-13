#!/usr/bin/env bash
set -euo pipefail
git reset --hard gold-baseline
echo "✅ Reverted tracked files to gold-baseline"
