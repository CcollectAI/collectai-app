import React, { useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

const WHITE = "#FFFFFF";
const NAVY = "#0C2233";
const MUTED = "#5B6B78";
const BORDER = "#E6EEF3";
const TIFF = "#38D6C7";

type StreamerRow = {
  id: string;
  name: string;
  focus: string[];
  estPortfolioValue: number;
  itemsTracked: number;
  streakDays: number;
  vibe: "pro" | "hype" | "collector";
};

const MOCK_STREAMERS: StreamerRow[] = [
  { id: "rune", name: "Rune", focus: ["Pokémon", "Lorcana"], estPortfolioValue: 12400, itemsTracked: 312, streakDays: 18, vibe: "pro" },
  { id: "aurora", name: "Aurora", focus: ["Warhammer", "Gunpla"], estPortfolioValue: 8600, itemsTracked: 141, streakDays: 9, vibe: "collector" },
  { id: "mini", name: "Mini", focus: ["Designer Toys"], estPortfolioValue: 15300, itemsTracked: 88, streakDays: 26, vibe: "hype" },
];

function fmtEUR(n: number) {
  try {
    return new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
  } catch {
    return `€${Math.round(n)}`;
  }
}

const Pill: React.FC<{ icon: keyof typeof Ionicons.glyphMap; label: string; onPress?: () => void }> = ({
  icon,
  label,
  onPress,
}) => (
  <Pressable onPress={onPress} style={styles.pill} accessibilityRole="button">
    <Ionicons name={icon} size={16} color={NAVY} />
    <Text style={styles.pillText}>{label}</Text>
  </Pressable>
);

export default function TwitchOverview() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  // Stub toggle for future (theme system later). Keeping white background per your request.
  const [mode] = useState<"light">("light");

  const top = useMemo(() => MOCK_STREAMERS[0], []);

  return (
    <SafeAreaView style={[styles.safe, { paddingTop: Math.max(8, insets.top), backgroundColor: WHITE }]} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={[styles.container, { paddingBottom: 28 }]}>
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.h1}>Twitch</Text>
            <Text style={styles.meta}>Tools for streamers + collectors — overlays, leaderboards, and trusted comps.</Text>
          </View>

          <Pressable
            onPress={() => router.push("/twitch-leaderboard")}
            style={styles.iconBtn}
            accessibilityRole="button"
            accessibilityLabel="Open Twitch leaderboard"
          >
            <Ionicons name="trophy-outline" size={18} color={NAVY} />
          </Pressable>
        </View>

        {/* Primary card: why a streamer cares */}
        <View style={styles.card}>
          <View style={styles.cardTopRow}>
            <View style={[styles.badge, { backgroundColor: TIFF }]}>
              <Ionicons name="radio-outline" size={18} color={NAVY} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.h2}>Make collecting stream-friendly</Text>
              <Text style={styles.body}>
                Show your collection value, track pack pulls and set completion, and share verified comps — without pausing the stream.
              </Text>
            </View>
          </View>

          <View style={styles.kpiRow}>
            <View style={styles.kpi}>
              <Text style={styles.kpiLabel}>Overlay Cards</Text>
              <Text style={styles.kpiValue}>Portfolio • Watchlist</Text>
            </View>
            <View style={styles.kpi}>
              <Text style={styles.kpiLabel}>Trust</Text>
              <Text style={styles.kpiValue}>Verified comps</Text>
            </View>
            <View style={styles.kpi}>
              <Text style={styles.kpiLabel}>Community</Text>
              <Text style={styles.kpiValue}>Friend-gated chat</Text>
            </View>
          </View>

          <View style={styles.pillRow}>
            <Pill icon="link-outline" label="Connect Twitch (mock)" onPress={() => {}} />
            <Pill icon="copy-outline" label="Copy overlay URL (mock)" onPress={() => {}} />
            <Pill icon="chatbubble-ellipses-outline" label="Chat commands (mock)" onPress={() => {}} />
          </View>
        </View>

        {/* “On stream” preview cards */}
        <Text style={[styles.h2, { marginTop: 10, marginBottom: 8 }]}>On-stream cards</Text>

        <View style={styles.gridRow}>
          <View style={[styles.card, styles.gridCard]}>
            <Text style={styles.kpiLabel}>Now Showing</Text>
            <Text style={styles.h2}>Portfolio Value</Text>
            <Text style={[styles.h1, { marginTop: 6 }]}>{fmtEUR(top.estPortfolioValue)}</Text>
            <Text style={styles.meta}>{top.itemsTracked} items • streak {top.streakDays}d</Text>
          </View>

          <View style={[styles.card, styles.gridCard]}>
            <Text style={styles.kpiLabel}>Watchlist</Text>
            <Text style={styles.h2}>Price Alerts</Text>
            <Text style={[styles.body, { marginTop: 6 }]}>
              Get pinged when a target item hits your range. Perfect for live “snipe” moments.
            </Text>
          </View>
        </View>

        {/* Featured streamers */}
        <Text style={[styles.h2, { marginTop: 12, marginBottom: 8 }]}>Featured streamers</Text>

        {MOCK_STREAMERS.map((s) => (
          <View key={s.id} style={styles.rowCard}>
            <View style={[styles.avatar, { backgroundColor: "rgba(56,214,199,0.25)" }]}>
              <Text style={styles.avatarText}>{s.name.slice(0, 2).toUpperCase()}</Text>
            </View>

            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>{s.name}</Text>
              <Text style={styles.meta} numberOfLines={1}>
                Focus: {s.focus.join(" • ")} • {s.itemsTracked} items
              </Text>
            </View>

            <View style={{ alignItems: "flex-end" }}>
              <Text style={styles.rowValue}>{fmtEUR(s.estPortfolioValue)}</Text>
              <Text style={styles.meta}>Streak {s.streakDays}d</Text>
            </View>
          </View>
        ))}

        <View style={[styles.card, { marginTop: 10 }]}>
          <Text style={styles.h2}>What streamers get next</Text>
          <Text style={styles.body}>
            • “Pull → Log” camera flow{"\n"}
            • Auto comps + price bands (q10/q50/q90){"\n"}
            • Stream overlay widgets (portfolio, watchlist, recent pulls){"\n"}
            • Creator pages (shareable, brand-store style category hubs)
          </Text>
        </View>
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
    width: 38,
    height: 38,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: BORDER,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: WHITE,
  },

  card: {
    backgroundColor: WHITE,
    borderColor: BORDER,
    borderWidth: 1,
    borderRadius: 14,
    padding: 12,
  },

  cardTopRow: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  badge: { width: 34, height: 34, borderRadius: 12, alignItems: "center", justifyContent: "center" },

  kpiRow: { flexDirection: "row", gap: 10, marginTop: 10 },
  kpi: { flex: 1, borderWidth: 1, borderColor: BORDER, borderRadius: 12, padding: 10 },
  kpiLabel: { fontSize: 11, fontWeight: "800", color: MUTED },
  kpiValue: { fontSize: 12, fontWeight: "900", color: NAVY, marginTop: 4 },

  pillRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10 },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: BORDER,
    backgroundColor: "rgba(56,214,199,0.15)",
  },
  pillText: { fontSize: 12, fontWeight: "900", color: NAVY },

  gridRow: { flexDirection: "row", gap: 10 },
  gridCard: { flex: 1 },

  rowCard: {
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

  avatar: { width: 36, height: 36, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  avatarText: { color: NAVY, fontSize: 12, fontWeight: "900" },

  rowTitle: { fontSize: 13, fontWeight: "900", color: NAVY },
  rowValue: { fontSize: 13, fontWeight: "900", color: NAVY },
});
