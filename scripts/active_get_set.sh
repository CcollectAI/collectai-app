#!/usr/bin/env bash
set -euo pipefail
CMD="${1:-get}"; CAT="${2:-pokemon}"
APP="$HOME/collectors-merge-recovered"
set -a; . "$APP/env/.env"; set +a
REGION="${AWS_REGION:-eu-north-1}"
ART="s3://${ARTIFACT_BUCKET}/artifacts/price/${CAT}"
case "$CMD" in
  get) aws s3 cp "$ART/ACTIVE.json" - --region "$REGION" || echo '{"version":"<none>"}' ;;
  set) VER="${3:?version required}"; printf '{"version":"%s"}\n' "$VER" | aws s3 cp - "$ART/ACTIVE.json" --region "$REGION" ;;
  *) echo "usage: $0 get|set <category> [version]"; exit 2 ;;
esac
