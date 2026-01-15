import React, { useMemo } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

const WHITE = "#FFFFFF";
const NAVY = "#0C2233";
const MUTED = "#5B6B78";
const BORDER = "#E6EEF3";
const TIFF = "#38D6C7";

type Row = {
  id: string;
  name: string;
  score: number;         // “collector credibility / activity” style score
  categories: number;
  items: number;
  portfolio: number;
  badge?: "gold" | "silver" | "platinum";
};

function fmtEUR(n: number) {
  try {
    return new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
  } catch {
    return `€${Math.round(n)}`;
  }
}

export default function TwitchLeaderboard() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const rows = useMemo<Row[]>(
    () => [
      { id: "rune", name: "Rune", score: 94, categories: 2, items: 312, portfolio: 12400, badge: "platinum" },
      { id: "mini", name: "Mini", score: 88, categories: 1, items: 88, portfolio: 15300, badge: "gold" },
      { id: "aurora", name: "Aurora", score: 81, categories: 2, items: 141, portfolio: 8600, badge: "silver" },
    ].sort((a, b) => b.score - a.score),
    []
  );

  return (
    <SafeAreaView style={[styles.safe, { paddingTop: Math.max(8, insets.top) }]} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={[styles.container, { paddingBottom: 28 }]}>
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={styles.iconBtn} accessibilityRole="button">
            <Ionicons name="chevron-back" size={18} color={NAVY} />
          </Pressable>

          <View style={{ flex: 1 }}>
            <Text style={styles.h1}>Twitch leaderboard</Text>
            <Text style={styles.meta}>Collectors with consistent activity + trusted portfolio signals (mock).</Text>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.h2}>How it helps streamers</Text>
          <Text style={styles.body}>
            Find credible collectors to collab with, discover category experts, and surface “trusted comps” sources for live discussions.
          </Text>
          <View style={styles.pills}>
            <View style={styles.pill}><Text style={styles.pillText}>Credibility</Text></View>
            <View style={styles.pill}><Text style={styles.pillText}>Category focus</Text></View>
            <View style={styles.pill}><Text style={styles.pillText}>Portfolio depth</Text></View>
          </View>
        </View>

        <Text style={[styles.h2, { marginTop: 12, marginBottom: 8 }]}>Top collectors</Text>

        {rows.map((r, idx) => (
          <Pressable
            key={r.id}
            onPress={() => router.push({ pathname: "/users-card/[userId]" as any, params: { userId: r.id } } as any)}
            style={styles.row}
            accessibilityRole="button"
          >
            <View style={styles.rank}>
              <Text style={styles.rankText}>{idx + 1}</Text>
            </View>

            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>
                {r.name}{" "}
                {r.badge ? (
                  <Text style={{ color: TIFF }}>
                    {r.badge === "platinum" ? "◆" : r.badge === "gold" ? "▲" : "●"}
                  </Text>
                ) : null}
              </Text>
              <Text style={styles.meta} numberOfLines={1}>
                {r.categories} categories • {r.items} items • portfolio {fmtEUR(r.portfolio)}
              </Text>
            </View>

            <View style={{ alignItems: "flex-end" }}>
              <Text style={styles.score}>{r.score}</Text>
              <Text style={styles.meta}>Score</Text>
            </View>

            <Ionicons name="chevron-forward" size={16} color={MUTED} />
          </Pressable>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: WHITE },
  container: { paddingHorizontal: 16 },

  // Typography (match Items baseline)
  h1: { fontSize: 18, fontWeight: "900", color: NAVY },
  h2: { fontSize: 14, fontWeight: "900", color: NAVY },
  body: { fontSize: 12, fontWeight: "600", color: NAVY, lineHeight: 17 },
  meta: { fontSize: 11, fontWeight: "600", color: MUTED, marginTop: 2 },

  headerRow: { flexDirection: "row", alignItems: "flex-start", gap: 10, marginBottom: 12 },
  iconBtn: {
    width: 38, height: 38, borderRadius: 12, borderWidth: 1, borderColor: BORDER,
    alignItems: "center", justifyContent: "center", backgroundColor: WHITE,
  },

  card: { backgroundColor: WHITE, borderColor: BORDER, borderWidth: 1, borderRadius: 14, padding: 12 },

  pills: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  pill: { paddingVertical: 8, paddingHorizontal: 10, borderRadius: 999, borderWidth: 1, borderColor: BORDER, backgroundColor: "rgba(56,214,199,0.15)" },
  pillText: { fontSize: 11, fontWeight: "900", color: NAVY },

  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: BORDER,
    backgroundColor: WHITE,
    marginBottom: 10,
  },

  rank: { width: 30, height: 30, borderRadius: 10, backgroundColor: "rgba(56,214,199,0.25)", alignItems: "center", justifyContent: "center" },
  rankText: { fontSize: 12, fontWeight: "900", color: NAVY },

  rowTitle: { fontSize: 13, fontWeight: "900", color: NAVY },
  score: { fontSize: 16, fontWeight: "900", color: NAVY },
});
