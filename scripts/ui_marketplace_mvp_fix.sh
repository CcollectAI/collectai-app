#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/marketplace.tsx"

if [ ! -f "$TARGET" ]; then
  echo "Marketplace screen not found at $TARGET, creating directory."
  mkdir -p "app/(tabs)"
fi

echo "Backing up $TARGET"
cp "$TARGET" "$TARGET.bak.marketplace_mvp_fix.$(date +%s)" || true

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

  const loadTrust = async function () {
    setTrustStatus("Loading seller trust…");
    setTrustParsed(null);
    setTrustRaw(null);
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
      setTrustStatus("Error while loading seller trust");
      const msg = e && e.message ? e.message : String(e);
      setTrustParsed(null);
      setTrustRaw(msg);
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
    return (
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
          Chat (coming later)
        </Text>
        <Text style={{ color: "#4a647a" }}>
          Real-time chat rooms and DMs between collectors will live here. For the MVP,
          this is just a placeholder.
        </Text>
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
            Marketplace search (mock)
          </Text>
          <Text style={{ color: "#4a647a" }}>
            In the full version, this would aggregate listings from multiple sources and
            show comps. For now it is a static placeholder.
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
          <Text style={{ fontSize: 16, fontWeight: "600", marginBottom: 4, color: "#103b5c" }}>
            Seller trust demo
          </Text>
          <Text style={{ color: "#4a647a", marginBottom: 8 }}>
            Tap below to load a demo seller trust profile from the backend. In the real
            app this will appear on the seller profile when you view a listing.
          </Text>
          <Button title="View demo seller trust" onPress={loadTrust} />

          {trustStatus && (
            <Text style={{ marginTop: 8, color: "#4a647a", fontSize: 12 }}>
              Status: {trustStatus}
            </Text>
          )}

          {trustParsed && (
            <View
              style={{
                marginTop: 8,
                padding: 8,
                borderRadius: 6,
                borderWidth: 1,
                borderColor: "#dde6ee",
                backgroundColor: "#f8fcff",
              }}
            >
              <Text style={{ fontWeight: "600", color: "#103b5c", marginBottom: 4 }}>
                Seller ID: {trustParsed.seller_id || "demo-user"}
              </Text>
              {typeof trustParsed.risk_score === "number" && (
                <Text style={{ color: "#4a647a" }}>
                  Risk score: {String(trustParsed.risk_score)}
                </Text>
              )}
              {trustParsed.flags && trustParsed.flags.length > 0 && (
                <Text style={{ color: "#4a647a", marginTop: 4 }}>
                  Flags: {trustParsed.flags.join(", ")}
                </Text>
              )}
              {trustParsed.notes && trustParsed.notes.length > 0 && (
                <Text style={{ color: "#4a647a", marginTop: 4 }}>
                  Notes: {trustParsed.notes.join(" • ")}
                </Text>
              )}
            </View>
          )}

          {trustRaw && (
            <View
              style={{
                marginTop: 8,
                padding: 8,
                borderRadius: 4,
                borderWidth: 1,
                borderColor: "#dde6ee",
                backgroundColor: "#f8fcff",
              }}
            >
              <Text
                style={{
                  fontFamily: "monospace",
                  fontSize: 11,
                  color: "#103b5c",
                }}
              >
                {trustRaw}
              </Text>
            </View>
          )}
        </View>
      </View>
    );
  };

  const renderSell = function () {
    return (
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
          Sell (mock form)
        </Text>
        <Text style={{ color: "#4a647a", marginBottom: 8 }}>
          This will become the main listing form: camera → prefill → pricing guidance →
          publish. For now, it is a placeholder section.
        </Text>
        <Text style={{ color: "#7a8b9a", fontSize: 12 }}>
          In a later iteration, we can also surface authenticity and anti-fraud hints
          powered by screenshot intel and provenance.
        </Text>
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
        Demo mode: chat, search and sell are mostly placeholders. Seller trust uses a real
        backend endpoint with stubbed risk data.
      </Text>
    </ScrollView>
  );
}
EOF

echo "Marketplace tab updated to MVP segmented layout with seller trust demo."
