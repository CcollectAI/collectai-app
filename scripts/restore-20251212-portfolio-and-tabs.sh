#!/usr/bin/env bash
set -euo pipefail

PORTF="app/(tabs)/index.tsx"
TABS="app/(tabs)/_layout.tsx"

need() { [ -f "$1" ] || { echo "ERROR: missing $1"; exit 1; }; }
need "$PORTF"
need "$TABS"

TS="$(date +%Y%m%d_%H%M%S)"
cp "$PORTF" "${PORTF}.pre_restore_${TS}"
cp "$TABS"  "${TABS}.pre_restore_${TS}"

# Pick the most recent Dec 12 backup for each file.
PORTF_BAK="$(ls -1t app/\(tabs\)/index.tsx.bak_20251212_* 2>/dev/null | head -n 1 || true)"
TABS_BAK="$(ls -1t app/\(tabs\)/_layout.tsx.bak_20251212_* 2>/dev/null | head -n 1 || true)"

if [ -z "$PORTF_BAK" ]; then
  echo "ERROR: No Portfolio backup found for 20251212 (app/(tabs)/index.tsx.bak_20251212_*)"
  exit 1
fi

if [ -z "$TABS_BAK" ]; then
  echo "ERROR: No Tabs layout backup found for 20251212 (app/(tabs)/_layout.tsx.bak_20251212_*)"
  exit 1
fi

echo "Restoring Portfolio from: $PORTF_BAK"
cp "$PORTF_BAK" "$PORTF"

echo "Restoring Tabs layout from: $TABS_BAK"
cp "$TABS_BAK" "$TABS"

# ---- Minimal requested tweaks in Tabs layout ----
# 1) Ensure words under icons
# (Add tabBarShowLabel:true if missing)
if ! grep -q "tabBarShowLabel" "$TABS"; then
  perl -0777 -pi -e 's/screenOptions=\{\{\s*/screenOptions={{\n        tabBarShowLabel: true,\n        tabBarLabelPosition: "below-icon",\n        tabBarLabelStyle: { fontSize: 11, fontWeight: "700" },\n/s' "$TABS"
fi

# 2) Portfolio icon: pie chart instead of home (Ionicons)
# Replace common home icon names if present
perl -pi -e 's/home-outline/pie-chart-outline/g; s/home/pie-chart/g' "$TABS"

echo "OK: Restored 2025-12-12 versions + applied: labels under icons, pie-chart icon"
echo "Backups created:"
echo " - ${PORTF}.pre_restore_${TS}"
echo " - ${TABS}.pre_restore_${TS}"
