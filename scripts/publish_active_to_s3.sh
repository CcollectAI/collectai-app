#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"; ROOT="$(cd -- "$ROOT/.." && pwd -P)"
cd "$ROOT"
: "${ARTIFACT_BUCKET:?Set ARTIFACT_BUCKET}"; REGION="${AWS_REGION:-eu-north-1}"
D_VER=$(basename "$(readlink -f artifacts/diecast/active)")
L_VER=$(basename "$(readlink -f artifacts/lego/active)")
printf '{"version":"%s"}' "$D_VER" | aws s3 cp - "s3://$ARTIFACT_BUCKET/artifacts/price/diecast/ACTIVE.json" --region "$REGION" --content-type application/json
printf '{"version":"%s"}' "$L_VER" | aws s3 cp - "s3://$ARTIFACT_BUCKET/artifacts/price/lego/ACTIVE.json"   --region "$REGION" --content-type application/json
aws s3 cp "s3://$ARTIFACT_BUCKET/artifacts/price/diecast/ACTIVE.json" - --region "$REGION" || true
aws s3 cp "s3://$ARTIFACT_BUCKET/artifacts/price/lego/ACTIVE.json"   - --region "$REGION" || true
