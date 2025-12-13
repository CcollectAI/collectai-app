#!/usr/bin/env bash
set -euo pipefail
REGION="${AWS_REGION:-eu-north-1}"
BUCKET="${ARTIFACT_BUCKET:?missing}"
CAT="${1:?cat}"
VER="$(basename "$(readlink -f "artifacts/${CAT}/active")")"
printf '{"version":"%s"}' "$VER" | aws s3 cp - "s3://${BUCKET}/artifacts/price/${CAT}/CANDIDATE.json" --region "$REGION" --content-type application/json
echo "CANDIDATE for ${CAT} -> ${VER} (flip CANARY_PERCENT in /etc/sysconfig/collectors.env if needed)"
