/**
 * Build & Paint Projects Screen — List view with Current/Completed sections.
 * Uses DataProvider for all data access.
 */

import React, { useEffect, useState, useCallback } from "react";
import {
  ScrollView,
  View,
  Text,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Animated,
  Modal,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { dataProvider, type BuildPaintProject } from "@/data";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";

const statusColor = (status: string | null | undefined, isCompleted: boolean) => {
  if (isCompleted) return { bg: "#E6F7EF", text: "#0BA86C" };
  const s = (status || "").toLowerCase();
  if (s === "active") return { bg: "#E7F6F8", text: "#19A7AE" };
  if (s === "backlog") return { bg: "#F3F6F8", text: "#647589" };
  return { bg: "#F3F6F8", text: "#647589" };
};

export default function BuildPaintProjectsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [projects, setProjects] = useState<BuildPaintProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [creating, setCreating] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const data = await dataProvider.listBuildPaintProjects();
      setProjects(data);
      setError(null);
    } catch (err: any) {
      console.warn("[BuildPaintProjects] loadProjects error:", err);
      setError(err?.message || "Failed to load projects");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreateProject = async () => {
    if (!newTitle.trim() || creating) return;

    setCreating(true);
    try {
      await dataProvider.createBuildPaintProject({
        title: newTitle.trim(),
        category: newCategory.trim() || null,
      });
      setNewTitle("");
      setNewCategory("");
      setShowCreateModal(false);
      await loadProjects();
    } catch (err: any) {
      console.warn("[BuildPaintProjects] create error:", err);
    } finally {
      setCreating(false);
    }
  };

  const handleProjectPress = (project: BuildPaintProject) => {
    router.push(`/projects/${project.id}`);
  };

  // Separate current (not completed) and completed projects
  const currentProjects = projects.filter((p) => !p.isCompleted);
  const completedProjects = projects.filter((p) => p.isCompleted);

  if (loading) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading projects...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        <Animated.View style={animatedStyle}>
          {/* Add button */}
          <View style={styles.actionRow}>
            <AnimatedPressable
              onPress={() => setShowCreateModal(true)}
              style={[styles.addBtn, { backgroundColor: colors.accent }]}
            >
              <Ionicons name="add" size={20} color="#fff" />
              <Text style={styles.addBtnText}>New Project</Text>
            </AnimatedPressable>
          </View>

          {/* Error state */}
          {error && (
            <View style={[styles.errorBanner, { backgroundColor: "#FDECEC", borderColor: "#D64545" }]}>
              <Ionicons name="warning-outline" size={18} color="#D64545" />
              <Text style={[styles.errorText, { color: "#D64545" }]}>{error}</Text>
            </View>
          )}

          {/* Empty state */}
          {projects.length === 0 && !error && (
            <View style={[styles.emptyCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Ionicons name="color-palette-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>No projects yet</Text>
              <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
                Tap the + button to create your first build or paint project
              </Text>
            </View>
          )}

          {/* Current Projects Section */}
          {currentProjects.length > 0 && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.muted }]}>
                Current ({currentProjects.length})
              </Text>
              {currentProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  colors={colors}
                  onPress={() => handleProjectPress(project)}
                />
              ))}
            </View>
          )}

          {/* Completed Projects Section */}
          {completedProjects.length > 0 && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.muted }]}>
                Completed ({completedProjects.length})
              </Text>
              {completedProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  colors={colors}
                  onPress={() => handleProjectPress(project)}
                />
              ))}
            </View>
          )}

          <View style={{ height: 24 }} />
        </Animated.View>
      </ScrollView>

      {/* Create Project Modal */}
      <Modal
        visible={showCreateModal}
        animationType="slide"
        transparent
        onRequestClose={() => setShowCreateModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          style={styles.modalOverlay}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>New Project</Text>
              <AnimatedPressable onPress={() => setShowCreateModal(false)}>
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>

            <Text style={[styles.inputLabel, { color: colors.text }]}>Title *</Text>
            <TextInput
              value={newTitle}
              onChangeText={setNewTitle}
              placeholder="e.g., Warhammer Kill Team squad"
              placeholderTextColor={colors.muted}
              style={[
                styles.textInput,
                { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
              ]}
            />

            <Text style={[styles.inputLabel, { color: colors.text, marginTop: 16 }]}>
              Category (optional)
            </Text>
            <TextInput
              value={newCategory}
              onChangeText={setNewCategory}
              placeholder="e.g., Warhammer, Gunpla, LEGO"
              placeholderTextColor={colors.muted}
              style={[
                styles.textInput,
                { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
              ]}
            />

            <AnimatedPressable
              onPress={handleCreateProject}
              disabled={!newTitle.trim() || creating}
              style={[
                styles.createBtn,
                {
                  backgroundColor: newTitle.trim() ? colors.accent : colors.border,
                  opacity: creating ? 0.7 : 1,
                },
              ]}
            >
              {creating ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Text style={styles.createBtnText}>Create Project</Text>
              )}
            </AnimatedPressable>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

// Project Card Component
function ProjectCard({
  project,
  colors,
  onPress,
}: {
  project: BuildPaintProject;
  colors: any;
  onPress: () => void;
}) {
  const statusColors = statusColor(project.status, project.isCompleted);

  return (
    <AnimatedPressable
      onPress={onPress}
      style={[styles.projectCard, { backgroundColor: colors.card, borderColor: colors.border }]}
    >
      <View style={styles.projectCardHeader}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.projectTitle, { color: colors.text }]} numberOfLines={1}>
            {project.title}
          </Text>
          {project.category && (
            <Text style={[styles.projectCategory, { color: colors.muted }]} numberOfLines={1}>
              {project.category}
            </Text>
          )}
        </View>
        <View style={[styles.statusPill, { backgroundColor: statusColors.bg }]}>
          <Text style={[styles.statusPillText, { color: statusColors.text }]}>
            {project.isCompleted ? "Completed" : project.status || "Backlog"}
          </Text>
        </View>
      </View>

      {/* Progress bar */}
      <View style={styles.progressContainer}>
        <View style={[styles.progressTrack, { backgroundColor: colors.border }]}>
          <View
            style={[
              styles.progressFill,
              {
                width: `${Math.min(Math.max(project.percent, 0), 100)}%`,
                backgroundColor: project.isCompleted ? "#0BA86C" : colors.accent,
              },
            ]}
          />
        </View>
        <Text style={[styles.progressText, { color: colors.muted }]}>{project.percent}%</Text>
      </View>

      {project.notes && (
        <Text style={[styles.projectNotes, { color: colors.muted }]} numberOfLines={2}>
          {project.notes}
        </Text>
      )}

      <View style={styles.projectFooter}>
        <Text style={[styles.projectDate, { color: colors.muted }]}>
          Updated {formatRelativeDate(project.updatedAt)}
        </Text>
        <Ionicons name="chevron-forward" size={16} color={colors.muted} />
      </View>
    </AnimatedPressable>
  );
}

