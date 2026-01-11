import React, { useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { Link } from "expo-router";

/**
 * Projects Hub (Build & Paint)
 * - Ongoing vs Closed
 * - Professional cards with % completion and meta
 * - Routes into /projects/[id]
 */

type Step = { id: string; label: string; done: boolean };
type Project = {
  id: string;
  title: string;
  categoryId?: string; // optional, for future category overview linking
  kit?: string;
  status: "ongoing" | "closed";
  updatedAt: string; // ISO date string
  steps: Step[];
};

const THEME = {
  BG: "#E6FFFA",        // Tiffany-ish wash
  CARD: "#FFFFFF",
  BORDER: "rgba(12,34,51,0.10)",
  NAVY: "#0C2233",
  MUTED: "rgba(12,34,51,0.65)",
  ACCENT: "#38D6C7",    // Tiffany
  ACCENT_SOFT: "rgba(56,214,199,0.18)",
};

const MOCK_PROJECTS: Project[] = [
  {
    id: "p1",
    title: "Gunpla — RX-78 Build",
    categoryId: "gunpla",
    kit: "RG 1/144",
    status: "ongoing",
    updatedAt: "2026-01-11",
    steps: [
      { id: "s1", label: "Unbox & inventory parts", done: true },
      { id: "s2", label: "Build (core frame)", done: true },
      { id: "s3", label: "Build (armor)", done: false },
      { id: "s4", label: "Panel lining", done: false },
      { id: "s5", label: "Decals", done: false },
      { id: "s6", label: "Top coat", done: false },
      { id: "s7", label: "Photography + archive", done: false },
    ],
  },
  {
    id: "p2",
    title: "Warhammer — Squad Paint",
    categoryId: "warhammer",
    kit: "10 minis",
    status: "ongoing",
    updatedAt: "2026-01-10",
    steps: [
      { id: "s1", label: "Clean mold lines", done: true },
      { id: "s2", label: "Prime", done: true },
      { id: "s3", label: "Basecoats", done: false },
      { id: "s4", label: "Shade + highlights", done: false },
      { id: "s5", label: "Basing", done: false },
      { id: "s6", label: "Varnish", done: false },
    ],
  },
  {
    id: "p3",
    title: "LEGO — Display Rebuild",
    categoryId: "lego",
    kit: "Shelf set",
    status: "closed",
    updatedAt: "2025-12-28",
    steps: [
      { id: "s1", label: "Plan display layout", done: true },
      { id: "s2", label: "Rebuild", done: true },
      { id: "s3", label: "Lighting + photos", done: true },
    ],
  },
];

function pctDone(steps: Step[]) {
  const total = steps.length || 1;
  const done = steps.filter((s) => s.done).length;
  return Math.round((done / total) * 100);
}

function fmtUpdated(iso: string) {
  // keep it simple + stable (no Intl)
  return iso;
}

function ProgressBar({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <View style={styles.progressTrack}>
      <View style={[styles.progressFill, { width: `${v}%` }]} />
    </View>
  );
}

export default function BuildPaintProjectsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [tab, setTab] = useState<"ongoing" | "closed">("ongoing");

  const projects = useMemo(() => {
    const all = [...MOCK_PROJECTS].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
    return all.filter((p) => p.status === tab);
  }, [tab]);

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: THEME.BG }]} edges={["top", "left", "right"]}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{
          paddingTop: Math.max(12, insets.top),
          paddingBottom: 28,
          paddingHorizontal: 16,
        }}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <Pressable
            onPress={() => router.back()}
            accessibilityRole="button"
            style={[styles.iconBtn, { borderColor: THEME.BORDER }]}
          >
            <Ionicons name="chevron-back" size={18} color={THEME.NAVY} />
          </Pressable>

          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={[styles.hTitle, { color: THEME.NAVY }]} numberOfLines={1}>
              Build & Paint Projects
            </Text>
            <Text style={[styles.hSub, { color: THEME.MUTED }]} numberOfLines={1}>
              Track steps, notes, and completion.
            </Text>
          </View>

          <Pressable
            onPress={() => {}}
            accessibilityRole="button"
            style={[styles.iconBtn, { borderColor: THEME.BORDER }]}
          >
            <Ionicons name="add" size={18} color={THEME.NAVY} />
          </Pressable>
        </View>

        {/* Segmented control */}
        <View style={[styles.segment, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
          <Pressable
            onPress={() => setTab("ongoing")}
            style={[
              styles.segmentBtn,
              tab === "ongoing" ? { backgroundColor: THEME.ACCENT_SOFT } : null,
            ]}
            accessibilityRole="button"
          >
            <Text style={[styles.segmentText, { color: THEME.NAVY }]}>Ongoing</Text>
          </Pressable>
          <Pressable
            onPress={() => setTab("closed")}
            style={[
              styles.segmentBtn,
              tab === "closed" ? { backgroundColor: THEME.ACCENT_SOFT } : null,
            ]}
            accessibilityRole="button"
          >
            <Text style={[styles.segmentText, { color: THEME.NAVY }]}>Closed</Text>
          </Pressable>
        </View>

        {/* Cards */}
        {projects.length === 0 ? (
          <View style={[styles.card, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}>
            <Text style={[styles.emptyTitle, { color: THEME.NAVY }]}>No projects yet</Text>
            <Text style={[styles.emptyBody, { color: THEME.MUTED }]}>
              Create a project to track steps, progress, and notes.
            </Text>
          </View>
        ) : (
          projects.map((p) => {
            const pct = pctDone(p.steps);
            const done = p.steps.filter((s) => s.done).length;
            return (
              <Pressable
                key={p.id}
                onPress={() => router.push({ pathname: "/projects/[id]" as any, params: { id: p.id } } as any)}
                style={[styles.card, { backgroundColor: THEME.CARD, borderColor: THEME.BORDER }]}
                accessibilityRole="button"
              >
                <View style={styles.cardTop}>
                  <View style={[styles.badge, { backgroundColor: THEME.ACCENT_SOFT }]}>
                    <Ionicons name="hammer-outline" size={14} color={THEME.NAVY} style={{ marginRight: 6 }} />
                    <Text style={[styles.badgeText, { color: THEME.NAVY }]}>{pct}%</Text>
                  </View>

                  <View style={{ flex: 1 }}>
                    <Text style={[styles.cardTitle, { color: THEME.NAVY }]} numberOfLines={1}>
                      {p.title}
                    </Text>
                    <Text style={[styles.cardSub, { color: THEME.MUTED }]} numberOfLines={1}>
                      {p.kit ? `${p.kit} • ` : ""}{done}/{p.steps.length} steps • Updated {fmtUpdated(p.updatedAt)}
                    </Text>
                  </View>

                  <Ionicons name="chevron-forward" size={18} color={THEME.MUTED} />
                </View>

                <View style={{ marginTop: 10 }}>
                  <ProgressBar value={pct} />
                </View>
              </Pressable>
            );
          })
        )}
      </ScrollView>
    
      {/* Floating + (New project) */}
      <Link href="/projects/new" asChild>
        <Pressable
          accessibilityRole="button"
          style={{
            position: "absolute",
            right: 16,
            bottom: 16,
            width: 54,
            height: 54,
            borderRadius: 27,
            backgroundColor: "#0C2233",
            alignItems: "center",
            justifyContent: "center",
            borderWidth: 1,
            borderColor: "#D6E4EC",
          }}
        >
          <Ionicons name="add" size={26} color="#FFFFFF" />
        </Pressable>
      </Link>

</SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { backgroundColor: "#F2F4F7", flex: 1},

  headerRow: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: 999,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#fff",
  },

  hTitle: { fontSize: 16, fontWeight: "900" },
  hSub: { marginTop: 2, fontSize: 12, fontWeight: "700" },

  segment: {
    flexDirection: "row",
    borderWidth: 1,
    borderRadius: 14,
    padding: 4,
    marginBottom: 10,
  },
  segmentBtn: { flex: 1, paddingVertical: 10, borderRadius: 12, alignItems: "center" },
  segmentText: { fontSize: 12, fontWeight: "900" },

  card: { borderWidth: 1, borderRadius: 16, padding: 12, marginBottom: 10 },
  cardTop: { flexDirection: "row", alignItems: "center", gap: 10 },

  badge: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    flexDirection: "row",
    alignItems: "center",
  },
  badgeText: { fontSize: 12, fontWeight: "900" },

  cardTitle: { fontSize: 14, fontWeight: "900" },
  cardSub: { marginTop: 2, fontSize: 12, fontWeight: "700" },

  progressTrack: {
    height: 10,
    borderRadius: 999,
    overflow: "hidden",
    backgroundColor: "rgba(12,34,51,0.08)",
  },
  progressFill: { height: 10, borderRadius: 999, backgroundColor: "#38D6C7" },

  emptyTitle: { fontSize: 14, fontWeight: "900" },
  emptyBody: { marginTop: 6, fontSize: 12, fontWeight: "700", lineHeight: 18 },
});
