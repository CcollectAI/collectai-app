#!/usr/bin/env bash
set -euo pipefail

FILE="app/(tabs)/index.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.pre_restore_${TS}"
echo "✅ Saved current: $FILE.pre_restore_${TS}"

# Candidate backups: bak_* and pre_*
mapfile -t CANDS < <(ls -1 app/\(tabs\)/index.tsx.bak_* app/\(tabs\)/index.tsx.pre_* 2>/dev/null || true)

if [ "${#CANDS[@]}" -eq 0 ]; then
  echo "❌ No backup candidates found (index.tsx.bak_* / index.tsx.pre_*)."
  echo "Run: ls -lah app/(tabs)/index.tsx* and paste it."
  exit 1
fi

# Choose “best” = largest file size; tie-break by newest mtime
BEST="$(python3 - <<'PY'
import os, sys, glob
cands = []
for p in glob.glob('app/(tabs)/index.tsx.bak_*') + glob.glob('app/(tabs)/index.tsx.pre_*'):
    try:
        st=os.stat(p)
        cands.append((st.st_size, st.st_mtime, p))
    except: pass
cands.sort(key=lambda x:(x[0], x[1]))
print(cands[-1][2] if cands else "")
PY
)"

if [ -z "$BEST" ]; then
  echo "❌ Could not select a best backup."
  exit 1
fi

echo "✅ Restoring Portfolio from: $BEST"
cp "$BEST" "$FILE"

echo "✅ Restored. Quick preview:"
head -n 20 "$FILE"
echo
echo "🛑 SANITY CHECK NOW: npx expo start --tunnel"
