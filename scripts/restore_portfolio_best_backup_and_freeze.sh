#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/index.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS="$(date +%Y%m%d_%H%M%S)"
cp "$FILE" "$FILE.pre_restore_${TS}"
echo "✅ Saved current: $FILE.pre_restore_${TS}"

BEST="$(python3 - <<'PY'
import glob, os
cands = glob.glob("app/(tabs)/index.tsx.bak_*") + glob.glob("app/(tabs)/index.tsx.pre_*")
rows=[]
for p in cands:
    try:
        st=os.stat(p)
        rows.append((st.st_size, st.st_mtime, p))
    except: pass
rows.sort()
print(rows[-1][2] if rows else "")
PY
)"

if [ -z "$BEST" ]; then
  echo "❌ No backups found for Portfolio index.tsx"
  exit 1
fi

echo "✅ Restoring Portfolio from: $BEST"
cp "$BEST" "$FILE"

echo "==> Quick confirm (size should NOT be ~1KB stripe file)"
ls -lah "$FILE"
echo
echo "==> Commit as new baseline"
git add "$FILE"
git commit -m "FREEZE2: restore Portfolio from best backup (${TS})" || true

echo "✅ Done. SANITY CHECK: npx expo start --tunnel"
