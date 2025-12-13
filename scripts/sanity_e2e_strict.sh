#!/usr/bin/env bash
set -euo pipefail
LOG=".sanity.log"
echo "=== $(date -Is) start ===" | tee -a "$LOG"

./scripts/force_jwt_refresh.sh | tee -a "$LOG"
./scripts/run_predict_with_image.sh | tee -a "$LOG"
./scripts/verify_dualwrite.sh | tee -a "$LOG"

echo "=== $(date -Is) ok ===" | tee -a "$LOG"
