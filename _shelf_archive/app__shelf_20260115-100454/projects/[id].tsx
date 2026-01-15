import React, { useMemo, useState } from "react";
import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";

type ProjectStep = { id: string; label: string; done?: boolean };
type Project = {
  id: string;
  slug?: string;
  title: string;
  subtitle?: string;
  status: "ongoing" | "closed";
  percent: number; // 0..100
  steps: ProjectStep[];
  notes?: string;
  updatedAt?: string;
};

function normalizeParam(v: string | string[] | undefined) {
  const raw = Array.isArray(v) ? v[0] : v;
  if (!raw) return undefined;
  try {
    return decodeURIComponent(String(raw)).trim();
  } catch {
    return String(raw).trim();
  }
}

function clamp(n: number) {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(100, n));
}

// Try to load a real project source if your repo has one; fallback to mock.
function loadProjects(): Project[] {
  // @ts-ignore
  const g: any = globalThis as any;

  // If you have a projects module somewhere, add it here later.
  // For now keep a stable mock so the screen never 404s due to missing imports.
  if (g.__COLLECTORS_PROJECTS__ && Array.isArray(g.__COLLECTORS_PROJECTS__)) return g.__COLLECTORS_PROJECTS__;

  return [
    {
      id: "gunpla-rx78",
      slug: "gunpla-rx78",
      title: "RX-78 Build + Paint",
      subtitle: "Gunpla • grade + finish plan",
      status: "ongoing",
      percent: 42,
      updatedAt: "Today",
      steps: [
        { id: "prep", label: "Prep & clean parts", done: true },
        { id: "assemble", label: "Assemble (dry-fit)", done: true },
        { id: "prime", label: "Prime", done: false },
        { id: "base", label: "Base coat", done: false },
        { id: "detail", label: "Detailing + decals", done: false },
        { id: "topcoat", label: "Top coat + seal", done: false },
      ],
      notes: "Mask shoulders, test metallic on backpack.",
    },
    {
      id: "pokemon-display",
      slug: "pokemon-display",
      title: "Pokémon Display Case",
      subtitle: "TCG • storage + catalog",
      status: "ongoing",
      percent: 18,
      updatedAt: "Yesterday",
      steps: [
        { id: "audit", label: "Audit collection", done: true },
        { id: "sleeves", label: "Sleeves + top loaders", done: false },
        { id: "case", label: "Case layout", done: false },
        { id: "labels", label: "Labels + indexing", done: false },
      ],
      notes: "Separate slabs by PSA grade; add humidity pack.",
    },
    {
      id: "warhammer-squad",
      slug: "warhammer-squad",
      title: "Warhammer Squad Batch Paint",
      subtitle: "Minis • batch pipeline",
      status: "closed",
      percent: 100,
      updatedAt: "Last week",
      steps: [
        { id: "prep", label: "Prep", done: true },
        { id: "prime", label: "Prime", done: true },
        { id: "base", label: "Base", done: true },
        { id: "wash", label: "Wash", done: true },
        { id: "highlight", label: "Highlights", done: true },
        { id: "seal", label: "Seal", done: true },
      ],
      notes: "Completed. Photograph + archive.",
    },
  ];
}

const BG = "#F2F4F7";
const CARD = "#FFFFFF";
const BORDER = "#D6E4EC";
const TEXT = "#0C2233";
const MUTED = "#647589";
const ACCENT = "#38D6C7";
const NAVY = "#0C2233";

