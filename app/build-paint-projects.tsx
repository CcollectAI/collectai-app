import { TextInput } from "react-native";
import React, { useEffect, useMemo, useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import supabase from "@/lib/supabaseClient";
import { useAppTheme } from "@/hooks/useAppTheme";
type LoadState = "idle" | "loading" | "loaded" | "error";

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

type BuildPaintProject = {
  id: string;
  title: string;
  category: string | null;
  status: string | null;   // Backlog | Active | Completed
  priority: string | null; // Low | Medium | High
  notes: string | null;
  estimated_hours: number | null;
};

type BuildPaintSession = {
  id: string;
  project_id: string;
  minutes: number;
};

type ProjectWithStats = BuildPaintProject & {
  totalMinutes: number;
  totalHours: number;
};

const MOCK_PROJECTS: ProjectWithStats[] = [
  {
    id: "mock-1",
    title: "Gunpla MG RX-78-2 (Ver. 3.0)",
    category: "Gunpla & model kits",
    status: "Active",
    priority: "High",
    notes: "Panel lining + decals this weekend.",
    estimated_hours: 12,
    totalMinutes: 180,
    totalHours: 3,
  },
  {
    id: "mock-2",
    title: "Warhammer Kill Team squad",
    category: "Warhammer minis",
    status: "Backlog",
    priority: "Medium",
    notes: "Prime + zenithal highlight first.",
    estimated_hours: 10,
    totalMinutes: 0,
    totalHours: 0,
  },
  {
    id: "mock-3",
    title: "LEGO UCS starship",
    category: "Bricks & kits",
    status: "Completed",
    priority: "Low",
    notes: "Display-only; tracking for nostalgia.",
    estimated_hours: 8,
    totalMinutes: 480,
    totalHours: 8,
  },
];

const statusColor = (status: string | null | undefined) => {
  const s = (status || "").toLowerCase();
  if (s === "active") return { bg: "#E7F6F8", text: "#19A7AE" };
  if (s === "completed") return { bg: "#E6F7EF", text: "#0BA86C" };
  if (s === "backlog") return { bg: "#F3F6F8", text: "#647589" };
  return { bg: "#F3F6F8", text: "#647589" };
};

const priorityLabel = (priority: string | null | undefined) => {
  const p = (priority || "").toLowerCase();
  if (p === "high") return "High";
  if (p === "medium") return "Medium";
  if (p === "low") return "Low";
  return "—";
};

const BuildPaintProjectsScreen: React.FC = () => {
  const colors = useAppColors();

  const [state, setState] = useState<LoadState>("idle");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectWithStats[]>([]);
  const [loggingIds, setLoggingIds] = useState<Set<string>>(new Set());

  const usingMock = useMemo(() => state === "error" || projects.length === 0, [
    state,
    projects.length,
  ]);

  useEffect(() => {
    const load = async () => {
      setState("loading");
      setErrorText(null);

      try {
        const client: any = supabase as any;
        if (!client || typeof client.from !== "function") {
          // Supabase not wired → fall back to mock
          setProjects(MOCK_PROJECTS);
          setState("error");
          setErrorText("Supabase client not configured – running on mock data.");
          return;
        }

        const [projRes, sessRes] = await Promise.all([
          client
            .from("build_paint_projects")
            .select(
              "id, title, category, status, priority, notes, estimated_hours"
            )
            .order("created_at", { ascending: true }),
          client
            .from("build_paint_sessions")
            .select("id, project_id, minutes"),
        ]);

        let projData: BuildPaintProject[] = [];
        let sessData: BuildPaintSession[] = [];

        if (projRes.error) {
          console.warn(
            "[BuildPaint] build_paint_projects error:",
            projRes.error.message
          );
        } else if (Array.isArray(projRes.data)) {
          projData = projRes.data as BuildPaintProject[];
        }

        if (sessRes.error) {
          console.warn(
            "[BuildPaint] build_paint_sessions error:",
            sessRes.error.message
          );
        } else if (Array.isArray(sessRes.data)) {
          sessData = sessRes.data as BuildPaintSession[];
        }

        if (projData.length === 0) {
          // If no projects in DB, use mocks so the screen never feels empty
          setProjects(MOCK_PROJECTS);
          setState("loaded");
          return;
        }

        const totals = new Map<string, number>();
        for (const s of sessData) {
          const current = totals.get(s.project_id) ?? 0;
          const m = Number(s.minutes ?? 0);
          if (!Number.isNaN(m)) {
            totals.set(s.project_id, current + m);
          }
        }

        const withStats: ProjectWithStats[] = projData.map((p) => {
          const minutes = totals.get(p.id) ?? 0;
          return {
            ...p,
            totalMinutes: minutes,
            totalHours: minutes / 60,
          };
        });

        setProjects(withStats);
        setState("loaded");
      } catch (err: any) {
        console.warn("[BuildPaint] unexpected error:", err);
        setProjects(MOCK_PROJECTS);
        setState("error");
        setErrorText(
          err?.message || "Unexpected error while loading build/paint projects."
        );
      }
    };

    load();
  }, []);

  const handleLogSession = async (projectId: string, minutes: number = 30) => {
    const client: any = supabase as any;
    if (!client || typeof client.from !== "function") {
      // No-op in demo mode
      return;
    }

    setLoggingIds((prev) => new Set(prev).add(projectId));

    try {
      const { error } = await client
        .from("build_paint_sessions")
        .insert([{ project_id: projectId, minutes }]);

      if (error) {
        console.warn("[BuildPaint] log session error:", error.message);
      } else {
        // Update local state
        setProjects((prev) =>
          prev.map((p) =>
            p.id === projectId
              ? {
                  ...p,
                  totalMinutes: p.totalMinutes + minutes,
                  totalHours: (p.totalMinutes + minutes) / 60,
                }
              : p
          )
        );
      }
    } catch (err: any) {
      console.warn("[BuildPaint] log session unexpected:", err);
    } finally {
      setLoggingIds((prev) => {
        const next = new Set(prev);
        next.delete(projectId);
        return next;
      });
    }
  };

  const loading = state === "loading";

  const totalMinutesAll = projects.reduce(
    (sum, p) => sum + (p.totalMinutes ?? 0),
    0
  );
  const totalHoursAll = totalMinutesAll / 60;
  const activeCount = projects.filter(
    (p) => (p.status || "").toLowerCase() === "active"
  ).length;
  const backlogCount = projects.filter(
    (p) => (p.status || "").toLowerCase() === "backlog"
  ).length;
  const completedCount = projects.filter(
    (p) => (p.status || "").toLowerCase() === "completed"
  ).length;

  return (
    <SafeAreaView
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>

          {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.headerLabel, { color: colors.muted }]}>
              Projects
            </Text>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Projects
            </Text>
            <Text style={[styles.headerSub, { color: colors.muted }]}>
              Track backlog, active projects and completed builds, plus total
              time spent. Logging here flows into your Analytics screen.
            </Text>
          </View>
          <View style={styles.headerIcon}>
            <Ionicons
              name="color-palette-outline"
              size={20}
              color={colors.accent}
            />
          </View>
        </View>

        
          {/* Quick notes (local) */}
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeaderRow}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Quick notes</Text>
              <Text style={[styles.cardHint, { color: colors.muted }]}>Local-only for now</Text>
            </View>

            <Text style={{ fontSize: 12, color: colors.muted, lineHeight: 18, marginTop: 6 }}>
              Use this for paint notes and a simple progress checklist. Later we can attach it to a project row in Supabase.
            </Text>

            <Text style={{ fontSize: 13, fontWeight: "700", color: colors.text, marginTop: 12, marginBottom: 6 }}>
              Notes
            </Text>

            <TextInput
              style={{
                borderRadius: 0,
                borderWidth: 1,
                borderColor: colors.border,
                paddingHorizontal: 12,
                paddingVertical: 10,
                fontSize: 13,
                color: colors.text,
                minHeight: 88,
              }}
              placeholder="Example: Warm ivory armor, purple OSL on blade, oils for skin…"
              placeholderTextColor={colors.muted}
              multiline
              textAlignVertical="top"
            />

            <Text style={{ fontSize: 13, fontWeight: "700", color: colors.text, marginTop: 14, marginBottom: 6 }}>
              Progress steps
            </Text>

            {[
              "Planning and references gathered",
              "Assembly / build finished",
              "Primed / surface prepared",
              "Base layer / basecoat finished",
              "Shading / washes done",
              "Details and highlights finished",
              "Final touches & varnish / display ready",
            ].map((label, idx) => (
              <View key={idx} style={{ flexDirection: "row", alignItems: "center", paddingVertical: 8 }}>
                <View
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: 9,
                    borderWidth: 1,
                    borderColor: colors.border,
                    marginRight: 10,
                  }}
                />
                <Text style={{ flex: 1, fontSize: 13, color: colors.text }} numberOfLines={2}>
                  {label}
                </Text>
              </View>
            ))}
          </View>

