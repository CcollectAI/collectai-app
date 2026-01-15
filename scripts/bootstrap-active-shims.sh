#!/usr/bin/env bash
set -euo pipefail

mkfile() {
  local path="$1"
  shift
  if [ -f "$path" ]; then
    echo "SKIP (exists): $path"
    return 0
  fi
  mkdir -p "$(dirname "$path")"
  cat > "$path" <<'EOF'
EOF
  # append content passed via stdin
  cat >> "$path"
  echo "CREATED: $path"
}

# --- ui/typography (used by tabs/index + tabs/events) ---
mkfile "src/ui/typography.ts" <<'EOF'
export const typography = {
  title: { fontSize: 18, fontWeight: "900" as const },
  body: { fontSize: 14, fontWeight: "700" as const },
  muted: { fontSize: 12, fontWeight: "700" as const, opacity: 0.7 },
};
EOF

# --- state/watchlistStore (tabs/index uses useWatchlist) ---
mkfile "src/state/watchlistStore.ts" <<'EOF'
import { useMemo, useState } from "react";

export type WatchlistItem = { id: string; title?: string; value_eur?: number };

export function useWatchlist() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  return useMemo(() => ({
    items,
    add: (it: WatchlistItem) => setItems((p) => (p.some(x => x.id === it.id) ? p : [it, ...p])),
    remove: (id: string) => setItems((p) => p.filter((x) => x.id !== id)),
    clear: () => setItems([]),
  }), [items]);
}
EOF

# --- hooks/useAppTheme (tabs/items + tabs/search + demos) ---
mkfile "src/hooks/useAppTheme.ts" <<'EOF'
export function useAppTheme() {
  return {
    colors: {
      bg: "#E6FFFA",
      card: "#FFFFFF",
      border: "rgba(12,34,51,0.10)",
      navy: "#0C2233",
      text: "#0C2233",
      muted: "rgba(12,34,51,0.62)",
      tiffany: "#38D6C7",
      success: "#0A7D4E",
      danger: "#B42318",
    },
    spacing: { xs: 6, sm: 10, md: 14, lg: 18, xl: 24 },
    radius: { sm: 8, md: 12, lg: 16, xl: 20 },
  };
}
EOF

# --- lib/supabaseClient (events/[id] imports default supabase) ---
mkfile "src/lib/supabaseClient.ts" <<'EOF'
type Stub = any;

/**
 * BOOT SHIM:
 * Real Supabase wiring can be restored later behind flags.
 * For now we export a minimal object with the methods used by current screens.
 */
const supabase: Stub = {
  auth: {
    getSession: async () => ({ data: { session: null } }),
  },
  from: () => ({
    select: async () => ({ data: [], error: null }),
    insert: async () => ({ data: null, error: null }),
    eq: () => ({ select: async () => ({ data: [], error: null }) }),
    order: () => ({ select: async () => ({ data: [], error: null }) }),
  }),
  storage: {
    from: () => ({
      upload: async () => ({ data: null, error: null }),
      getPublicUrl: () => ({ data: { publicUrl: "" } }),
    }),
  },
};

export default supabase;
export { supabase };
EOF

# --- data: categories/users/events (used by routes + tabs/events) ---
mkfile "src/data/categories.ts" <<'EOF'
export type Category = { id: string; label: string };
export const CATEGORIES: Category[] = [
  { id: "pokemon", label: "Pokémon" },
  { id: "funko", label: "Funko Pops" },
  { id: "diecast", label: "Diecast" },
];
export function getCategoryById(id: string) {
  return CATEGORIES.find((c) => c.id === id) ?? { id, label: id };
}
EOF

mkfile "src/data/users.ts" <<'EOF'
export type UserProfile = { id: string; name: string; handle?: string };
export const USER_PROFILES: UserProfile[] = [
  { id: "u1", name: "You", handle: "@you" },
];
export function getUserById(id: string) {
  return USER_PROFILES.find((u) => u.id === id) ?? { id, name: "Unknown" };
}
EOF

mkfile "src/data/events.ts" <<'EOF'
export type EventKind = "drop" | "release" | "meetup";
export type CollectorsEvent = {
  id: string;
  title: string;
  date: string; // ISO
  kind: EventKind;
  categoryId?: string;
};

export const EVENTS: CollectorsEvent[] = [
  { id: "e1", title: "Sample Drop", date: new Date().toISOString(), kind: "drop", categoryId: "pokemon" },
];
EOF

