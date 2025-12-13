#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/marketplace.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.ui_marketplace_segmented.$(date +%s)"
else
  echo "Creating new Marketplace screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, Pressable } from "react-native";

type TabKey = "chat" | "search" | "sell";

function SegmentedTabs(props: {
  active: TabKey;
  onChange: (tab: TabKey) => void;
}) {
  const tabs: { key: TabKey; label: string }[] = [
    { key: "chat", label: "Chat" },
    { key: "search", label: "Search" },
    { key: "sell", label: "Sell" },
  ];

  return (
    <View
      style={{
        flexDirection: "row",
        backgroundColor: "#d0e9f5",
        borderRadius: 999,
        padding: 4,
        marginBottom: 16,
      }}
    >
      {tabs.map(function (t) {
        const isActive = props.active === t.key;
        return (
          <Pressable
            key={t.key}
            onPress={function () {
              props.onChange(t.key);
            }}
            style={{
              flex: 1,
              paddingVertical: 6,
              borderRadius: 999,
              backgroundColor: isActive ? "#ffffff" : "transparent",
              alignItems: "center",
            }}
          >
            <Text
              style={{
                color: isActive ? "#103b5c" : "#4a647a",
                fontWeight: isActive ? "600" : "400",
              }}
            >
              {t.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function MarketplaceScreen() {
  const [active, setActive] = useState<TabKey>("search");

  let body: JSX.Element;

  if (active === "chat") {
    body = (
      <View>
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            marginBottom: 16,
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}>
            Chat (mock)
          </Text>
          <Text style={{ color: "#4a647a" }}>
            In the MVP, buyers and sellers will be able to chat about a listing,
            share photos and negotiate before committing. This is a mock tab to
            show where the conversation UX will live.
          </Text>
        </View>
      </View>
    );
  } else if (active === "search") {
    body = (
      <View>
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            marginBottom: 16,
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}>
            Search listings (mock)
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 4 }}>
            This tab will surface Pokémon, Funko, Gunpla and other categories with
            live pricing overlays.
          </Text>
          <Text style={{ color: "#4a647a" }}>
            For MVP, we keep this as a static description instead of a full search UI.
          </Text>
        </View>
      </View>
    );
  } else {
    // Sell tab with authenticity checker explanation
    body = (
      <View>
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            marginBottom: 16,
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}>
            List an item (MVP)
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 4 }}>
            The listing flow will include QuickScan, pricing guidance, and later a
            seller profile screen with trust metrics (like an Amazon seller page).
          </Text>
          <Text style={{ color: "#4a647a" }}>
            That per-seller trust overview will not live on this main tab; it will
            appear when a buyer taps into a seller&apos;s listing.
          </Text>
        </View>

        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            marginBottom: 16,
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 8, color: "#103b5c" }}>
            Authenticity checker (light version)
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 4 }}>
            Sellers will upload photos or screenshots of their listing. The app will
            run light-weight authenticity checks and flag unusual patterns.
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 4 }}>
            This includes listing screenshot authenticity score, provenance hints,
            and behavioural anti-scam signals.
          </Text>
          <Text style={{ color: "#7a8b9a", fontSize: 12, marginTop: 4 }}>
            Demo mode: this tab explains how the tools will work. The full seller
            trust overview will be shown on each seller profile page, not here.
          </Text>
        </View>
      </View>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#e6f7fb" }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 32, paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16, color: "#103b5c" }}>
        Marketplace
      </Text>

      <SegmentedTabs active={active} onChange={setActive} />

      {body}
    </ScrollView>
  );
}
EOF

echo "Marketplace tab updated: segmented Chat/Search/Sell, authenticity under Sell, no root seller trust card."