{/* Status banner */}
        <View
          style={[
            styles.banner,
            {
              backgroundColor:
                state === "error"
                  ? "#FDECEC"
                  : state === "loading"
                  ? "#FFF7E6"
                  : "#E7F6F8",
              borderColor:
                state === "error"
                  ? "#D64545"
                  : state === "loading"
                  ? "#F59E0B"
                  : "#19A7AE",
            },
          ]}
        >
          <View style={styles.bannerIconBox}>
            {loading ? (
              <ActivityIndicator size="small" color={colors.accent} />
            ) : (
              <Ionicons
                name={
                  state === "error"
                    ? "warning-outline"
                    : "checkmark-circle-outline"
                }
                size={18}
                color={
                  state === "error"
                    ? "#D64545"
                    : "#19A7AE"
                }
              />
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.bannerTitle, { color: colors.text }]}>
              {usingMock
                ? "Running on mock projects"
                : "Projects & sessions loaded from Supabase"}
            </Text>
            <Text style={[styles.bannerBody, { color: colors.muted }]}>
              When Supabase is configured and tables exist, this screen reads
              real projects and time logs. Otherwise it falls back to safe demo
              data.
            </Text>
            {errorText && (
              <Text
                style={[styles.bannerError, { color: "#D64545" }]}
                numberOfLines={2}
              >
                {errorText}
              </Text>
            )}
          </View>
        </View>

        {/* Summary strip */}
        <View
          style={[
            styles.summaryCard,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryLabel, { color: colors.muted }]}>
              Active
            </Text>
            <Text style={[styles.summaryValue, { color: colors.text }]}>
              {activeCount}
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryLabel, { color: colors.muted }]}>
              Backlog
            </Text>
            <Text style={[styles.summaryValue, { color: colors.text }]}>
              {backlogCount}
            </Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={[styles.summaryLabel, { color: colors.muted }]}>
              Completed
            </Text>
            <Text style={[styles.summaryValue, { color: "#0BA86C" }]}>
              {completedCount}
            </Text>
          </View>
        </View>

        {/* Total time card */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Total build time
            </Text>
            <Text style={[styles.cardHint, { color: colors.muted }]}>
              All sessions across all projects
            </Text>
          </View>
          <Text style={[styles.totalTimeText, { color: colors.text }]}>
            {totalMinutesAll.toLocaleString("en-US")} min{" "}
            <Text style={styles.totalTimeSub}>
              (~{totalHoursAll.toFixed(1)} hours)
            </Text>
          </Text>
          <View style={styles.metaRow}>
            <Ionicons
              name="information-circle-outline"
              size={14}
              color={colors.muted}
              style={{ marginRight: 4 }}
            />
            <Text style={[styles.metaText, { color: colors.muted }]}>
              Each tap on &quot;Log 30 min&quot; creates a build_paint_sessions
              row in Supabase (when configured).
            </Text>
          </View>
        </View>

        {/* Projects list */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.cardHeaderRow}>
            <Text style={[styles.cardTitle, { color: colors.text }]}>
              Projects
            </Text>
            <Text style={[styles.cardHint, { color: colors.muted }]}>
              Tap &quot;Log 30 min&quot; as you work
            </Text>
          </View>

          {projects.map((p, idx) => {
            const colorsStatus = statusColor(p.status);
            const isLogging = loggingIds.has(p.id);
            const displayHours = p.totalHours || 0;

            return (
              <View key={p.id}>
                <View style={styles.projectRow}>
                  <View style={{ flex: 1 }}>
                    <Text
                      style={[styles.projectTitle, { color: colors.text }]}
                      numberOfLines={1}
                    >
                      {p.title}
                    </Text>
                    <Text
                      style={[styles.projectMetaTop, { color: colors.muted }]}
                      numberOfLines={1}
                    >
                      {p.category || "Build / paint"}
                    </Text>
                    <View style={styles.projectMetaRow}>
                      <View
                        style={[
                          styles.statusPill,
                          { backgroundColor: colorsStatus.bg },
                        ]}
                      >
                        <Text
                          style={[
                            styles.statusPillText,
                            { color: colorsStatus.text },
                          ]}
                        >
                          {p.status || "Backlog"}
                        </Text>
                      </View>
                      <Text
                        style={[
                          styles.projectMetaBottom,
                          { color: colors.muted },
                        ]}
                        numberOfLines={1}
                      >
                        Priority: {priorityLabel(p.priority)} · Logged:{" "}
                        {displayHours.toFixed(1)}h
                      </Text>
                    </View>
                    {p.notes ? (
                      <Text
                        style={[styles.projectNotes, { color: colors.muted }]}
                        numberOfLines={2}
                      >
                        {p.notes}
                      </Text>
                    ) : null}
                  </View>

                  <View style={styles.projectRight}>
                    <Pressable
                      onPress={() => handleLogSession(p.id, 30)}
                      disabled={isLogging || usingMock}
                      style={[
                        styles.logButton,
                        {
                          backgroundColor: usingMock
                            ? "#F3F6F8"
                            : colors.accent,
                          opacity: isLogging ? 0.7 : 1,
                        },
                      ]}
                    >
                      {isLogging ? (
                        <ActivityIndicator size="small" color="#FFFFFF" />
                      ) : (
                        <>
                          <Ionicons
                            name="time-outline"
                            size={14}
                            color={usingMock ? "#647589" : "#FFFFFF"}
                          />
                          <Text
                            style={[
                              styles.logButtonText,
                              {
                                color: usingMock ? "#647589" : "#FFFFFF",
                              },
                            ]}
                          >
                            Log 30 min
                          </Text>
                        </>
                      )}
                    </Pressable>
                    {usingMock && (
                      <Text style={styles.demoTag}>
                        Demo only
                      </Text>
                    )}
                  </View>
                </View>
                {idx < projects.length - 1 && (
                  <View
                    style={[
                      styles.separator,
                      { backgroundColor: colors.border },
                    ]}
                  />
                )}
              </View>
            );
          })}
        </View>

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  headerLabel: {
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    fontWeight: "600",
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
    marginTop: 2,
  },
  headerSub: {
    fontSize: 12,
    marginTop: 4,
    maxWidth: 280,
  },
  headerIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#D6E4EC",
  },
  banner: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 16,
  },
  bannerIconBox: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  bannerTitle: {
    fontSize: 13,
    fontWeight: "600",
  },
  bannerBody: {
    fontSize: 11,
    marginTop: 2,
  },
  bannerError: {
    fontSize: 11,
    marginTop: 2,
  },
  summaryCard: {
  borderWidth: 1,
  borderRadius: 0,
  paddingVertical: 12,
  paddingHorizontal: 14,
  borderWidth: 1,
  borderRadius: 0,
  paddingVertical: 12,
  paddingHorizontal: 14,
    flexDirection: "row",
    justifyContent: "space-between",
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 16,
  },
  summaryItem: { flex: 1 },
  summaryLabel: {
    fontSize: 12,
  },
  summaryValue: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 2,
  },
  card: {
  borderWidth: 1,
  borderRadius: 0,
  padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  cardHint: {
    fontSize: 11,
  },
  totalTimeText: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 4,
  },
  totalTimeSub: {
    fontSize: 13,
    fontWeight: "500",
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 8,
  },
  metaText: {
    fontSize: 11,
    flex: 1,
  },
  metricsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  projectRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 8,
  },
  projectTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  projectMetaTop: {
    fontSize: 11,
    marginTop: 2,
  },
  projectMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 4,
  },
  statusPill: {
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
    marginRight: 8,
  },
  statusPillText: {
    fontSize: 11,
    fontWeight: "600",
  },
  projectMetaBottom: {
    fontSize: 11,
  },
  projectNotes: {
    fontSize: 11,
    marginTop: 4,
  },
  projectRight: {
    alignItems: "flex-end",
    marginLeft: 8,
  },
  logButton: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
    gap: 4,
  },
  logButtonText: {
    fontSize: 12,
    fontWeight: "600",
  },
  demoTag: {
    marginTop: 4,
    fontSize: 10,
    color: "#647589",
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 6,
  },
});

export default BuildPaintProjectsScreen;
