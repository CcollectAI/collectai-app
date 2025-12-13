#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

echo "=== Scanning for extra _layout.tsx files that use <Tabs> (outside app/(tabs)/_layout.tsx) ==="

# Collect all _layout.tsx that contain "Tabs.Screen", excluding the main app/(tabs)/_layout.tsx
python3 <<'PYCODE'
from pathlib import Path

root = Path("app")
targets = []

for layout in root.rglob("_layout.tsx"):
    rel = layout.as_posix()
    if rel == "app/(tabs)/_layout.tsx":
        continue
    text = layout.read_text(encoding="utf-8")
    if "Tabs.Screen" in text or "<Tabs" in text:
        targets.append(layout)

if not targets:
    print("ℹ️ No extra Tabs-based layouts found outside app/(tabs)/_layout.tsx.")
else:
    print("Found extra Tabs layouts:")
    for p in targets:
        print(" -", p)

    # For each extra Tabs layout, back it up and replace with a simple Stack layout
    for layout in targets:
        rel = layout.as_posix()
        bak = layout.with_suffix(layout.suffix + ".bak_extraTabs")
        layout.replace(bak)
        print(f"📦 Backed up {rel} -> {bak.as_posix()}")

        # Write a simple Stack layout that does NOT create a bottom tab bar
        layout.write_text("""import React from "react";
import { Stack } from "expo-router";

/**
 * Simplified layout: Stack only, no Tabs.
 * This file was auto-generated to avoid duplicate bottom tab bars.
 * Original file is backed up as _layout.tsx.bak_extraTabs alongside this file.
 */
export default function Layout() {
  return (
    <Stack screenOptions={{ headerShown: false }} />
  );
}
""", encoding="utf-8")
        print(f"✅ Replaced {rel} with a Stack-only layout (no Tabs).")
PYCODE

echo
echo "=== Done scanning & cleaning extra tab layouts (if any). ==="