# --- services/collectorsClient (used by sets-to-complete + search-status) ---
mkfile "src/services/collectorsClient.ts" <<'EOF'
export type PortfolioItem = {
  id: string;
  title: string;
  categoryId?: string;
  value_eur?: number;
};

export async function getPortfolioItems(): Promise<PortfolioItem[]> {
  // BOOT SHIM: replace with real API later.
  return [
    { id: "i1", title: "Sample Item", categoryId: "pokemon", value_eur: 120 },
  ];
}
EOF

# --- utils/statusScoring (used by sets-to-complete + search-status) ---
mkfile "src/utils/statusScoring.ts" <<'EOF'
export type CollectionStatusInput = { id: string; title?: string };

export function scoreStatus(_input: CollectionStatusInput) {
  return { tier: "silver" as const, score: 0.5 };
}
EOF

# --- components required by ACTIVE tabs/screens ---
mkfile "src/components/CategoryPill.tsx" <<'EOF'
import React from "react";
import { View, Text, StyleSheet } from "react-native";

export function CategoryPill({ label }: { label: string }) {
  return (
    <View style={s.pill}>
      <Text style={s.text}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  pill: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(12,34,51,0.10)",
    backgroundColor: "rgba(56,214,199,0.18)",
  },
  text: { fontWeight: "900", fontSize: 12, color: "#0C2233" },
});
EOF

mkfile "src/components/SearchStatusPanel.tsx" <<'EOF'
import React from "react";
import { View, Text, StyleSheet } from "react-native";

export default function SearchStatusPanel() {
  return (
    <View style={s.card}>
      <Text style={s.title}>Search Status</Text>
      <Text style={s.sub}>Boot shim panel (replace later).</Text>
    </View>
  );
}
const s = StyleSheet.create({
  card: { backgroundColor: "#fff", borderWidth: 1, borderColor: "rgba(12,34,51,0.10)", padding: 14 },
  title: { fontWeight: "900", color: "#0C2233" },
  sub: { marginTop: 6, fontWeight: "700", opacity: 0.7 },
});
EOF

mkfile "src/components/AddImportCard.tsx" <<'EOF'
import React from "react";
import { View, Text, Pressable, StyleSheet, Alert } from "react-native";
import { Ionicons } from "@expo/vector-icons";

export function AddImportCard({ onPress }: { onPress?: () => void }) {
  return (
    <View style={s.card}>
      <Text style={s.title}>Import</Text>
      <Text style={s.sub}>Bring in items from CSV (mock for now).</Text>
      <Pressable
        accessibilityRole="button"
        onPress={() => (onPress ? onPress() : Alert.alert("Import", "Not wired yet (shim)."))}
        style={s.btn}
      >
        <Text style={s.btnText}>Open Import</Text>
        <Ionicons name="chevron-forward" size={16} color="#0C2233" />
      </Pressable>
    </View>
  );
}
const s = StyleSheet.create({
  card: { backgroundColor: "#fff", borderWidth: 1, borderColor: "rgba(12,34,51,0.10)", padding: 14 },
  title: { fontWeight: "900", color: "#0C2233" },
  sub: { marginTop: 6, fontWeight: "700", opacity: 0.7 },
  btn: { marginTop: 10, flexDirection: "row", gap: 8, alignItems: "center", alignSelf: "flex-start" },
  btnText: { fontWeight: "900", color: "#0C2233" },
});
EOF

mkfile "src/components/AddQuickScanLayoutPro.tsx" <<'EOF'
import React from "react";
import { View, Text, StyleSheet } from "react-native";

export function AddQuickScanLayoutPro() {
  return (
    <View style={s.wrap}>
      <Text style={s.title}>QuickScan</Text>
      <Text style={s.sub}>Boot shim layout (replace later).</Text>
    </View>
  );
}
const s = StyleSheet.create({
  wrap: { backgroundColor: "#fff", borderWidth: 1, borderColor: "rgba(12,34,51,0.10)", padding: 14 },
  title: { fontWeight: "900", color: "#0C2233" },
  sub: { marginTop: 6, fontWeight: "700", opacity: 0.7 },
});
EOF

# --- store/collectionStore (tabs/items) ---
mkfile "src/store/collectionStore.ts" <<'EOF'
export type ItemRow = {
  id: string;
  title: string;
  category?: string;
  image_url?: string | null;
  value_eur?: number | null;
};

export async function fetchCollectionItems(): Promise<ItemRow[]> {
  // BOOT SHIM
  return [
    { id: "i1", title: "Sample Item", category: "pokemon", value_eur: 120 },
  ];
}
EOF

echo "== bootstrap-active-shims done =="
