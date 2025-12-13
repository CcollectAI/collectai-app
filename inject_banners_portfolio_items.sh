#!/usr/bin/env bash
set -euo pipefail

echo "=== Injecting UpcomingEventsBanner into Portfolio + Items tabs ==="

python3 <<'PYCODE'
import pathlib

PROJECT_ROOT = pathlib.Path("/home/ubuntu/collectors-merge-recovered")

def inject(tab_name: str, context: str):
    path = PROJECT_ROOT / "app" / "(tabs)" / f"{tab_name}.tsx"
    if not path.exists():
        print(f"  ⚠️  {path} not found, skipping.")
        return

    text = path.read_text(encoding="utf-8")

    if "UpcomingEventsBanner" in text:
        print(f"  ✓ {tab_name}.tsx already references UpcomingEventsBanner, skipping.")
        return

    # Backup original file
    backup = path.with_suffix(path.suffix + f".bak_banner_{tab_name}")
    backup.write_text(text, encoding="utf-8")
    print(f"  📦 Backed up {path} to {backup}")

    # ---------- 1) ADD IMPORT ----------
    import_line = 'import UpcomingEventsBanner from "@/components/UpcomingEventsBanner";\n'

    # Insert import after first expo-router import if exists
    idx_router = max(text.find('from "expo-router"'), text.find("from 'expo-router'"))
    if idx_router != -1:
        end_line = text.find("\n", idx_router)
        text = text[: end_line + 1] + import_line + text[end_line + 1 :]
    else:
        # Otherwise add at top
        text = import_line + text

    # ---------- 2) INJECT BANNER INTO VIEW ----------
    injection = f'      <UpcomingEventsBanner context="{context}" />\n'

    # Prefer injecting before closing ScrollView
    idx_scroll = text.rfind("</ScrollView>")
    if idx_scroll != -1:
        text = text[:idx_scroll] + injection + text[idx_scroll:]
        print(f"  ✅ Injected banner (context={context}) before </ScrollView> in {path}.")
        path.write_text(text, encoding="utf-8")
        return

    # Fallback: inject before closing main View
    idx_view = text.rfind("</View>")
    if idx_view != -1:
        text = text[:idx_view] + injection + text[idx_view:]
        print(f"  ✅ Injected banner (context={context}) before </View> in {path}.")
        path.write_text(text, encoding="utf-8")
        return

    print(f"  ⚠️ Could not find a safe injection point in {path}. No changes applied.")

# Apply to both tabs
inject("portfolio", "portfolio")
inject("items", "items")

PYCODE

echo "=== Banner injection complete ==="
