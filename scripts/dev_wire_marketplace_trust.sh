#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CANDIDATES=("app/(tabs)/marketplace.tsx" "app/marketplace.tsx")
TARGET=""

for f in "${CANDIDATES[@]}"; do
  if [ -f "$f" ]; then
    TARGET="$f"
    break
  fi
done

if [ -z "$TARGET" ]; then
  echo "No Marketplace screen found; creating app/(tabs)/marketplace.tsx."
  mkdir -p "app/(tabs)"
  TARGET="app/(tabs)/marketplace.tsx"
fi

if [ -f "$TARGET" ]; then
  cp "$TARGET" "$TARGET.bak.trust.$(date +%s)"
fi

cat <<'EOF' > "$TARGET"
import React, { useEffect, useState } from "react";
import { View, Text, ScrollView, ActivityIndicator } from "react-native";

const API_BASE = "http://51.21.210.195:8000"; // keep in sync with src/api/config.ts

async function get(path: string) {
  const res = await fetch(\`\${API_BASE}\${path}\`);
  if (!res.ok) throw new Error(\`GET \${path} failed (\${res.status})\`);
  return res.json();
}

async function post(path: string, body: any = {}) {
  const res = await fetch(\`\${API_BASE}\${path}\`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(\`POST \${path} failed (\${res.status})\`);
  return res.json();
}

export default function MarketplaceScreen() {
  const [trust, setTrust] = useState<any | null>(null);
  const [screenshotIntel, setScreenshotIntel] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [t, s] = await Promise.all([
          get("/marketplace/trust2/seller/demo-user"),
          post("/screenshot-intel/analyze", {
            screenshot_id: "demo-shot-1",
            source_hint: "ebay",
          }),
        ]);
        setTrust(t);
        setScreenshotIntel(s);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <ScrollView
      style={{ flex: 1, padding: 16 }}
      contentContainerStyle={{ paddingBottom: 32 }}
    >
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>
        Marketplace (Trust Demo)
      </Text>

      {loading && (
        <View style={{ marginTop: 16 }}>
          <ActivityIndicator />
          <Text style={{ marginTop: 8 }}>Loading trust data…</Text>
        </View>
      )}

      {error && (
        <Text style={{ marginTop: 16, color: "red" }}>
          Error: {error}
        </Text>
      )}

      {trust && (
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
            Seller Trust (demo-user)
          </Text>
          <Text selectable style={{ fontFamily: "monospace" }}>
            {JSON.stringify(trust, null, 2)}
          </Text>
        </View>
      )}

      {screenshotIntel && (
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
            Screenshot Intel
          </Text>
          <Text selectable style={{ fontFamily: "monospace" }}>
            {JSON.stringify(screenshotIntel, null, 2)}
          </Text>
        </View>
      )}
    </ScrollView>
  );
}
EOF

echo "Patched $TARGET with Marketplace Trust + Screenshot Intel demo."
