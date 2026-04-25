#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="app/(tabs)/add.tsx"

if [ -f "$TARGET" ]; then
  echo "Backing up $TARGET"
  cp "$TARGET" "$TARGET.bak.add_network_debug_v2.$(date +%s)"
else
  echo "Creating new Add screen at $TARGET"
  mkdir -p "app/(tabs)"
fi

cat <<'EOF' > "$TARGET"
import React, { useState } from "react";
import { View, Text, ScrollView, ActivityIndicator, Button } from "react-native";

const API_BASE = "http://51.21.210.195:8000";

async function quickscanDebug() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const res = await fetch(API_BASE + "/quickscan-advanced/single", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      signal: controller.signal,
    });
    clearTimeout(timeout);
    const text = await res.text();
    return { ok: res.ok, status: res.status, bodyText: text };
  } catch (e: any) {
    clearTimeout(timeout);
    throw new Error(e?.message ?? String(e));
  }
}

export default function AddScreen() {
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastStatus, setLastStatus] = useState<string>("idle");

  const handleQuickScan = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setLastStatus("started");
    try {
      const res = await quickscanDebug();
      const statusText =
        "done (status=" + String(res.status) + ", ok=" + (res.ok ? "true" : "false") + ")";
      setLastStatus(statusText);
      setResult(res.bodyText);
    } catch (e: any) {
      setLastStatus("error");
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView
      style={{ flex: 1, paddingHorizontal: 16, paddingTop: 32 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 8 }}>
        Add Item (Network Debug)
      </Text>
      <Text style={{ marginBottom: 8, color: "#555" }}>
        API_BASE: {API_BASE}
      </Text>
      <Text style={{ marginBottom: 16, color: "#555" }}>
        Last status: {lastStatus}
      </Text>

      <Button title="Test QuickScan endpoint" onPress={handleQuickScan} />

      {loading && (
        <View style={{ marginTop: 16, alignItems: "center" }}>
          <ActivityIndicator />
          <Text style={{ marginTop: 8 }}>Calling backend…</Text>
        </View>
      )}

      {error && (
        <Text style={{ marginTop: 16, color: "red" }}>
          Error: {error}
        </Text>
      )}

      {result && (
        <View
          style={{
            marginTop: 16,
            padding: 12,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: "#ddd",
          }}
        >
          <Text style={{ fontSize: 18, fontWeight: "600", marginBottom: 4 }}>
            Raw Response Body
          </Text>
          <Text selectable style={{ fontFamily: "monospace" }}>
            {result}
          </Text>
        </View>
      )}
    </ScrollView>
  );
}
EOF

echo "Replaced Add tab with template-free network debug QuickScan screen."
