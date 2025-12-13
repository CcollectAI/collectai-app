#!/usr/bin/env bash
set -euo pipefail

TS=$(date +%Y%m%d_%H%M%S)

# If a disabled twitch file exists, re-enable it
if [ -f "app/twitch.tsx.disabled" ]; then
  cp "app/twitch.tsx.disabled" "app/twitch.tsx.bak_${TS}"
  mv "app/twitch.tsx.disabled" "app/twitch.tsx"
  echo "✅ Re-enabled app/twitch.tsx from .disabled"
fi

# Ensure app/twitch.tsx exists + has default export
if [ ! -f "app/twitch.tsx" ]; then
  cat > "app/twitch.tsx" <<'TSX'
import React from "react";
import { View, Text, StyleSheet } from "react-native";

export default function TwitchScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Twitch Overview</Text>
      <Text style={styles.sub}>Route is wired. Next: render your real Twitch overview content here.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 16 },
  title: { fontSize: 20, fontWeight: "800" },
  sub: { marginTop: 8, color: "#475569" },
});
TSX
  echo "✅ Created app/twitch.tsx (wired route)."
else
  # check for default export; if missing, wrap minimal default export
  node - <<'NODE'
const fs=require("fs");
const f="app/twitch.tsx";
const s=fs.readFileSync(f,"utf8");
const has=/export\s+default\s+function|export\s+default\s*\(/.test(s);
if(has){
  console.log("✅ app/twitch.tsx has default export.");
  process.exit(0);
}
console.log("⚠️ app/twitch.tsx missing default export; adding minimal wrapper at bottom.");
fs.writeFileSync(f, s + "\n\nexport default function TwitchRouteShim(){ return null; }\n");
NODE
fi

echo "🛑 SANITY CHECK NOW: npx expo start --tunnel"
