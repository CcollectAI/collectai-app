#!/usr/bin/env bash
set -euo pipefail
CAT="${1:?cat}"
VER="$(basename "$(readlink -f "artifacts/${CAT}/active")")"
echo "== feature schema for ${CAT}"
python3 - <<'PY'
from app.ml.features import feature_order
import sys
cat=sys.argv[1]
num, catf = feature_order(cat)
print({"numeric":num,"categorical":catf})
PY "${CAT}"
# TODO: wire prod telemetry → compute PSI across buckets; placeholder exit 0
exit 0