export default function ProjectDetailScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string | string[]; projectId?: string | string[]; slug?: string | string[] }>();

  const idParam = normalizeParam(params.id) ?? normalizeParam(params.projectId) ?? normalizeParam(params.slug);

  const projects = useMemo(() => loadProjects(), []);
  const project = useMemo(() => {
    if (!idParam) return undefined;
    const key = idParam.toLowerCase();
    return projects.find((p) => {
      const a = String(p.id).toLowerCase();
      const b = String(p.slug ?? "").toLowerCase();
      return a === key || b === key;
    });
  }, [idParam, projects]);

  const [steps, setSteps] = useState<ProjectStep[]>(project?.steps ?? []);
  const [notes, setNotes] = useState(project?.notes ?? "");

  const percent = useMemo(() => {
    if (!steps.length) return clamp(project?.percent ?? 0);
    const done = steps.filter((s) => !!s.done).length;
    return clamp(Math.round((done / steps.length) * 100));
  }, [steps, project?.percent]);

  const toggleStep = (sid: string) => {
    setSteps((prev) => prev.map((s) => (s.id === sid ? { ...s, done: !s.done } : s)));
  };

  if (!project) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: BG }]} edges={["top", "left", "right"]}>
        <View style={[styles.container, { paddingTop: Math.max(12, insets.top) }]}>
          <View style={styles.headerRow}>
            <Pressable onPress={() => router.back()} style={[styles.iconBtn, { borderColor: BORDER }]}>
              <Ionicons name="chevron-back" size={18} color={MUTED} />
            </Pressable>
            <Text style={styles.h1}>Project not found</Text>
            <View style={{ width: 36 }} />
          </View>

          <View style={[styles.card, { borderColor: BORDER, backgroundColor: CARD }]}>
            <Text style={styles.bodyMuted}>
              Tried id: <Text style={{ fontWeight: "900", color: TEXT }}>{idParam ?? "(missing)"}</Text>
            </Text>
            <Text style={[styles.bodyMuted, { marginTop: 10 }]}>Available project IDs (for quick sanity):</Text>
            {projects.map((p) => (
              <Text key={p.id} style={[styles.body, { marginTop: 6 }]}>
                • {p.id}
              </Text>
            ))}
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: BG }]} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={[styles.container, { paddingTop: 12, paddingBottom: 28 }]}>
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={[styles.iconBtn, { borderColor: BORDER }]}>
            <Ionicons name="chevron-back" size={18} color={MUTED} />
          </Pressable>

          <View style={{ flex: 1, paddingHorizontal: 10 }}>
            <Text style={styles.h1} numberOfLines={1}>
              {project.title}
            </Text>
            <Text style={styles.h2} numberOfLines={1}>
              {project.subtitle ?? "Build & Paint Project"}
            </Text>
          </View>

          <View style={{ width: 36 }} />
        </View>

        <View style={[styles.card, { borderColor: BORDER, backgroundColor: CARD }]}>
          <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            <Text style={styles.sectionTitle}>Progress</Text>
            <Text style={styles.kpi}>{percent}%</Text>
          </View>

          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${percent}%` }]} />
          </View>

          <Text style={[styles.bodyMuted, { marginTop: 8 }]}>
            Updated: <Text style={{ color: TEXT, fontWeight: "800" }}>{project.updatedAt ?? "—"}</Text>
          </Text>
        </View>

        <View style={[styles.card, { borderColor: BORDER, backgroundColor: CARD }]}>
          <Text style={styles.sectionTitle}>Steps</Text>

          {steps.map((s) => (
            <Pressable
              key={s.id}
              onPress={() => toggleStep(s.id)}
              style={[
                styles.stepRow,
                {
                  borderColor: BORDER,
                  backgroundColor: s.done ? "rgba(56,214,199,0.12)" : "#FFFFFF",
                },
              ]}
              accessibilityRole="button"
            >
              <Ionicons
                name={s.done ? "checkmark-circle" : "ellipse-outline"}
                size={18}
                color={s.done ? ACCENT : MUTED}
                style={{ marginRight: 10 }}
              />
              <Text style={[styles.stepText, { color: TEXT }]} numberOfLines={2}>
                {s.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <View style={[styles.card, { borderColor: BORDER, backgroundColor: CARD }]}>
          <Text style={styles.sectionTitle}>Notes</Text>
          <View style={[styles.noteBox, { borderColor: BORDER }]}>
            <Text style={{ color: MUTED, fontSize: 12, fontWeight: "700" }}>
              (Edit later — wiring persistence next)
            </Text>
            <Text style={[styles.body, { marginTop: 8 }]} numberOfLines={6}>
              {notes?.trim() ? notes : "Add build notes, paint recipe, decal plan, and next actions."}
            </Text>
          </View>
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

  h1: { color: TEXT, fontSize: 16, fontWeight: "900" },
  h2: { marginTop: 2, color: MUTED, fontSize: 11, fontWeight: "700" },

  card: { borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 10 },

  sectionTitle: { color: NAVY, fontSize: 13, fontWeight: "900" },
  kpi: { color: NAVY, fontSize: 13, fontWeight: "900" },

  progressTrack: { marginTop: 10, height: 10, borderRadius: 999, backgroundColor: "rgba(12,34,51,0.08)", overflow: "hidden" },
  progressFill: { height: 10, borderRadius: 999, backgroundColor: ACCENT },

  body: { color: TEXT, fontSize: 12, fontWeight: "700", lineHeight: 17 },
  bodyMuted: { color: MUTED, fontSize: 12, fontWeight: "700", lineHeight: 17 },

  stepRow: { marginTop: 10, borderWidth: 1, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 10, flexDirection: "row", alignItems: "center" },
  stepText: { flex: 1, fontSize: 12, fontWeight: "800" },

  noteBox: { marginTop: 10, borderWidth: 1, borderRadius: 12, padding: 12 },
});
