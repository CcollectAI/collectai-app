import React, { useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

import { getUserById } from "@/data/users";
import { getCategoryById } from "@/data/categories";
import { getConnectionStatus, getLocalUserId } from "@/lib/connections";

type AnyUser = {
  id: string;
  name?: string;
  handle?: string;
  bio?: string;
  color?: string;
  favoriteCategoryId?: string;
};

type PortfolioSummary = {
  totalValueEUR: number;
  items: number;
  collections: number;
  categories: number;
  topCategories: Array<{ id: string; label: string; sharePct: number }>;
  highlights: string[];
};

const DARK = {
  BG: "#0f172a",
  CARD: "#020617",
  BORDER: "#1f2933",
  TEXT: "#e5e7eb",
  MUTED: "#9ca3af",
  PRIMARY: "#0ea5e9",
  CHIP: "rgba(14,165,233,0.14)",
};

const LIGHT = {
  BG: "#f4f4f5",
  CARD: "#ffffff",
  BORDER: "#e5e7eb",
  TEXT: "#0f172a",
  MUTED: "#6b7280",
  PRIMARY: "#0ea5e9",
  CHIP: "rgba(14,165,233,0.10)",
};

function initials(name?: string) {
  const safe = (name ?? "").trim();
  if (!safe) return "?";
  return safe
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function safeDecode(x?: string | string[]) {
  const raw = Array.isArray(x) ? x[0] : x;
  return raw ? decodeURIComponent(String(raw)) : "";
}

function tryLoadAllUsers(): AnyUser[] {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require("@/data/users");
    const list = (mod?.USERS ?? mod?.users ?? mod?.DEFAULT_USERS) as AnyUser[] | undefined;
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

/**
 * Professional long-term shape, but safe + mock-filled for now.
 * Replace later with real computed stats from your portfolio store / API.
 */
function mockSummaryForUser(user: AnyUser | undefined): PortfolioSummary {
  const fav = user?.favoriteCategoryId ?? "pokemon";
  const favCat = getCategoryById(fav as any) as any;

  // Stable mock numbers (so UI looks real, doesn’t show “—”)
  const base = Math.abs((user?.id ?? "x").split("").reduce((a, c) => a + c.charCodeAt(0), 0));
  const items = 42 + (base % 58);
  const collections = 6 + (base % 8);
  const categories = 3 + (base % 5);
  const totalValueEUR = 1850 + (base % 9000);

  const topCategories = [
    { id: fav, label: favCat?.name ?? fav.toUpperCase(), sharePct: 52 },
    { id: "lego", label: "LEGO", sharePct: 18 },
    { id: "diecast", label: "Diecast", sharePct: 12 },
  ].slice(0, Math.min(3, categories));

  const highlights = [
    "Consistent collector activity (mock)",
    "Prefers high-signal comps + clean provenance",
    "Top category focus is stable over time (mock)",
  ];

  return { totalValueEUR, items, collections, categories, topCategories, highlights };
}

const MetricTile: React.FC<{
  label: string;
  value: string;
  icon: keyof typeof Ionicons.glyphMap;
  theme: any;
}> = ({ label, value, icon, theme }) => (
  <View style={[styles.metricTile, { borderColor: theme.BORDER, backgroundColor: theme.CARD }]}>
    <View style={styles.metricTop}>
      <Ionicons name={icon} size={16} color={theme.MUTED} />
      <Text style={[styles.metricLabel, { color: theme.MUTED }]} numberOfLines={1}>
        {label}
      </Text>
    </View>
    <Text style={[styles.metricValue, { color: theme.TEXT }]} numberOfLines={1}>
      {value}
    </Text>
  </View>
);

const SimilarCollectorCard: React.FC<{ u: AnyUser; theme: any; onPress: () => void }> = ({ u, theme, onPress }) => {
  const name = u.name ?? "Collector";
  const handle = u.handle ? `@${u.handle}` : "";
  return (
    <Pressable onPress={onPress} style={[styles.simCard, { backgroundColor: theme.CARD, borderColor: theme.BORDER, opacity: chatUnlocked ? 1 : 0.55 }]}>
      <View style={[styles.simAvatar, { backgroundColor: u.color ?? theme.CHIP }]}>
        <Text style={styles.simAvatarText}>{initials(name)}</Text>
      </View>
      <Text style={[styles.simName, { color: theme.TEXT }]} numberOfLines={1}>
        {name}
      </Text>
      {!!handle && (
        <Text style={[styles.simMeta, { color: theme.MUTED }]} numberOfLines={1}>
          {handle}
        </Text>
      )}
      <View style={{ marginTop: 8, flexDirection: "row", alignItems: "center", gap: 6 }}>
        <Ionicons name="sparkles-outline" size={14} color={theme.MUTED} />
        <Text style={[styles.simMeta, { color: theme.MUTED }]} numberOfLines={1}>
          Similar collector
        </Text>
      </View>
    </Pressable>
  );
};

export default function UserProfileCardScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const { userId } = useLocalSearchParams<{ userId?: string | string[] }>();
  const userIdStr = safeDecode(userId);

  const [isDark, setIsDark] = useState(true);

  const me = getLocalUserId();
  const connStatus = useMemo(() => (userIdStr ? getConnectionStatus(me, userIdStr) : "none"), [me, userIdStr]);
  const chatUnlocked = connStatus === "connected";

  const theme = isDark ? DARK : LIGHT;

  const user = useMemo(() => (userIdStr ? (getUserById(userIdStr as any) as AnyUser | undefined) : undefined), [userIdStr]);
  const summary = useMemo(() => mockSummaryForUser(user), [user]);

  const allUsers = useMemo(() => tryLoadAllUsers(), []);
  const similar = useMemo(() => {
    const pool = allUsers.filter((x) => x?.id && x.id !== userIdStr);
    const fav = user?.favoriteCategoryId;
    const ranked = fav ? [...pool.filter((u) => u.favoriteCategoryId === fav), ...pool.filter((u) => u.favoriteCategoryId !== fav)] : pool;
    return ranked.slice(0, 10);
  }, [allUsers, userIdStr, user?.favoriteCategoryId]);

  const name = user?.name ?? "Collector";
  const handle = user?.handle ? `@${user.handle}` : "";
  const bio = user?.bio?.trim() || "Professional collector overview — portfolio composition, category focus, and community presence.";

  const favCategory = user?.favoriteCategoryId ? (getCategoryById(user.favoriteCategoryId as any) as any) : undefined;

  const valueStr = new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(
    summary.totalValueEUR
  );

  const openLeaderboard = () => router.push("/leaderboard" as any);

  const openConnect = () => {
    if (!userIdStr) return;
    router.push({ pathname: "/connect/[userId]" as any, params: { userId: userIdStr } } as any);
  };

  const openChat = () => {
    if (!userIdStr) return;
    if (!chatUnlocked) return;
    router.push({ pathname: "/chat/dm/[userId]" as any, params: { userId: userIdStr } } as any);
  };

  const openUserCard = (id: string) => {
    if (!id) return;
    router.push({ pathname: "/users-card/[userId]" as any, params: { userId: id } } as any);
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: theme.BG }]} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={[styles.container, { paddingTop: Math.max(12, insets.top), paddingBottom: 26 }]}>
        {/* Header */}
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={[styles.iconBtn, { borderColor: theme.BORDER }]}>
            <Ionicons name="chevron-back" size={18} color={theme.MUTED} />
          </Pressable>

          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={[styles.headerTitle, { color: theme.TEXT }]} numberOfLines={1}>
              Collector Profile
            </Text>
            <Text style={[styles.headerSub, { color: theme.MUTED }]} numberOfLines={1}>
              {handle || userIdStr || "unknown"}
            </Text>
          </View>

          <Pressable onPress={() => setIsDark((v) => !v)} style={[styles.iconBtn, { borderColor: theme.BORDER }]}>
            <Ionicons name={isDark ? "sunny-outline" : "moon-outline"} size={18} color={theme.MUTED} />
          </Pressable>

          <Pressable onPress={openLeaderboard} style={[styles.iconBtn, { borderColor: theme.BORDER, marginLeft: 8 }]}>
            <Ionicons name="trophy-outline" size={18} color={theme.MUTED} />
          </Pressable>
        </View>

        {/* Hero card */}
        <View style={[styles.card, { backgroundColor: theme.CARD, borderColor: theme.BORDER, opacity: chatUnlocked ? 1 : 0.55 }]}>
          <View style={styles.heroRow}>
            <View style={[styles.avatar, { backgroundColor: user?.color ?? theme.CHIP }]}>
              <Text style={styles.avatarText}>{initials(name)}</Text>
            </View>

            <View style={{ flex: 1 }}>
              <Text style={[styles.title, { color: theme.TEXT }]} numberOfLines={1}>
                {name}
              </Text>

              <View style={styles.chipRow}>
                <View style={[styles.chip, { backgroundColor: theme.CHIP, borderColor: theme.BORDER }]}>
                  <Ionicons name="shield-checkmark-outline" size={12} color={theme.PRIMARY} />
                  <Text style={[styles.chipText, { color: theme.TEXT }]}>Verified</Text>
                </View>

                <View style={[styles.chip, { backgroundColor: theme.CARD, borderColor: theme.BORDER, opacity: chatUnlocked ? 1 : 0.55 }]}>
                  <Ionicons name="pricetag-outline" size={12} color={theme.MUTED} />
                  <Text style={[styles.chipTextMuted, { color: theme.MUTED }]}>
                    {favCategory?.name ?? "Multi-category"}
                  </Text>
                </View>
              </View>
            </View>
          </View>

          <Text style={[styles.body, { color: theme.MUTED }]}>{bio}</Text>

          {/* Actions */}
          <View style={styles.ctaRow}>
            <Pressable onPress={openConnect} style={[styles.primaryBtn, { backgroundColor: theme.PRIMARY, borderColor: theme.BORDER }]}>
              <Ionicons name="person-add-outline" size={16} color="#fff" style={{ marginRight: 6 }} />
              <Text style={styles.primaryText}>Follow</Text>
            </Pressable>

            <Pressable
              onPress={openChat}
              disabled={!chatUnlocked}
              style={[
                styles.secondaryBtn,
                { backgroundColor: theme.CARD, borderColor: theme.BORDER, opacity: chatUnlocked ? 1 : 0.55 },
              ]}
            >
              <Ionicons name={chatUnlocked ? "chatbubble-ellipses-outline" : "lock-closed-outline"} size={16} color={theme.MUTED} style={{ marginRight: 6 }} />
              <Text style={[styles.secondaryText, { color: theme.MUTED }]}>{chatUnlocked ? "Chat" : "Chat locked"}</Text>
            </Pressable>
          </View>
        </View>

        {/* Portfolio summary (professional) */}
        <View style={[styles.card, { backgroundColor: theme.CARD, borderColor: theme.BORDER, opacity: chatUnlocked ? 1 : 0.55 }]}>
          <View style={styles.sectionHead}>
            <Text style={[styles.sectionTitle, { color: theme.TEXT }]}>Portfolio summary</Text>
            <Text style={[styles.sectionHint, { color: theme.MUTED }]}>Mocked now, wired to real data later</Text>
          </View>

          <View style={styles.metricsGrid}>
            <MetricTile theme={theme} label="Total value" value={valueStr} icon="cash-outline" />
            <MetricTile theme={theme} label="Items" value={String(summary.items)} icon="albums-outline" />
            <MetricTile theme={theme} label="Collections" value={String(summary.collections)} icon="cube-outline" />
            <MetricTile theme={theme} label="Categories" value={String(summary.categories)} icon="grid-outline" />
          </View>

          <View style={[styles.innerCard, { borderColor: theme.BORDER, backgroundColor: theme.BG }]}>
            <Text style={[styles.innerTitle, { color: theme.TEXT }]}>Top categories</Text>
            {summary.topCategories.map((c) => (
              <View key={c.id} style={styles.rowBetween}>
                <Text style={[styles.rowLeft, { color: theme.TEXT }]} numberOfLines={1}>
                  {c.label}
                </Text>
                <Text style={[styles.rowRight, { color: theme.MUTED }]}>{c.sharePct}%</Text>
              </View>
            ))}
          </View>

          <View style={[styles.innerCard, { borderColor: theme.BORDER, backgroundColor: theme.BG, marginTop: 10 }]}>
            <Text style={[styles.innerTitle, { color: theme.TEXT }]}>Signals</Text>
            {summary.highlights.slice(0, 3).map((h) => (
              <View key={h} style={{ flexDirection: "row", gap: 8, marginTop: 8, alignItems: "center" }}>
                <Ionicons name="checkmark-circle-outline" size={16} color={theme.PRIMARY} />
                <Text style={[styles.bodyTight, { color: theme.MUTED }]}>{h}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Similar collectors carousel banner (bottom) */}
        <View style={[styles.card, { backgroundColor: theme.CARD, borderColor: theme.BORDER, opacity: chatUnlocked ? 1 : 0.55 }]}>
          <View style={styles.sectionHead}>
            <Text style={[styles.sectionTitle, { color: theme.TEXT }]}>Similar collectors</Text>
            <Text style={[styles.sectionHint, { color: theme.MUTED }]}>Swipe to explore</Text>
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingTop: 10, paddingBottom: 2 }}>
            {similar.length === 0 ? (
              <Text style={[styles.body, { color: theme.MUTED }]}>No similar collectors yet.</Text>
            ) : (
                            <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={{ paddingTop: 10, paddingBottom: 2, paddingRight: 12 }}
                style={{ marginTop: 6 }}
              >
                {similar.map((u) => (
                  <Pressable
                    key={u.id}
                    onPress={() => router.push({ pathname: "/users-card/[userId]" as any, params: { userId: String(u.id) } } as any)}
                    style={[
                      styles.similarCard,
                      { backgroundColor: theme.CARD, borderColor: theme.BORDER, marginRight: 10, width: 220 },
                    ]}
                    accessibilityRole="button"
                  >
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                      <View style={[styles.avatar, { backgroundColor: u.color ?? "rgba(14,165,233,0.35)" }]}>
                        <Text style={[styles.avatarText, { color: "#fff" }]}>{(u.name ?? "?").slice(0, 2).toUpperCase()}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.personName, { color: theme.TEXT }]} numberOfLines={1}>
                          {u.name ?? "Collector"}
                        </Text>
                        <Text style={[styles.personMeta, { color: theme.MUTED }]} numberOfLines={1}>
                          Similar category focus • mock
                        </Text>
                      </View>
                      <Ionicons name="chevron-forward" size={16} color={theme.MUTED} />
                    </View>
                  </Pressable>
                ))}
              </ScrollView>
            )}
          </ScrollView>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { paddingHorizontal: 16 },

  headerRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  iconBtn: { width: 36, height: 36, borderRadius: 999, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  headerTitle: { fontSize: 16, fontWeight: "900" },
  headerSub: { marginTop: 2, fontSize: 11, fontWeight: "600" },

  card: { borderRadius: 16, borderWidth: 1, padding: 12, marginBottom: 10 },

  heroRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  avatar: { width: 56, height: 56, borderRadius: 28, alignItems: "center", justifyContent: "center" },
  avatarText: { color: "#fff", fontSize: 16, fontWeight: "900" },
  title: { fontSize: 16, fontWeight: "900" },

  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 6 },
  chip: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 6, paddingHorizontal: 10, borderRadius: 999, borderWidth: 1 },
  chipText: { fontSize: 12, fontWeight: "800" },
  chipTextMuted: { fontSize: 12, fontWeight: "800" },

  body: { marginTop: 10, fontSize: 12, lineHeight: 17, fontWeight: "600" },
  bodyTight: { fontSize: 12, lineHeight: 16, fontWeight: "600", flex: 1 },

  ctaRow: { marginTop: 12, flexDirection: "row", alignItems: "center", gap: 8 },
  primaryBtn: { flex: 1, paddingVertical: 10, borderRadius: 12, borderWidth: 1, alignItems: "center", justifyContent: "center", flexDirection: "row" },
  primaryText: { color: "#fff", fontSize: 12, fontWeight: "900" },
  secondaryBtn: { paddingVertical: 10, paddingHorizontal: 10, borderRadius: 12, borderWidth: 1, alignItems: "center", justifyContent: "center", flexDirection: "row" },
  secondaryText: { fontSize: 12, fontWeight: "800" },

  sectionHead: {},
  sectionTitle: { fontSize: 13, fontWeight: "900" },
  sectionHint: { marginTop: 6, fontSize: 11, fontWeight: "600" },

  metricsGrid: { marginTop: 12, flexDirection: "row", flexWrap: "wrap", gap: 10 },
  metricTile: { width: "48%", borderWidth: 1, borderRadius: 14, padding: 10 },
  metricTop: { flexDirection: "row", alignItems: "center", gap: 8 },
  metricLabel: { fontSize: 11, fontWeight: "700" },
  metricValue: { marginTop: 6, fontSize: 14, fontWeight: "900" },

  innerCard: { borderWidth: 1, borderRadius: 14, padding: 10, marginTop: 12 },
  innerTitle: { fontSize: 12, fontWeight: "900" },
  rowBetween: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 8 },
  rowLeft: { fontSize: 12, fontWeight: "800", flex: 1, paddingRight: 10 },
  rowRight: { fontSize: 12, fontWeight: "800" },

  simCard: { width: 200, borderRadius: 16, borderWidth: 1, padding: 12, marginRight: 10 },
  simAvatar: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center" },
  simAvatarText: { color: "#fff", fontSize: 12, fontWeight: "900" },
  simName: { marginTop: 10, fontSize: 12, fontWeight: "900" },
  simMeta: { marginTop: 2, fontSize: 11, fontWeight: "700" },
});
