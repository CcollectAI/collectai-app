#!/usr/bin/env bash
set -euo pipefail

python3 <<'PYCODE'
import pathlib

PROJECT_ROOT = pathlib.Path("/home/ubuntu/collectors-merge-recovered")

def inject_into_file(
    filename: str,
    import_lines: list[str],
    top_component: str | None,
    bottom_components: list[str],
):
    path = PROJECT_ROOT / "app" / "(tabs)" / filename
    if not path.exists():
        print(f"  ⚠️  {path} not found, skipping.")
        return

    text = path.read_text(encoding="utf-8")

    # Back up original
    backup = path.with_suffix(path.suffix + ".bak_banner_" + filename.replace(".tsx", ""))
    backup.write_text(text, encoding="utf-8")
    print(f"  📦 Backed up {path} to {backup}")

    # ---------- IMPORTS ----------
    for imp in import_lines:
        if imp.strip() in text:
            continue
        # Insert after first expo-router import if possible
        idx_router = max(text.find('from "expo-router"'), text.find("from 'expo-router'"))
        if idx_router != -1:
            end_line = text.find("\n", idx_router)
            text = text[: end_line + 1] + imp + "\n" + text[end_line + 1 :]
        else:
            # otherwise prepend
            text = imp + "\n" + text

    # ---------- TOP BANNER (ITEMS ONLY) ----------
    if top_component:
        if top_component.strip() in text:
            print(f"  ✓ Top component already present in {path}, skipping top inject.")
        else:
            # Try to inject after opening ScrollView or main content View
            inserted = False
            for marker in ["<ScrollView", "<View"]:
                idx = text.find(marker)
                if idx != -1:
                    # Find the end of the opening tag line
                    line_end = text.find(">", idx)
                    if line_end != -1:
                        insert_pos = line_end + 1
                        text = text[:insert_pos] + "\n    " + top_component + "\n" + text[insert_pos:]
                        print(f"  ✅ Injected top component into {path} after {marker}.")
                        inserted = True
                        break
            if not inserted:
                print(f"  ⚠️ Could not find a safe top injection point in {path}.")

    # ---------- BOTTOM BANNERS ----------
    for component in bottom_components:
        if component.strip() in text:
            print(f"  ✓ Bottom component already present in {path}, skipping.")
            continue

        # Prefer to inject before last </ScrollView>
        marker = "</ScrollView>"
        idx = text.rfind(marker)
        if idx != -1:
            text = text[:idx] + "      " + component + "\n" + text[idx:]
            print(f"  ✅ Injected bottom component into {path} before </ScrollView>.")
        else:
            marker = "</View>"
            idx = text.rfind(marker)
            if idx != -1:
                text = text[:idx] + "      " + component + "\n" + text[idx:]
                print(f"  ✅ Injected bottom component into {path} before </View>.")
            else:
                print(f"  ⚠️ Could not find a safe bottom injection point in {path}.")

    path.write_text(text, encoding="utf-8")


# Portfolio: only calendar banner at bottom
inject_into_file(
    "portfolio.tsx",
    ['import UpcomingEventsBanner from "@/components/UpcomingEventsBanner";'],
    top_component=None,
    bottom_components=['<UpcomingEventsBanner context="portfolio" />'],
)

# Items: top overview banner, then separate bottom banners
inject_into_file(
    "items.tsx",
    [
        'import ItemsOverviewBanner from "@/components/ItemsOverviewBanner";',
        'import UpcomingEventsBanner from "@/components/UpcomingEventsBanner";',
        'import BuildProjectsBanner from "@/components/BuildProjectsBanner";',
    ],
    top_component="<ItemsOverviewBanner />",
    bottom_components=[
        '<UpcomingEventsBanner context="items" />',
        "<BuildProjectsBanner />",
    ],
)

PYCODE
