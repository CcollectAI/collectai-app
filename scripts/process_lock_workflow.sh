#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d_%H%M%S)"

echo "==> 1) Create a GOLD BASELINE tag from current HEAD (only do this when app is stable)"
git tag -f gold-baseline || true

echo "==> 2) Create/checkout a WORK branch for changes"
git switch -c "work/ui_${TS}" >/dev/null 2>&1 || git switch "work/ui_${TS}"

echo "==> 3) Add a visible build stamp to Portfolio so we know we're editing the right file"
FILE="app/(tabs)/index.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

cp "$FILE" "$FILE.bak_stamp_${TS}"

python3 - <<PY
import pathlib, re
p=pathlib.Path("app/(tabs)/index.tsx")
s=p.read_text()

# Add a small stamp banner at the top of the rendered tree, only if not already present
if "PORTFOLIO_STAMP__" in s:
    print("✅ Stamp already present.")
    raise SystemExit(0)

# Try to inject inside the return() of default component: after first opening container View/SafeAreaView
# We'll insert a little banner component JSX.
stamp = r'''
      {/* PORTFOLIO_STAMP__ do not remove until we lock the final Portfolio */}
      <View style={{ paddingHorizontal: 16, paddingTop: 6, paddingBottom: 6 }}>
        <Text style={{ fontSize: 12, fontWeight: "900", color: "#dc2626" }}>
          PORTFOLIO STAMP: work/ui_${TS}
        </Text>
      </View>
'''

# Ensure View/Text imported
if not re.search(r'import\s*{\s*[^}]*\bView\b', s):
    s = re.sub(r'import\s*{\s*([^}]*)}\s*from\s*"react-native";',
               lambda m: 'import { ' + (m.group(1).strip()+', ' if m.group(1).strip() else '') + 'View, Text } from "react-native";',
               s, count=1)

# If import line doesn't exist in that format, we won't attempt complex rewrites here.
# Inject stamp after first occurrence of <ScrollView or <SafeAreaView content start:
m = re.search(r'(<ScrollView[^>]*>\s*)', s)
if m:
    s = s[:m.end()] + stamp + s[m.end():]
else:
    m = re.search(r'(<SafeAreaView[^>]*>\s*)', s)
    if m:
        s = s[:m.end()] + stamp + s[m.end():]
    else:
        # Fallback: inject after first return (
        s = re.sub(r'(return\s*\(\s*)', r'\1\n' + stamp + '\n', s, count=1)

p.write_text(s)
print("✅ Stamp injected into app/(tabs)/index.tsx")
PY

echo "==> 4) Create an instant revert script to GOLD BASELINE"
cat > scripts/revert_to_gold_baseline.sh <<'RB'
#!/usr/bin/env bash
set -euo pipefail
git reset --hard gold-baseline
echo "✅ Reverted tracked files to gold-baseline"
RB
chmod +x scripts/revert_to_gold_baseline.sh

echo
echo "✅ Done."
echo "NEXT:"
echo "  1) npx expo start --tunnel"
echo "  2) Confirm you see: PORTFOLIO STAMP: work/ui_${TS}"
echo
echo "If anything goes wrong later, run:"
echo "  bash scripts/revert_to_gold_baseline.sh"
