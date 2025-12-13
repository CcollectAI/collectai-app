#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1
ts="$(date +%Y%m%d_%H%M%S)"
log="expo-doctor-$ts.log"

echo "== env =="
node -v || true
npx --version || true

echo "== quick sanity: are there 'app/ui' routes? (should NOT exist) =="
if [ -d "app/ui" ]; then
  echo "FATAL: app/ui exists and will be treated as routes by expo-router."
  echo "Move it out of app/:   mv app/ui src/ui   (or quarantine it)"
  exit 2
fi

echo "== quick sanity: do common route files export default? =="
# only check the most likely culprits (fast)
for f in app/_layout.tsx app/index.tsx app/+not-found.tsx app/\(tabs\)/_layout.tsx app/\(tabs\)/index.tsx; do
  if [ -f "$f" ]; then
    if ! grep -q "export default" "$f"; then
      echo "FATAL: $f is missing 'export default'."
      exit 3
    fi
  fi
done

echo "== start expo (clean cache) and capture first hard error =="
echo "Writing log to: $log"
# kill any old metro/expo
pkill -f "expo start" >/dev/null 2>&1 || true
pkill -f "metro" >/dev/null 2>&1 || true

# run expo; stop after first ERROR block
( npx expo start -c --non-interactive 2>&1 | tee "$log" ) &
pid=$!

# Wait until we see a red-flag error pattern, then kill expo and print context.
# Patterns cover: bundling failed, unable to resolve, syntax error, missing default export, etc.
while kill -0 "$pid" >/dev/null 2>&1; do
  if grep -Eq "Bundling failed|Unable to resolve|SyntaxError|Unexpected token|missing the required default export|TypeError:|ReferenceError:" "$log"; then
    echo
    echo "== FIRST BLOCKING ERROR (context) =="
    # print ~80 lines around the first match
    python - <<'PY'
import re
pats = re.compile(r"(Bundling failed|Unable to resolve|SyntaxError|Unexpected token|missing the required default export|TypeError:|ReferenceError:)")
lines=open(sorted([p for p in __import__("glob").glob("expo-doctor-*.log")])[-1]).read().splitlines()
for i,l in enumerate(lines):
  if pats.search(l):
    start=max(0,i-20); end=min(len(lines), i+80)
    print("\n".join(lines[start:end]))
    break
PY
    echo
    echo "== stopping expo =="
    kill "$pid" >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 0.5
done

echo "Expo exited without matching error patterns. Check log: $log"
exit 0
