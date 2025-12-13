#!/bin/bash
set -e

TARGET="app/(tabs)/index.tsx"

if [ ! -f "$TARGET" ]; then
  echo "❌ ERROR: $TARGET not found"
  exit 1
fi

echo "📝 Backing up $TARGET..."
cp "$TARGET" "$TARGET.bak_twitch_$(date +%s)"

python <<'PY'
import os

path = "app/(tabs)/index.tsx"

with open(path, "r", encoding="utf-8") as f:
    src = f.read()

orig = src

# 1) Fix the empty Twitch card title
old_title_block = (
    "              <Text style={[styles.cardTitle, { color: colors.text }]}>\n"
    "              </Text>"
)

new_title_block = (
    "              <Text style={[styles.cardTitle, { color: colors.text }]}>\\n"
    "                Twitch creators & streams\\n"
    "              </Text>"
)

if old_title_block in src:
    src = src.replace(old_title_block, new_title_block, 1)
    print("✔ Filled in Twitch card title with 'Twitch creators & streams'")
else:
    print("⚠️ Could not find exact empty title block to replace")

# 2) Improve the subtitle under the title
old_subtitle = "Curated streamers that fit your categories."
new_subtitle = (
    "Paint streams, deck techs and hobby hangs that match your collection focus."
)

if old_subtitle in src:
    src = src.replace(old_subtitle, new_subtitle, 1)
    print("✔ Updated Twitch card subtitle copy")
else:
    print("⚠️ Twitch subtitle string not found; skipping subtitle update")

# 3) Improve the hint text under the card
old_hint = (
    "Later this will show live-now badges and direct links, weighted by\n"
    "            how close they are to your portfolio."
)
new_hint = (
    "Running in demo mode for now. Once Twitch + Supabase are wired, this will show "
    "live-now badges and creators ranked by how close they are to your collection."
)

if old_hint in src:
    src = src.replace(old_hint, new_hint, 1)
    print("✔ Updated Twitch card hint copy")
else:
    print("⚠️ Twitch hint block not found; skipping hint update")

if src != orig:
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"💾 Updated {path}")
else:
    print("ℹ️ No changes written; source remained identical.")
PY
