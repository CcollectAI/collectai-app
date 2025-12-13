#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/marketplace.tsx"

if [ ! -f "$TARGET" ]; then
  echo "Marketplace screen not found at $TARGET, creating directory."
  mkdir -p "app/(tabs)"
fi

echo "Backing up $TARGET"
cp "$TARGET" "$TARGET.bak.feedback_pass1.$(date +%s)" || true

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, Pressable, Button } from "react-native";
import { API_BASE } from "../../src/api/config";

type TrustResponse = {
  seller_id?: string;
  risk_score?: number;
  flags?: string[];
  notes?: string[];
};

export default function MarketplaceScreen() {
  const [tab, setTab] = useState<"chat" | "search" | "sell">("search");

  const [trustStatus, setTrustStatus] = useState<string | null>(null);
  const [trustParsed, setTrustParsed] = useState<TrustResponse | null>(null);
  const [trustRaw, setTrustRaw] = useState<string | null>(null);
  const [trustVisible, setTrustVisible] = useState<boolean>(false);

  const loadTrust = async function () {
    setTrustStatus("Loading seller trust…");
    setTrustParsed(null);
    setTrustRaw(null);
    setTrustVisible(true);
    try {
      const url = API_BASE + "/marketplace/trust2/seller/demo-user";
      const res = await fetch(url);
      const text = await res.text();
      setTrustRaw(text);

      let json: TrustResponse | null = null;
      try {
        json = JSON.parse(text);
      } catch (e) {
        json = null;
      }
      setTrustParsed(json);
      const s = "Done (status=" + String(res.status) + ", ok=" + String(res.ok) + ")";
      setTrustStatus(s);
    } catch (e: any) {
      const msg = e && e.message ? e.message : String(e);
      setTrustStatus("Error while loading seller trust: " + msg);
      setTrustParsed(null);
      setTrustRaw(null);
    }
  };

  const renderTabs = function () {
    return (
      <View
        style={{
          flexDirection: "row",
          backgroundColor: "#d0ecf7",
          borderRadius: 999,
          padding: 4,
          marginBottom: 16,
        }}
      >
        {[
          { id: "chat", label: "Chat" },
          { id: "search", label: "Search" },
          { id: "sell", label: "Sell" },
        ].map(function (t) {
          const id = t.id as "chat" | "search" | "sell";
          const active = tab === id;
          return (
            <Pressable
              key={id}
              onPress={function () {
                setTab(id);
              }}
              style={{
                flex: 1,
                paddingVertical: 8,
                borderRadius: 999,
                alignItems: "center",
                backgroundColor: active ? "#ffffff" : "transparent",
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: active ? "600" : "400",
                  color: active ? "#103b5c" : "#4a647a",
                }}
              >
                {t.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    );
  };

  const renderChat = function () {
    const rooms = [
      { id: "tcg-grails", title: "Pokémon / MTG grails", description: "High-end pulls, grading, auctions." },
      { id: "funko-deals", title: "Funko deals & drops", description: "New releases, vaulted pops, trades." },
      { id: "gunpla-builds", title: "Gunpla builds", description: "Work-in-progress, paint jobs, rare kits." },
      { id: "designer-toys", title: "Designer / art toys", description: "Collabs, Labubu-style drops, resale." },
    ];

    return (
      <View style={{ gap: 12 }}>
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4, color: "#103b5c" }}>
            Topic chatrooms
          </Text>
          <Text style={{ color: "#4a647a" }}>
            In the full version, each room is a real-time chat with collectors. For the MVP,
            this is a static preview of how rooms are organised.
          </Text>
        </View>

        {rooms.map(function (room) {
          return (
            <View
              key={room.id}
              style={{
                padding: 14,
                borderRadius: 8,
                borderWidth: 1,
                borderColor: "#dde6ee",
                backgroundColor: "#ffffff",
              }}
            >
              <Text style={{ fontSize: 15, fontWeight: "600", color: "#103b5c", marginBottom: 2 }}>
                {room.title}
              </Text>
              <Text style={{ color: "#4a647a", fontSize: 13 }}>{room.description}</Text>
              <Text style={{ marginTop: 6, color: "#7a8b9a", fontSize: 11 }}>
                Demo mode: tap will do nothing yet – real chat comes later.
              </Text>
            </View>
          );
        })}
      </View>
    );
  };

  const renderSellerTrust = function () {
    if (!trustVisible) {
      return null;
    }

    return (
      <View
        style={{
          marginTop: 8,
          padding: 10,
          borderRadius: 8,
          borderWidth: 1,
          borderColor: "#dde6ee",
          backgroundColor: "#f8fcff",
        }}
      >
        <Text style={{ fontSize: 14, fontWeight: "600", marginBottom: 4, color: "#103b5c" }}>
          Seller trust profile
        </Text>
        {trustStatus && (
          <Text style={{ color: "#4a647a", fontSize: 11, marginBottom: 4 }}>
            {trustStatus}
          </Text>
        )}
        {trustParsed && (
          <>
            <Text style={{ color: "#103b5c", fontSize: 13 }}>
              Seller ID: {trustParsed.seller_id || "demo-user"}
            </Text>
            {typeof trustParsed.risk_score === "number" && (
              <Text style={{ color: "#4a647a", fontSize: 13 }}>
                Risk score: {String(trustParsed.risk_score)}
              </Text>
            )}
            {trustParsed.flags && trustParsed.flags.length > 0 && (
              <Text style={{ color: "#4a647a", fontSize: 12, marginTop: 4 }}>
                Flags: {trustParsed.flags.join(", ")}
              </Text>
            )}
            {trustParsed.notes && trustParsed.notes.length > 0 && (
              <Text style={{ color: "#4a647a", fontSize: 12, marginTop: 4 }}>
                Notes: {trustParsed.notes.join(" • ")}
              </Text>
            )}
          </>
        )}
        {trustRaw && (
          <View
            style={{
              marginTop: 6,
              padding: 6,
              borderRadius: 4,
              borderWidth: 1,
              borderColor: "#dde6ee",
              backgroundColor: "#ffffff",
            }}
          >
            <Text
              style={{
                fontFamily: "monospace",
                fontSize: 10,
                color: "#103b5c",
              }}
            >
              {trustRaw}
            </Text>
          </View>
        )}
      </View>
    );
  };

  const renderSearch = function () {
    return (
      <View style={{ gap: 12 }}>
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4, color: "#103b5c" }}>
            Marketplace search
          </Text>
          <Text style={{ color: "#4a647a" }}>
            Later this will show live listings and comps from different sources. For now
            you can see how a listing and seller profile will look.
          </Text>
        </View>

        {/* Example listing, like Vinted / Amazon style */}
        <View
          style={{
            padding: 16,
            borderRadius: 10,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 15, fontWeight: "600", color: "#103b5c", marginBottom: 4 }}>
            Demo Charizard – graded
          </Text>
          <Text style={{ color: "#4a647a", fontSize: 13, marginBottom: 2 }}>
            Category: Pokémon · Condition: Near mint
          </Text>
          <Text style={{ color: "#103b5c", fontSize: 14, marginBottom: 8 }}>
            Price: €124.00
          </Text>

          <View
            style={{
              padding: 10,
              borderRadius: 8,
              borderWidth: 1,
              borderColor: "#eef2f7",
              backgroundColor: "#f9fcff",
            }}
          >
            <Text style={{ color: "#4a647a", fontSize: 12, marginBottom: 4 }}>
              Offered by
            </Text>
            <View
              style={{
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <View>
                <Text style={{ color: "#103b5c", fontWeight: "600" }}>demo-user</Text>
                <Text style={{ color: "#7a8b9a", fontSize: 11 }}>
                  Tap to view seller trust profile
                </Text>
              </View>
              <Button title="View seller" onPress={loadTrust} />
            </View>

            {/* Seller trust section only visible after tapping "View seller" */}
            {renderSellerTrust()}
          </View>

          <Text style={{ marginTop: 8, color: "#7a8b9a", fontSize: 11 }}>
            Demo: in the real app you land on this screen from the main search results,
            and can then drill into the seller profile for more trust details.
          </Text>
        </View>
      </View>
    );
  };

  const renderSell = function () {
    return (
      <View style={{ gap: 12 }}>
        <View
          style={{
            padding: 16,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#dde6ee",
            backgroundColor: "#ffffff",
          }}
        >
          <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4, color: "#103b5c" }}>
            Sell an item
          </Text>
          <Text style={{ color: "#4a647a" }}>
            Full flow: snap your item → QuickScan fills details → pricing guidance →
            publish listing. Seller trust is attached to your seller profile so buyers can
            check you just like on Amazon or Vinted.
          </Text>
        </View>

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
            MVP placeholder
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 6 }}>
            For now, this screen is only explanatory. Later you will:
          </Text>
          <Text style={{ color: "#4a647a", fontSize: 13 }}>
            • Take photos or upload screenshots{"\n"}
            • Let the model prefill title, category and condition{"\n"}
            • Get price guidance from the same pricing engine{"\n"}
            • Publish the listing to the marketplace
          </Text>
          <Text style={{ marginTop: 8, color: "#7a8b9a", fontSize: 11 }}>
            Seller trust card lives on your seller profile, not directly on this tab.
          </Text>
        </View>
      </View>
    );
  };

  let content: JSX.Element;
  if (tab === "chat") {
    content = renderChat();
  } else if (tab === "search") {
    content = renderSearch();
  } else {
    content = renderSell();
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: "#e6f7fb" }}
      contentContainerStyle={{ paddingHorizontal: 16, paddingTop: 32, paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 26, fontWeight: "700", marginBottom: 16, color: "#103b5c" }}>
        Marketplace
      </Text>

      {renderTabs()}
      {content}

      <Text style={{ marginTop: 16, color: "#7a8b9a", fontSize: 12 }}>
        Demo mode: chat rooms are static; listings and seller trust use backend stubs.
        Trust is only shown inside the listing via the seller profile, not as a global card.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Marketplace tab updated with topic chatrooms and listing-based seller trust."
