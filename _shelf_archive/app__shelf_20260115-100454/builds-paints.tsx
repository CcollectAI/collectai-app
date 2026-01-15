import React, { useMemo, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

type BuildStatus = "planning" | "in_progress" | "finished";

type BuildProject = {
  id: string;
  title: string;
  category: string; // e.g. "Gunpla", "Warhammer", "LEGO"
  status: BuildStatus;
  progress: number; // 0–100
  linkedItemName?: string;
  targetDate?: string; // ISO or label
  tags: string[];
};

const useAppColors = () => ({
  background: "#FFFFFF",
  card: "#FFFFFF",
  text: "#0C2233",
  muted: "#647589",
  accent: "#19A7AE",
  border: "#D6E4EC",
  chipBg: "#F3F6F8",
});

const MOCK_PROJECTS: BuildProject[] = [
  {
    id: "p1",
    title: "HG Gundam Aerial (build + panel line)",
    category: "Gunpla",
    status: "in_progress",
    progress: 45,
    linkedItemName: "HG Gundam Aerial",
    targetDate: "2025-12-15",
    tags: ["Gunpla", "Panel lining", "Water decals"],
  },
  {
    id: "p2",
    title: "Warhammer 40K – Space Marines patrol",
    category: "Warhammer",
    status: "planning",
    progress: 10,
    linkedItemName: "Space Marines starter",
    targetDate: "Weekend project",
    tags: ["Warhammer", "Contrast paints", "Tabletop ready"],
  },
  {
    id: "p3",
    title: "LEGO UCS X-Wing – display stand mod",
    category: "LEGO",
    status: "finished",
    progress: 100,
    linkedItemName: "LEGO UCS X-Wing",
    targetDate: "Done",
    tags: ["LEGO", "Display", "Mod"],
  },
];

const statusLabel = (status: BuildStatus) => {
  if (status === "in_progress") return "In progress";
  if (status === "planning") return "Planning";
  return "Finished";
};

const statusColor = (status: BuildStatus) => {
  if (status === "in_progress") return "#19A7AE";
  if (status === "planning") return "#647589";
  return "#0BA86C";
};

const BuildsPaintsScreen: React.FC = () => {
  const colors = useAppColors();
  const [notesById, setNotesById] = useState<Record<string, string>>({});

  const sections = useMemo(() => {
    const planning = MOCK_PROJECTS.filter((p) => p.status === "planning");
    const inProgress = MOCK_PROJECTS.filter((p) => p.status === "in_progress");
    const finished = MOCK_PROJECTS.filter((p) => p.status === "finished");
    return { planning, inProgress, finished };
  }, []);

  const handleNoteChange = (id: string, text: string) => {
    setNotesById((prev) => ({ ...prev, [id]: text }));
  };

  const renderSection = (title: string, projects: BuildProject[]) => {
    if (!projects.length) return null;

    return (
      <View style={styles.sectionBlock}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>
          {title}
        </Text>

        {projects.map((p) => {
          const sColor = statusColor(p.status);
          const noteValue = notesById[p.id] ?? "";

          let etaLabel = "";
          if (p.status === "in_progress") {
            if (p.progress < 30) etaLabel = "Long";
            else if (p.progress < 80) etaLabel = "Medium";
            else etaLabel = "Short";
          } else if (p.status === "planning") {
            etaLabel = "Not started";
          } else {
            etaLabel = "Completed";
          }

          return (
            <View
              key={p.id}
              style={[
                styles.card,
                { backgroundColor: colors.card, borderColor: colors.border },
              ]}
            >
              {/* Header row */}
              <View style={styles.cardHeaderRow}>
                <View style={{ flex: 1 }}>
                  <Text
                    style={[styles.projectTitle, { color: colors.text }]}
                    numberOfLines={2}
                  >
                    {p.title}
                  </Text>
                  <View style={styles.projectMetaRow}>
                    <Text
                      style={[
                        styles.projectMetaText,
                        { color: colors.muted },
                      ]}
                    >
                      {p.category}
                    </Text>
                    {p.linkedItemName && (
                      <Text
                        style={[
                          styles.projectMetaText,
                          { color: colors.muted, marginLeft: 8 },
                        ]}
                      >
                        Linked: {p.linkedItemName}
                      </Text>
                    )}
                  </View>
                </View>

                <View
                  style={[
                    styles.statusChip,
                    { borderColor: sColor, backgroundColor: "#F3F6F8" },
                  ]}
                >
                  <View
                    style={[
                      styles.statusDot,
                      { backgroundColor: sColor },
                    ]}
                  />
                  <Text
                    style={[
                      styles.statusChipText,
                      { color: sColor },
                    ]}
                  >
                    {statusLabel(p.status)}
                  </Text>
                </View>
              </View>

              {/* Progress bar */}
              <View style={styles.progressRow}>
                <View style={styles.progressLabelRow}>
                  <Text
                    style={[styles.progressLabel, { color: colors.muted }]}
                  >
                    Progress
                  </Text>
                  <Text
                    style={[styles.progressLabel, { color: colors.muted }]}
                  >
                    {p.progress}%
                  </Text>
                </View>
                <View style={styles.progressBarBackground}>
                  <View
                    style={[
                      styles.progressBarFill,
                      {
                        width: `${Math.max(4, p.progress)}%`,
                        backgroundColor: sColor,
                      },
                    ]}
                  />
                </View>
                <Text
                  style={[styles.etaText, { color: colors.muted }]}
                >
                  ETA: {etaLabel}
                </Text>
              </View>

              {/* Tags */}
              {p.tags.length > 0 && (
                <View style={styles.tagsRow}>
                  {p.tags.map((tag) => (
                    <View
                      key={tag}
                      style={[
                        styles.tagChip,
                        { backgroundColor: colors.chipBg },
                      ]}
                    >
                      <Text
                        style={[
                          styles.tagText,
                          { color: colors.muted },
                        ]}
                      >
                        {tag}
                      </Text>
                    </View>
                  ))}
                </View>
              )}

              {/* Notes */}
              <View style={styles.notesBlock}>
                <View style={styles.notesHeaderRow}>
                  <Text
                    style={[styles.notesLabel, { color: colors.text }]}
                  >
                    Paint / build notes
                  </Text>
                  <Ionicons
                    name="brush-outline"
                    size={14}
                    color={colors.muted}
                  />
                </View>
                <TextInput
                  multiline
                  placeholder="Primer, base coat, wash, highlight, varnish…"
                  placeholderTextColor={colors.muted}
                  value={noteValue}
                  onChangeText={(text) => handleNoteChange(p.id, text)}
                  style={[
                    styles.notesInput,
                    {
                      borderColor: colors.border,
                      color: colors.text,
                    },
                  ]}
                />
              </View>
            </View>
          );
        })}
      </View>
    );
  };

  return (
    <SafeAreaView
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.title, { color: colors.text }]}>
              Builds & paints
            </Text>
            <Text style={[styles.subtitle, { color: colors.muted }]}>
              Track active builds, painting projects and display mods for your
              collection.
            </Text>
          </View>
          <View style={styles.headerIconCircle}>
            <Ionicons name="color-palette-outline" size={20} color={colors.text} />
          </View>
        </View>

        {/* Info card */}
        <View
          style={[
            styles.infoCard,
            { backgroundColor: "#F3F9FB", borderColor: colors.border },
          ]}
        >
          <Ionicons
            name="information-circle-outline"
            size={18}
            color={colors.accent}
            style={{ marginRight: 8 }}
          />
          <Text style={[styles.infoText, { color: colors.muted }]}>
            For now this is mock data and local notes only. Later we’ll sync
            projects to Supabase, link them to specific items, and surface
            progress on the Portfolio screen.
          </Text>
        </View>

        {renderSection("In progress", sections.inProgress)}
        {renderSection("Planning", sections.planning)}
        {renderSection("Finished", sections.finished)}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
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
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 13,
    marginTop: 4,
  },
  headerIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F3F6F8",
  },
  infoCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 14,
  },
  infoText: {
    flex: 1,
    fontSize: 12,
    lineHeight: 16,
  },
  sectionBlock: {
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: "700",
    marginBottom: 8,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
  },
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  projectTitle: {
    fontSize: 15,
    fontWeight: "600",
  },
  projectMetaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 4,
    flexWrap: "wrap",
  },
  projectMetaText: {
    fontSize: 12,
  },
  statusChip: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 4,
  },
  statusChipText: {
    fontSize: 11,
    fontWeight: "600",
  },
  progressRow: {
    marginTop: 4,
  },
  progressLabelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 4,
  },
  progressLabel: {
    fontSize: 11,
  },
  progressBarBackground: {
    height: 8,
    borderRadius: 999,
    backgroundColor: "#F3F6F8",
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    borderRadius: 999,
  },
  etaText: {
    fontSize: 11,
    marginTop: 4,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: 6,
  },
  tagChip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    marginRight: 6,
    marginTop: 4,
  },
  tagText: {
    fontSize: 11,
    fontWeight: "500",
  },
  notesBlock: {
    marginTop: 10,
  },
  notesHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  notesLabel: {
    fontSize: 13,
    fontWeight: "600",
  },
  notesInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 12,
    minHeight: 60,
    textAlignVertical: "top",
  },
});

export default BuildsPaintsScreen;
