import React, { useMemo } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

function tryLoadCategories(): Array<{ id: string; name: string; description?: string }> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require("@/data/categories");
    const list = (mod?.CATEGORIES ?? mod?.categories ?? mod?.DEFAULT_CATEGORIES) as any[];
    if (Array.isArray(list)) return list;
  } catch {}
  return [
    { id: "pokemon", name: "Pokémon" },
    { id: "gunpla", name: "Gunpla" },
    { id: "warhammer", name: "Warhammer" },
    { id: "lego", name: "LEGO" },
    { id: "diecast", name: "Diecast" },
  ];
}

const DARK = {
  BG: "#0f172a",
  CARD: "#020617",
  BORDER: "#1f2933",
  TEXT: "#e5e7eb",
  MUTED: "#9ca3af",
  PRIMARY: "#0ea5e9",
};

export default function CategoriesHub() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const cats = useMemo(() => tryLoadCategories(), []);

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: DARK.BG }]} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={[styles.container, { paddingTop: Math.max(12, insets.top), paddingBottom: 24 }]}>
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={[styles.iconBtn, { borderColor: DARK.BORDER }]}>
            <Ionicons name="chevron-back" size={18} color={DARK.MUTED} />
          </Pressable>
          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={[styles.headerTitle, { color: DARK.TEXT }]}>Categories</Text>
            <Text style={[styles.headerSub, { color: DARK.MUTED }]}>Brandstore-style storefronts</Text>
          </View>
          <View style={{ width: 36 }} />
        </View>

        {cats.map((c) => (
          <Pressable
            key={c.id}
            onPress={() => router.push({ pathname: "/categories/[categoryId]" as any, params: { categoryId: c.id } } as any)}
            style={[styles.card, { backgroundColor: DARK.CARD, borderColor: DARK.BORDER }]}
          >
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <Text style={[styles.title, { color: DARK.TEXT }]}>{c.name ?? c.id}</Text>
              <Ionicons name="chevron-forward" size={18} color={DARK.MUTED} />
            </View>
            {!!c.description && <Text style={[styles.body, { color: DARK.MUTED }]} numberOfLines={2}>{c.description}</Text>}
          </Pressable>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { backgroundColor: '#FFFFFF', flex: 1},
  container: { backgroundColor: '#FFFFFF', paddingHorizontal: 16},
  headerRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  iconBtn: { width: 36, height: 36, borderRadius: 999, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  headerTitle: { fontSize: 16, fontWeight: "900" },
  headerSub: { marginTop: 2, fontSize: 11, fontWeight: "600" },
  card: { borderRadius: 16, borderWidth: 1, padding: 12, marginBottom: 10 },
  title: { fontSize: 14, fontWeight: "900" },
  body: { marginTop: 8, fontSize: 12, lineHeight: 17, fontWeight: "600" },
});
