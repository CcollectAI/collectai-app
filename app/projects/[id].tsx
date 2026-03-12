/**
 * Project Detail Screen — View and edit build/paint project.
 * Category-aware with linked item card, template steps, and accent colors.
 */

import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
} from "react-native";
import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  dataProvider,
  type BuildPaintProject,
  type BuildPaintStep,
  type BuildPaintNote,
} from "@/data";
import type { PaintRecipe } from "@/data/types";
import { CATEGORIES } from "@/data/categories";
import { isBuildableCategory, getStepTemplateForCategory } from "@/constants/buildStepTemplates";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import logger from "@/utils/logger";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { QuickNavBar } from "@/components/QuickNavBar";
import { useToast } from "@/components/Toast";
import { ProjectHeaderCard } from "@/components/projects/ProjectHeaderCard";
import { LinkedItemCard } from "@/components/projects/LinkedItemCard";
import { ProjectStepsCard } from "@/components/projects/ProjectStepsCard";
import { ProjectNotesCard } from "@/components/projects/ProjectNotesCard";
import { PaintRecipesCard } from "@/components/projects/PaintRecipesCard";

const PAINT_CATEGORIES = ["warhammer", "gunpla", "scale_models"] as const;

function ProjectDetailScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
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

  // Apply template
  const [applyingTemplate, setApplyingTemplate] = useState(false);

  // Pull-to-refresh
  const [refreshing, setRefreshing] = useState(false);

  // Paint recipes
  const [paintRecipes, setPaintRecipes] = useState<PaintRecipe[]>([]);
  const [savingRecipes, setSavingRecipes] = useState(false);

  const accentColor = colors.accent;

  const categoryName = useMemo(() => {
    if (!project?.categoryId) return project?.category;
    return CATEGORIES.find((c) => c.id === project.categoryId)?.name ?? project.category;
  }, [project?.categoryId, project?.category]);

  const showPaintRecipes = PAINT_CATEGORIES.includes(
    project?.categoryId as (typeof PAINT_CATEGORIES)[number],
  );

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
        if (found.paintRecipes && Array.isArray(found.paintRecipes)) {
          setPaintRecipes(found.paintRecipes as PaintRecipe[]);
        }
      }
      setSteps(stepsData);
      setNotes(notesData);
      setError(null);
    } catch (err: unknown) {
      logger.warn("[ProjectDetail] loadProject error:", err);
      setError((err as Error)?.message || "Failed to load project");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadProject();
    setRefreshing(false);
  }, [loadProject]);

  const handleSaveProgress = async () => {
    if (!project || savingProgress) return;
    setSavingProgress(true);
    try {
      const newStatus = pendingPercent >= 100 ? "completed" : pendingPercent > 0 ? "active" : "backlog";
      await dataProvider.setBuildPaintProgress(project.id, pendingPercent, newStatus);
      await loadProject();
    } catch (err: unknown) {
      showToast({ message: (err as Error)?.message || "Failed to save progress", type: "error" });
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
      showToast({ message: (err as Error)?.message || "Failed to toggle complete", type: "error" });
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
      showToast({ message: (err as Error)?.message || "Failed to add step", type: "error" });
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
      showToast({ message: (err as Error)?.message || "Failed to toggle step", type: "error" });
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
      showToast({ message: (err as Error)?.message || "Failed to add note", type: "error" });
    } finally {
      setAddingNote(false);
    }
  };

  const handleApplyTemplate = async () => {
    if (!project?.categoryId || applyingTemplate) return;
    setApplyingTemplate(true);
    try {
      await dataProvider.applyStepTemplate(project.id, project.categoryId);
      const stepsData = await dataProvider.listBuildPaintSteps(project.id);
      setSteps(stepsData);
    } catch (err: unknown) {
      showToast({ message: (err as Error)?.message || "Failed to apply template", type: "error" });
    } finally {
      setApplyingTemplate(false);
    }
  };

  const savePaintRecipes = useCallback(
    async (recipes: PaintRecipe[]) => {
      if (!project) return;
      setSavingRecipes(true);
      try {
        await dataProvider.updateBuildPaintProject(project.id, { paintRecipes: recipes });
        setPaintRecipes(recipes);
        showToast({ message: "Paint recipes saved", type: "success" });
      } catch (err: unknown) {
        showToast({ message: (err as Error)?.message || "Failed to save recipes", type: "error" });
      } finally {
        setSavingRecipes(false);
      }
    },
    [project, showToast],
  );

  const handleDeleteRecipe = useCallback(
    (idx: number) => {
      const updated = paintRecipes.filter((_, i) => i !== idx);
      savePaintRecipes(updated);
    },
    [paintRecipes, savePaintRecipes],
  );

  // Whether to show "Apply Template" button
  const canApplyTemplate = !!(
    project?.categoryId &&
    isBuildableCategory(project.categoryId) &&
    steps.length === 0
  );

  const templateForCategory = canApplyTemplate
    ? getStepTemplateForCategory(project?.categoryId)
    : null;

  if (loading) {
    return (
      <>
        <Stack.Screen options={{ headerTitle: "Project" }} />
        <View style={[styles.safe, { backgroundColor: colors.background }]}>
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.accent} />
          </View>
        </View>
      </>
    );
  }

  if (error || !project) {
    return (
      <>
        <Stack.Screen options={{ headerTitle: "Project" }} />
        <View style={[styles.safe, { backgroundColor: colors.background }]}>
          <View style={styles.loadingContainer}>
            <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
            <Text style={[styles.errorText, { color: colors.text }]}>
              {error || "Project not found"}
            </Text>
            <AnimatedPressable
              style={[styles.backBtn, { borderColor: colors.border }]}
              onPress={() => router.back()}
              accessibilityRole="button"
              accessibilityLabel="Go back"
            >
              <Text style={[styles.backBtnText, { color: colors.text }]}>Go back</Text>
            </AnimatedPressable>
          </View>
        </View>
      </>
    );
  }

  return (
    <>
      <Stack.Screen options={{ headerTitle: project.title }} />
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={{ flex: 1 }}
          keyboardVerticalOffset={Platform.OS === "ios" ? 88 : 0}
        >
          <ScrollView
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
            }
          >
            <ProjectHeaderCard
              project={project}
              categoryName={categoryName}
              accentColor={accentColor}
              pendingPercent={pendingPercent}
              savingProgress={savingProgress}
              togglingComplete={togglingComplete}
              onDecrease={() => setPendingPercent(Math.max(0, pendingPercent - 5))}
              onIncrease5={() => setPendingPercent(Math.min(100, pendingPercent + 5))}
              onIncrease10={() => setPendingPercent(Math.min(100, pendingPercent + 10))}
              onSaveProgress={handleSaveProgress}
              onToggleComplete={handleToggleComplete}
            />

            <LinkedItemCard
              project={project}
              categoryName={categoryName}
              accentColor={accentColor}
            />

            <ProjectStepsCard
              steps={steps}
              accentColor={accentColor}
              newStepTitle={newStepTitle}
              addingStep={addingStep}
              applyingTemplate={applyingTemplate}
              canApplyTemplate={canApplyTemplate}
              templateForCategory={templateForCategory}
              onChangeStepTitle={setNewStepTitle}
              onAddStep={handleAddStep}
              onToggleStep={handleToggleStep}
              onApplyTemplate={handleApplyTemplate}
            />

            <ProjectNotesCard
              notes={notes}
              accentColor={accentColor}
              newNoteBody={newNoteBody}
              addingNote={addingNote}
              onChangeNoteBody={setNewNoteBody}
              onAddNote={handleAddNote}
            />

            {showPaintRecipes && (
              <PaintRecipesCard
                paintRecipes={paintRecipes}
                accentColor={accentColor}
                savingRecipes={savingRecipes}
                onSaveRecipes={savePaintRecipes}
                onDeleteRecipe={handleDeleteRecipe}
              />
            )}

            <View style={{ height: 32 }} />
          </ScrollView>
        </KeyboardAvoidingView>
        <QuickNavBar />
      </View>
    </>
  );
}

export default function ProjectDetailScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Project Detail">
      <ProjectDetailScreen />
    </ScreenErrorBoundary>
  );
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
});
