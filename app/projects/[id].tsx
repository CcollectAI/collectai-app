/**
 * Project Detail Screen — View and edit build/paint project.
 * Uses DataProvider for all data access.
 */

import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Switch,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  dataProvider,
  type BuildPaintProject,
  type BuildPaintStep,
  type BuildPaintNote,
} from "@/data";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import logger from "@/utils/logger";

export default function ProjectDetailScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const params = useLocalSearchParams<{ id?: string }>();
  const projectId = params.id ?? "";

  const [project, setProject] = useState<BuildPaintProject | null>(null);
  const [steps, setSteps] = useState<BuildPaintStep[]>([]);
  const [notes, setNotes] = useState<BuildPaintNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Progress controls
  const [pendingPercent, setPendingPercent] = useState<number>(0);
  const [savingProgress, setSavingProgress] = useState(false);

  // Add step
  const [newStepTitle, setNewStepTitle] = useState("");
  const [addingStep, setAddingStep] = useState(false);

  // Add note
  const [newNoteBody, setNewNoteBody] = useState("");
  const [addingNote, setAddingNote] = useState(false);

  // Toggle completing
  const [togglingComplete, setTogglingComplete] = useState(false);

  const loadProject = useCallback(async () => {
    if (!projectId) {
      setError("No project ID provided");
      setLoading(false);
      return;
    }

    try {
      const [projectsData, stepsData, notesData] = await Promise.all([
        dataProvider.listBuildPaintProjects(),
        dataProvider.listBuildPaintSteps(projectId),
        dataProvider.listBuildPaintNotes(projectId),
      ]);

      const found = projectsData.find((p) => p.id === projectId);
      if (!found) {
        setError("Project not found");
      } else {
        setProject(found);
        setPendingPercent(found.percent);
      }
      setSteps(stepsData);
      setNotes(notesData);
      setError(null);
    } catch (err: unknown) {
      logger.warn("[ProjectDetail] loadProject error:", err);
      setError(err?.message || "Failed to load project");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const handleSaveProgress = async () => {
    if (!project || savingProgress) return;
    setSavingProgress(true);
    try {
      const newStatus = pendingPercent >= 100 ? "completed" : pendingPercent > 0 ? "active" : "backlog";
      await dataProvider.setBuildPaintProgress(project.id, pendingPercent, newStatus);
      await loadProject();
    } catch (err: unknown) {
      Alert.alert("Error", err?.message || "Failed to save progress");
    } finally {
      setSavingProgress(false);
    }
  };

  const handleToggleComplete = async () => {
    if (!project || togglingComplete) return;
    setTogglingComplete(true);
    try {
      await dataProvider.markBuildPaintProjectComplete(project.id, !project.isCompleted);
      await loadProject();
    } catch (err: unknown) {
      Alert.alert("Error", err?.message || "Failed to toggle complete");
    } finally {
      setTogglingComplete(false);
    }
  };

  const handleAddStep = async () => {
    if (!project || !newStepTitle.trim() || addingStep) return;
    setAddingStep(true);
    try {
      await dataProvider.addBuildPaintStep(project.id, newStepTitle.trim());
      setNewStepTitle("");
      const stepsData = await dataProvider.listBuildPaintSteps(project.id);
      setSteps(stepsData);
    } catch (err: unknown) {
      Alert.alert("Error", err?.message || "Failed to add step");
    } finally {
      setAddingStep(false);
    }
  };

  const handleToggleStep = async (stepId: string, currentIsDone: boolean) => {
    try {
      await dataProvider.toggleBuildPaintStep(stepId, !currentIsDone);
      const stepsData = await dataProvider.listBuildPaintSteps(projectId);
      setSteps(stepsData);
    } catch (err: unknown) {
      Alert.alert("Error", err?.message || "Failed to toggle step");
    }
  };

  const handleAddNote = async () => {
    if (!project || !newNoteBody.trim() || addingNote) return;
    setAddingNote(true);
    try {
      await dataProvider.addBuildPaintNote(project.id, newNoteBody.trim());
      setNewNoteBody("");
      const notesData = await dataProvider.listBuildPaintNotes(project.id);
      setNotes(notesData);
    } catch (err: unknown) {
      Alert.alert("Error", err?.message || "Failed to add note");
    } finally {
      setAddingNote(false);
    }
  };

  if (loading) {
    return (
      <>
        <Stack.Screen options={{ headerTitle: "Project" }} />
        <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.accent} />
          </View>
        </SafeAreaView>
      </>
    );
  }

  if (error || !project) {
    return (
      <>
        <Stack.Screen options={{ headerTitle: "Project" }} />
        <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
          <View style={styles.loadingContainer}>
            <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
            <Text style={[styles.errorText, { color: colors.text }]}>{error || "Project not found"}</Text>
            <AnimatedPressable
              style={[styles.backBtn, { borderColor: colors.border }]}
              onPress={() => router.back()}
              accessibilityRole="button"
              accessibilityLabel="Go back"
            >
              <Text style={[styles.backBtnText, { color: colors.text }]}>Go back</Text>
            </AnimatedPressable>
          </View>
        </SafeAreaView>
      </>
    );
  }

  const doneSteps = steps.filter((s) => s.isDone).length;
  const totalSteps = steps.length;

  return (
    <>
      <Stack.Screen options={{ headerTitle: project.title }} />
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["left", "right"]}>
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={{ flex: 1 }}
          keyboardVerticalOffset={Platform.OS === "ios" ? 88 : 0}
        >
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Header Card */}
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.headerRow}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.projectTitle, { color: colors.text }]}>{project.title}</Text>
                {project.category && (
                  <Text style={[styles.projectCategory, { color: colors.muted }]}>{project.category}</Text>
                )}
              </View>
              <View style={styles.completeToggle}>
                <Text style={[styles.completeLabel, { color: colors.muted }]}>Complete</Text>
                {togglingComplete ? (
                  <ActivityIndicator size="small" color={colors.accent} />
                ) : (
                  <Switch
                    value={project.isCompleted}
                    onValueChange={handleToggleComplete}
                    trackColor={{ false: colors.border, true: "#34D399" }}
                    thumbColor={project.isCompleted ? "#fff" : "#fff"}
                    accessibilityLabel="Mark project as complete"
                  />
                )}
              </View>
            </View>

            {/* Progress section */}
            <View style={styles.progressSection}>
              <View style={styles.progressHeader}>
                <Text style={[styles.progressLabel, { color: colors.text }]}>Progress</Text>
                <Text style={[styles.progressValue, { color: colors.accent }]}>{pendingPercent}%</Text>
              </View>
              <View style={[styles.progressTrack, { backgroundColor: colors.border }]}>
                <View
                  style={[
                    styles.progressFill,
                    {
                      width: `${Math.min(Math.max(pendingPercent, 0), 100)}%`,
                      backgroundColor: project.isCompleted ? "#34D399" : colors.accent,
                    },
                  ]}
                />
              </View>
              <View style={styles.progressControls}>
                <AnimatedPressable
                  style={[styles.percentBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
                  onPress={() => setPendingPercent(Math.max(0, pendingPercent - 5))}
                  accessibilityRole="button"
                  accessibilityLabel="Decrease progress by 5 percent"
                >
                  <Text style={[styles.percentBtnText, { color: colors.text }]}>-5</Text>
                </AnimatedPressable>
                <AnimatedPressable
                  style={[styles.percentBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
                  onPress={() => setPendingPercent(Math.min(100, pendingPercent + 5))}
                  accessibilityRole="button"
                  accessibilityLabel="Increase progress by 5 percent"
                >
                  <Text style={[styles.percentBtnText, { color: colors.text }]}>+5</Text>
                </AnimatedPressable>
                <AnimatedPressable
                  style={[styles.percentBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
                  onPress={() => setPendingPercent(Math.min(100, pendingPercent + 10))}
                  accessibilityRole="button"
                  accessibilityLabel="Increase progress by 10 percent"
                >
                  <Text style={[styles.percentBtnText, { color: colors.text }]}>+10</Text>
                </AnimatedPressable>
                <AnimatedPressable
                  style={[
                    styles.saveBtn,
                    {
                      backgroundColor: pendingPercent !== project.percent ? colors.accent : colors.border,
                      opacity: savingProgress ? 0.7 : 1,
                    },
                  ]}
                  onPress={handleSaveProgress}
                  disabled={pendingPercent === project.percent || savingProgress}
                  accessibilityRole="button"
                  accessibilityLabel="Save progress"
                >
                  {savingProgress ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : (
                    <Text style={styles.saveBtnText}>Save</Text>
                  )}
                </AnimatedPressable>
              </View>
            </View>

            {/* Notes */}
            {project.notes && (
              <View style={[styles.notesSection, { borderTopColor: colors.border }]}>
                <Text style={[styles.sectionLabel, { color: colors.muted }]}>Project Notes</Text>
                <Text style={[styles.notesText, { color: colors.text }]}>{project.notes}</Text>
              </View>
            )}
          </View>

          {/* Steps Card */}
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Steps</Text>
              <Text style={[styles.cardSubtitle, { color: colors.muted }]}>
                {doneSteps}/{totalSteps} completed
              </Text>
            </View>

            {steps.length === 0 ? (
              <Text style={[styles.emptyText, { color: colors.muted }]}>No steps added yet</Text>
            ) : (
              <View style={styles.stepsList}>
                {steps.map((step) => (
                  <AnimatedPressable
                    key={step.id}
                    style={styles.stepRow}
                    onPress={() => handleToggleStep(step.id, step.isDone)}
                    accessibilityRole="button"
                    accessibilityLabel={`${step.title}, ${step.isDone ? 'completed' : 'not completed'}`}
                  >
                    <View
                      style={[
                        styles.stepCheckbox,
                        {
                          backgroundColor: step.isDone ? colors.accent : "transparent",
                          borderColor: step.isDone ? colors.accent : colors.border,
                        },
                      ]}
                    >
                      {step.isDone && <Ionicons name="checkmark" size={14} color="#fff" />}
                    </View>
                    <Text
                      style={[
                        styles.stepTitle,
                        { color: colors.text },
                        step.isDone && { textDecorationLine: "line-through", color: colors.muted },
                      ]}
                    >
                      {step.title}
                    </Text>
                  </AnimatedPressable>
                ))}
              </View>
            )}

            {/* Add step input */}
            <View style={styles.addRow}>
              <TextInput
                value={newStepTitle}
                onChangeText={setNewStepTitle}
                placeholder="Add a step..."
                placeholderTextColor={colors.muted}
                accessibilityLabel="New step title"
                style={[
                  styles.addInput,
                  { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
                ]}
              />
              <AnimatedPressable
                style={[
                  styles.addBtn,
                  {
                    backgroundColor: newStepTitle.trim() ? colors.accent : colors.border,
                    opacity: addingStep ? 0.7 : 1,
                  },
                ]}
                onPress={handleAddStep}
                disabled={!newStepTitle.trim() || addingStep}
                accessibilityRole="button"
                accessibilityLabel="Add step"
              >
                {addingStep ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Ionicons name="add" size={20} color="#fff" />
                )}
              </AnimatedPressable>
            </View>
          </View>

          {/* Notes Card */}
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Progress Notes</Text>
              <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{notes.length} entries</Text>
            </View>

            {notes.length === 0 ? (
              <Text style={[styles.emptyText, { color: colors.muted }]}>No notes added yet</Text>
            ) : (
              <View style={styles.notesList}>
                {notes.map((note, idx) => (
                  <View
                    key={note.id}
                    style={[
                      styles.noteItem,
                      idx < notes.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border },
                    ]}
                  >
                    <Text style={[styles.noteDate, { color: colors.muted }]}>
                      {formatDate(note.createdAt)}
                    </Text>
                    <Text style={[styles.noteBody, { color: colors.text }]}>{note.body}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Add note input */}
            <View style={styles.addNoteRow}>
              <TextInput
                value={newNoteBody}
                onChangeText={setNewNoteBody}
                placeholder="Add a note..."
                placeholderTextColor={colors.muted}
                multiline
                accessibilityLabel="New note"
                style={[
                  styles.addNoteInput,
                  { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
                ]}
              />
              <AnimatedPressable
                style={[
                  styles.addNoteBtn,
                  {
                    backgroundColor: newNoteBody.trim() ? colors.accent : colors.border,
                    opacity: addingNote ? 0.7 : 1,
                  },
                ]}
                onPress={handleAddNote}
                disabled={!newNoteBody.trim() || addingNote}
                accessibilityRole="button"
                accessibilityLabel={addingNote ? 'Adding note' : 'Add note'}
              >
                {addingNote ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.addNoteBtnText}>Add Note</Text>
                )}
              </AnimatedPressable>
            </View>
          </View>

          <View style={{ height: 32 }} />
        </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </>
  );
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 32,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 32,
  },
  errorText: {
    fontSize: 16,
    fontWeight: "600",
    marginTop: 16,
    textAlign: "center",
  },
  backBtn: {
    marginTop: 24,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
  backBtnText: {
    fontSize: 14,
    fontWeight: "600",
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  projectTitle: {
    fontSize: 20,
    fontWeight: "700",
  },
  projectCategory: {
    fontSize: 13,
    marginTop: 4,
  },
  completeToggle: {
    alignItems: "center",
  },
  completeLabel: {
    fontSize: 11,
    marginBottom: 4,
  },
  progressSection: {
    marginTop: 20,
  },
  progressHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  progressLabel: {
    fontSize: 14,
    fontWeight: "600",
  },
  progressValue: {
    fontSize: 18,
    fontWeight: "700",
  },
  progressTrack: {
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 4,
  },
  progressControls: {
    flexDirection: "row",
    marginTop: 12,
    gap: 8,
  },
  percentBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  percentBtnText: {
    fontSize: 13,
    fontWeight: "600",
  },
  saveBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  saveBtnText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#fff",
  },
  notesSection: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 6,
  },
  notesText: {
    fontSize: 14,
    lineHeight: 20,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: "700",
  },
  cardSubtitle: {
    fontSize: 12,
  },
  emptyText: {
    fontSize: 13,
    fontStyle: "italic",
    marginBottom: 12,
  },
  stepsList: {
    marginBottom: 12,
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
  },
  stepCheckbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  stepTitle: {
    flex: 1,
    fontSize: 14,
  },
  addRow: {
    flexDirection: "row",
    gap: 8,
  },
  addInput: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  addBtn: {
    width: 44,
    height: 44,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  notesList: {
    marginBottom: 12,
  },
  noteItem: {
    paddingVertical: 12,
  },
  noteDate: {
    fontSize: 11,
    marginBottom: 4,
  },
  noteBody: {
    fontSize: 14,
    lineHeight: 20,
  },
  addNoteRow: {
    gap: 8,
  },
  addNoteInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    minHeight: 60,
    textAlignVertical: "top",
  },
  addNoteBtn: {
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  addNoteBtnText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#fff",
  },
});