function formatRelativeDate(dateStr: string): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    fontWeight: "600",
  },
  actionRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginBottom: 16,
  },
  addBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    gap: 6,
  },
  addBtnText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#fff",
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
  },
  errorText: {
    flex: 1,
    fontSize: 13,
    fontWeight: "500",
  },
  emptyCard: {
    alignItems: "center",
    padding: 32,
    borderRadius: 16,
    borderWidth: 1,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: "center",
    marginTop: 8,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  projectCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 12,
  },
  projectCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  projectTitle: {
    fontSize: 16,
    fontWeight: "600",
  },
  projectCategory: {
    fontSize: 12,
    marginTop: 2,
  },
  statusPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    marginLeft: 12,
  },
  statusPillText: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "capitalize",
  },
  progressContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 8,
  },
  progressTrack: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 3,
  },
  progressText: {
    fontSize: 12,
    fontWeight: "600",
    minWidth: 36,
    textAlign: "right",
  },
  projectNotes: {
    fontSize: 13,
    marginBottom: 8,
  },
  projectFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  projectDate: {
    fontSize: 11,
  },

  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: "700",
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 8,
  },
  textInput: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
  createBtn: {
    marginTop: 24,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  createBtnText: {
    fontSize: 15,
    fontWeight: "600",
    color: "#fff",
  },
});
