#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

echo "=== Step 1: Ensure UpcomingEventsBanner component exists under src/components ==="

SRC_DIR="$PROJECT_ROOT/src"
SRC_COMPONENTS_DIR="$SRC_DIR/components"
BANNER_FILE="$SRC_COMPONENTS_DIR/UpcomingEventsBanner.tsx"

mkdir -p "$SRC_COMPONENTS_DIR"

if [ -f "$BANNER_FILE" ]; then
  echo "  ✓ Found existing $BANNER_FILE"
else
  echo "  ⚠️  $BANNER_FILE not found, creating it."
  cat > "$BANNER_FILE" <<'TSX'
import React from "react";
import { View, Text, Pressable } from "react-native";
import { useRouter } from "expo-router";

type BannerContext = "portfolio" | "items";

interface Props {
  context?: BannerContext;
}

/**
 * Small CTA banner that links into the Calendar v1 demo.
 * Use at the bottom of Portfolio and Items.
 */
export default function UpcomingEventsBanner({ context = "portfolio" }: Props) {
  const router = useRouter();

  const title =
    context === "items"
      ? "Events & drops for your items"
      : "Upcoming events & drops";

  const subtitle =
    context === "items"
      ? "See release dates and events linked to your collections."
      : "Track big releases, tournaments, and value catalysts.";

  const buttonLabel =
    context === "items" ? "Open calendar" : "View events calendar";

  return (
    <View
      style={{
        marginTop: 16,
        marginBottom: 24,
        padding: 16,
        borderRadius: 12,
        backgroundColor: "#E5F4F8",
        borderWidth: 1,
        borderColor: "#B4DDE7",
      }}
    >
      <Text
        style={{
          fontSize: 14,
          fontWeight: "600",
          marginBottom: 4,
        }}
      >
        {title}
      </Text>
      <Text
        style={{
          fontSize: 12,
          marginBottom: 12,
          opacity: 0.85,
        }}
      >
        {subtitle}
      </Text>

      <Pressable
        onPress={() => router.push("/calendar-v1-demo")}
        style={{
          alignSelf: "flex-start",
          paddingHorizontal: 14,
          paddingVertical: 8,
          borderRadius: 999,
          backgroundColor: "#00A3C4",
        }}
      >
        <Text
          style={{
            color: "#FFFFFF",
            fontSize: 12,
            fontWeight: "600",
          }}
        >
          {buttonLabel}
        </Text>
      </Pressable>
    </View>
  );
}
TSX
fi

echo
echo "=== Step 2: Inject banner into Portfolio and Items tabs ==="

PY_SCRIPT="$(mktemp)"

cat > "$PY_SCRIPT" <<'PYCODE'
import pathlib

project_root = pathlib.Path("/home/ubuntu/collectors-merge-recovered")

def inject_banner(tab_name: str, context: str):
    path = project_root / "app" / "(tabs)" / f"{tab_name}.tsx"
    if not path.exists():
        print(f"  ⚠️  {path} not found, skipping.")
        return

    text = path.read_text(encoding="utf-8")

    if "UpcomingEventsBanner" in text:
        print(f"  ✓ {tab_name}.tsx already references UpcomingEventsBanner, skipping injection.")
        return

    backup = path.with_suffix(path.suffix + f".bak_addcalendar_{tab_name}")
    backup.write_text(text, encoding="utf-8")
    print(f"  📦 Backed up {path} to {backup}")

    # 1) Add import line
    import_line = 'import UpcomingEventsBanner from "@/components/UpcomingEventsBanner";\n'
    if 'from "expo-router"' in text or "from 'expo-router'" in text:
        # insert after first expo-router import line
        idx = text.find("from \"expo-router\"")
        single = False
        if idx == -1:
            idx = text.find("from 'expo-router'")
            single = True
        if idx != -1:
            end_line = text.find("\n", idx)
            text = text[: end_line + 1] + import_line + text[end_line + 1 :]
        else:
            text = import_line + text
    else:
        # insert after first import line if any
        first_import = text.find("import ")
        if first_import != -1:
            end_line = text.find("\n", first_import)
            text = text[: end_line + 1] + import_line + text[end_line + 1 :]
        else:
            text = import_line + text

    # 2) Inject banner before last </ScrollView> if possible,
    #    otherwise before last </View> as a fallback.
    marker = "</ScrollView>"
    idx = text.rfind(marker)
    injection = f'      <UpcomingEventsBanner context="{context}" />\n'
    if idx == -1:
        marker = "</View>"
        idx = text.rfind(marker)
        if idx == -1:
            print(f"  ⚠️  Could not find </ScrollView> or </View> in {path}. "
                  f"Please manually place <UpcomingEventsBanner context=\"{context}\" /> near the bottom.")
            path.write_text(text, encoding="utf-8")
            return
        # Insert before closing View
        text = text[:idx] + injection + text[idx:]
        print(f"  ✅ Injected UpcomingEventsBanner(context=\"{context}\") before last </View> in {path}.")
    else:
        text = text[:idx] + injection + text[idx:]
        print(f"  ✅ Injected UpcomingEventsBanner(context=\"{context}\") before last </ScrollView> in {path}.")

    path.write_text(text, encoding="utf-8")

inject_banner("portfolio", "portfolio")
inject_banner("items", "items")
PYCODE

python "$PY_SCRIPT"
rm "$PY_SCRIPT"

echo
echo "=== Done. Calendar should now be reachable from Portfolio + Items banners. Restart Expo to test. ==="
