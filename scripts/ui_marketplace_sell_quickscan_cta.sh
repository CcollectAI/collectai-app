#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/marketplace.tsx"

if [ ! -f "$TARGET" ]; then
  echo "Marketplace screen not found at $TARGET"
  exit 1
fi

echo "Backing up $TARGET"
cp "$TARGET" "$TARGET.bak.sell_quickscan_cta.$(date +%s)" || true

# Rewrite only the Sell tab portion by replacing renderSell function
python <<'PY'
from pathlib import Path

path = Path("app/(tabs)/marketplace.tsx")
text = path.read_text()

start = text.find("  const renderSell = function () {")
end = text.find("  };\n\n  let content", start)
if start == -1 or end == -1:
    raise SystemExit("renderSell function not found; aborting.")

before = text[:start]
after = text[end:]

replacement = r'''  const renderSell = function () {
    return (
      <View style={{ gap: 12 }}>
        {/* CTA: Scan items with QuickScan */}
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 6, color: "#103b5c" }}>
            Scan items with QuickScan
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 10 }}>
            In the full flow, you start on the Add tab, open the camera, and let QuickScan
            detect category, edition, condition and price. From there you can publish a
            listing into the marketplace with guidance from the pricing model.
          </Text>
          <View
            style={{
              marginTop: 4,
              paddingVertical: 10,
              paddingHorizontal: 12,
              borderRadius: 999,
              backgroundColor: "#103b5c",
              alignItems: "center",
            }}
          >
            <Text style={{ color: "#ffffff", fontWeight: "600" }}>
              Open QuickScan on the Add tab
            </Text>
          </View>
          <Text style={{ marginTop: 6, color: "#7a8b9a", fontSize: 11 }}>
            Demo note: this button is visual only. To try QuickScan, tap the “Add” tab in
            the bottom navigation and use the existing Add screen.
          </Text>
        </View>

        {/* MVP explanation card */}
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 15, fontWeight: "600", marginBottom: 4, color: "#103b5c" }}>
            Listing flow (MVP vision)
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 6 }}>
            Here is how the sell experience will work in the MVP:
          </Text>
          <Text style={{ color: "#4a647a", fontSize: 13 }}>
            1. Open the Add tab and run QuickScan on your item.{"\n"}
            2. The app pre-fills title, category, edition and condition.{"\n"}
            3. The pricing engine suggests a low / mid / high range.{"\n"}
            4. You tweak the price and details if needed.{"\n"}
            5. Publish the listing into the marketplace.{"\n"}
            6. Buyers can check your seller trust profile before making an offer.
          </Text>
          <Text style={{ marginTop: 8, color: "#7a8b9a", fontSize: 11 }}>
            Seller trust stays attached to your seller profile and is visible from the
            listing screen (like “view seller” on Amazon or Vinted), not as a separate
            global card on this tab.
          </Text>
        </View>
      </View>
    );
  };
'''

path.write_text(before + replacement + after)
PY

echo "Marketplace Sell tab updated with QuickScan CTA and clarified MVP flow."
