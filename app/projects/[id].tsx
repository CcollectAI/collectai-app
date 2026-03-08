/**
 * Project Detail Screen — View and edit build/paint project.
 * Category-aware with linked item card, template steps, and accent colors.
 */

import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  Switch,
  KeyboardAvoidingView,
  Platform,
  Image,
  RefreshControl,
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
import { CATEGORIES, CATEGORY_VISUAL } from "@/data/categories";
import { isBuildableCategory, getStepTemplateForCategory } from "@/constants/buildStepTemplates";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import logger from "@/utils/logger";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { useToast } from '@/components/Toast';

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

  // ── Paint Recipes state ─────────────────────────────────────────────
  type PaintEntry = { brand: string; color: string; type: string };
  type PaintRecipe = { name: string; paints: PaintEntry[]; notes: string };
  const [paintRecipes, setPaintRecipes] = useState<PaintRecipe[]>([]);
  const [recipeExpanded, setRecipeExpanded] = useState(false);
  const [addingRecipe, setAddingRecipe] = useState(false);
  const [savingRecipes, setSavingRecipes] = useState(false);
  const [editingRecipeIdx, setEditingRecipeIdx] = useState<number | null>(null);
  // New recipe form
  const [newRecipeName, setNewRecipeName] = useState('');
  const [newRecipePaints, setNewRecipePaints] = useState<PaintEntry[]>([]);
  const [newRecipeNotes, setNewRecipeNotes] = useState('');
  // New paint entry form
  const [newPaintBrand, setNewPaintBrand] = useState('');
  const [newPaintColor, setNewPaintColor] = useState('');
  const [newPaintType, setNewPaintType] = useState<string>('base');

  const PAINT_TYPES = ['base', 'layer', 'shade', 'technical', 'contrast', 'dry', 'texture', 'spray'] as const;
  const PAINT_BRANDS = ['Citadel', 'Vallejo', 'Army Painter', 'AK Interactive', 'Scale75', 'Tamiya', 'Mr. Color', 'Other'] as const;
  const PAINT_CATEGORIES = ['warhammer', 'gunpla', 'scale_models'] as const;
  const showPaintRecipes = PAINT_CATEGORIES.includes(project?.categoryId as typeof PAINT_CATEGORIES[number]);

  // Always use app theme accent for consistency
  const accentColor = colors.accent;

  const categoryName = useMemo(() => {
    if (!project?.categoryId) return project?.category;
    return CATEGORIES.find((c) => c.id === project.categoryId)?.name ?? project.category;
  }, [project?.categoryId, project?.category]);

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
        // Load paint recipes from project data
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
      showToast({ message: (err as Error)?.message || "Failed to save progress", type: 'error' });
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
      showToast({ message: (err as Error)?.message || "Failed to toggle complete", type: 'error' });
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
      showToast({ message: (err as Error)?.message || "Failed to add step", type: 'error' });
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
      showToast({ message: (err as Error)?.message || "Failed to toggle step", type: 'error' });
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
      showToast({ message: (err as Error)?.message || "Failed to add note", type: 'error' });
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
      showToast({ message: (err as Error)?.message || "Failed to apply template", type: 'error' });
    } finally {
      setApplyingTemplate(false);
    }
  };

  // ── Paint Recipes handlers ───────────────────────────────────────────
  const savePaintRecipes = useCallback(async (recipes: PaintRecipe[]) => {
    if (!project) return;
    setSavingRecipes(true);
    try {
      await dataProvider.updateBuildPaintProject(project.id, { paintRecipes: recipes });
      setPaintRecipes(recipes);
      showToast({ message: 'Paint recipes saved', type: 'success' });
    } catch (err: unknown) {
      showToast({ message: (err as Error)?.message || 'Failed to save recipes', type: 'error' });
    } finally {
      setSavingRecipes(false);
    }
  }, [project]);

  const handleAddRecipe = () => {
    if (!newRecipeName.trim()) return;
    const recipe: PaintRecipe = {
      name: newRecipeName.trim(),
      paints: newRecipePaints,
      notes: newRecipeNotes.trim(),
    };
    const updated = [...paintRecipes, recipe];
    savePaintRecipes(updated);
    setNewRecipeName('');
    setNewRecipePaints([]);
    setNewRecipeNotes('');
    setAddingRecipe(false);
  };

  const handleDeleteRecipe = (idx: number) => {
    const updated = paintRecipes.filter((_, i) => i !== idx);
    savePaintRecipes(updated);
  };

  const handleAddPaintToRecipe = () => {
    if (!newPaintBrand.trim() || !newPaintColor.trim()) return;
    setNewRecipePaints((prev) => [
      ...prev,
      { brand: newPaintBrand.trim(), color: newPaintColor.trim(), type: newPaintType },
    ]);
    setNewPaintBrand('');
    setNewPaintColor('');
    setNewPaintType('base');
  };

  const handleRemovePaintFromRecipe = (paintIdx: number) => {
    setNewRecipePaints((prev) => prev.filter((_, i) => i !== paintIdx));
  };

  // Whether to show "Apply Template" button
  const canApplyTemplate = project?.categoryId &&
    isBuildableCategory(project.categoryId) &&
    steps.length === 0;

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
        </View>
      </>
    );
  }

  const doneSteps = steps.filter((s) => s.isDone).length;
  const totalSteps = steps.length;
  const progressBarColor = project.isCompleted ? "#34D399" : accentColor || colors.accent;

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
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#81D8D0" />}
        >
          {/* Header Card */}
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.headerRow}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.projectTitle, { color: colors.text }]}>{project.title}</Text>
                {/* Category pill */}
                {categoryName && (
                  <View style={styles.categoryRow}>
                    {accentColor && <View style={[styles.catDot, { backgroundColor: accentColor }]} />}
                    <Text style={[styles.projectCategory, { color: accentColor || colors.muted }]}>
                      {categoryName}
                    </Text>
                  </View>
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
                    thumbColor="#fff"
                    accessibilityLabel="Mark project as complete"
                  />
                )}
              </View>
            </View>

            {/* Progress section */}
            <View style={styles.progressSection}>
              <View style={styles.progressHeader}>
                <Text style={[styles.progressLabel, { color: colors.text }]}>Progress</Text>
                <Text style={[styles.progressValue, { color: progressBarColor }]}>{pendingPercent}%</Text>
              </View>
              <View style={[styles.progressTrack, { backgroundColor: colors.border }]}>
                <View
                  style={[
                    styles.progressFill,
                    {
                      width: `${Math.min(Math.max(pendingPercent, 0), 100)}%`,
                      backgroundColor: progressBarColor,
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
                      backgroundColor: pendingPercent !== project.percent ? (accentColor || colors.accent) : colors.border,
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

          {/* Linked Item Card */}
          {project.itemId && (project.itemName || project.itemImageUrl) && (
            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.cardHeader}>
                <Text style={[styles.cardTitle, { color: colors.text }]}>Linked Item</Text>
                <Ionicons name="link-outline" size={16} color={colors.muted} />
              </View>
              <View style={styles.linkedItemRow}>
                {project.itemImageUrl && (
                  <Image source={{ uri: project.itemImageUrl }} style={styles.linkedItemImg} />
                )}
                <View style={{ flex: 1 }}>
                  <Text style={[styles.linkedItemName, { color: colors.text }]} numberOfLines={2}>
                    {project.itemName ?? "Linked item"}
                  </Text>
                  {categoryName && (
                    <View style={styles.linkedItemMeta}>
                      {accentColor && <View style={[styles.catDotSm, { backgroundColor: accentColor }]} />}
                      <Text style={[styles.linkedItemCat, { color: colors.muted }]}>{categoryName}</Text>
                    </View>
                  )}
                </View>
              </View>
            </View>
          )}

          {/* Steps Card */}
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Steps</Text>
              <Text style={[styles.cardSubtitle, { color: colors.muted }]}>
                {doneSteps}/{totalSteps} completed
              </Text>
            </View>

            {/* Apply Template button (shown when no steps + has category template) */}
            {canApplyTemplate && templateForCategory && (
              <AnimatedPressable
                onPress={handleApplyTemplate}
                disabled={applyingTemplate}
                style={[styles.applyTemplateBtn, { backgroundColor: (accentColor || colors.accent) + '15', borderColor: accentColor || colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel={`Apply ${templateForCategory.displayName} workflow with ${templateForCategory.steps.length} steps`}
              >
                {applyingTemplate ? (
                  <ActivityIndicator size="small" color={accentColor || colors.accent} />
                ) : (
                  <>
                    <Ionicons name="flash-outline" size={18} color={accentColor || colors.accent} />
                    <View style={{ flex: 1, marginLeft: 8 }}>
                      <Text style={[styles.applyTemplateTitle, { color: accentColor || colors.accent }]}>
                        Use {templateForCategory.displayName} workflow?
                      </Text>
                      <Text style={[styles.applyTemplateHint, { color: colors.muted }]}>
                        {templateForCategory.steps.length} steps will be added
                      </Text>
                    </View>
                    <Ionicons name="arrow-forward" size={16} color={accentColor || colors.accent} />
                  </>
                )}
              </AnimatedPressable>
            )}

            {steps.length === 0 && !canApplyTemplate ? (
              <Text style={[styles.emptyText, { color: colors.muted }]}>No steps added yet</Text>
            ) : steps.length > 0 ? (
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
                          backgroundColor: step.isDone ? (accentColor || colors.accent) : "transparent",
                          borderColor: step.isDone ? (accentColor || colors.accent) : colors.border,
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
            ) : null}

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
                    backgroundColor: newStepTitle.trim() ? (accentColor || colors.accent) : colors.border,
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
                    backgroundColor: newNoteBody.trim() ? (accentColor || colors.accent) : colors.border,
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

          {/* Paint Recipes Card — for Warhammer, Gunpla, Scale Models */}
          {showPaintRecipes && (
            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.cardHeader}>
                <Text style={[styles.cardTitle, { color: colors.text }]}>Paint Recipes</Text>
                <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{paintRecipes.length} recipes</Text>
              </View>

              {paintRecipes.length === 0 && !addingRecipe ? (
                <Text style={[styles.emptyText, { color: colors.muted }]}>
                  No paint recipes yet. Add your paint lists and technique notes.
                </Text>
              ) : (
                <View style={styles.recipesList}>
                  {paintRecipes.map((recipe, idx) => (
                    <View
                      key={idx}
                      style={[
                        styles.recipeItem,
                        idx < paintRecipes.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border },
                      ]}
                    >
                      <View style={styles.recipeHeader}>
                        <View style={styles.recipeHeaderLeft}>
                          <Ionicons name="color-palette-outline" size={16} color={accentColor || colors.accent} />
                          <Text style={[styles.recipeName, { color: colors.text }]}>{recipe.name}</Text>
                        </View>
                        <AnimatedPressable
                          onPress={() => handleDeleteRecipe(idx)}
                          hitSlop={8}
                          accessibilityRole="button"
                          accessibilityLabel={`Delete recipe: ${recipe.name}`}
                        >
                          <Ionicons name="close-circle-outline" size={18} color={colors.muted} />
                        </AnimatedPressable>
                      </View>
                      {/* Paints list */}
                      {recipe.paints.length > 0 && (
                        <View style={styles.paintsList}>
                          {recipe.paints.map((paint, pIdx) => (
                            <View key={pIdx} style={styles.paintRow}>
                              <View style={[styles.paintTypeDot, { backgroundColor: getPaintTypeColor(paint.type) }]} />
                              <Text style={[styles.paintText, { color: colors.text }]}>
                                {paint.brand} — {paint.color}
                              </Text>
                              <Text style={[styles.paintTypeLabel, { color: colors.muted }]}>
                                {paint.type}
                              </Text>
                            </View>
                          ))}
                        </View>
                      )}
                      {recipe.notes ? (
                        <Text style={[styles.recipeNotes, { color: colors.muted }]}>{recipe.notes}</Text>
                      ) : null}
                    </View>
                  ))}
                </View>
              )}

              {/* Add recipe form */}
              {addingRecipe ? (
                <View style={[styles.addRecipeForm, { borderColor: colors.border }]}>
                  <TextInput
                    value={newRecipeName}
                    onChangeText={setNewRecipeName}
                    placeholder="Recipe name (e.g. Base Skin Tone)"
                    placeholderTextColor={colors.muted}
                    style={[styles.addInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                    accessibilityLabel="Recipe name"
                  />

                  {/* Paints added so far */}
                  {newRecipePaints.length > 0 && (
                    <View style={styles.paintsList}>
                      {newRecipePaints.map((paint, pIdx) => (
                        <View key={pIdx} style={styles.paintRow}>
                          <View style={[styles.paintTypeDot, { backgroundColor: getPaintTypeColor(paint.type) }]} />
                          <Text style={[styles.paintText, { color: colors.text }]}>
                            {paint.brand} — {paint.color}
                          </Text>
                          <Text style={[styles.paintTypeLabel, { color: colors.muted }]}>{paint.type}</Text>
                          <AnimatedPressable
                            onPress={() => handleRemovePaintFromRecipe(pIdx)}
                            hitSlop={8}
                            accessibilityRole="button"
                            accessibilityLabel={`Remove ${paint.color}`}
                          >
                            <Ionicons name="close" size={14} color={colors.muted} />
                          </AnimatedPressable>
                        </View>
                      ))}
                    </View>
                  )}

                  {/* Add paint entry row */}
                  <View style={styles.addPaintRow}>
                    <View style={{ flex: 1 }}>
                      <TextInput
                        value={newPaintBrand}
                        onChangeText={setNewPaintBrand}
                        placeholder="Brand"
                        placeholderTextColor={colors.muted}
                        style={[styles.paintInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                        accessibilityLabel="Paint brand"
                      />
                    </View>
                    <View style={{ flex: 1 }}>
                      <TextInput
                        value={newPaintColor}
                        onChangeText={setNewPaintColor}
                        placeholder="Color name"
                        placeholderTextColor={colors.muted}
                        style={[styles.paintInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                        accessibilityLabel="Paint color"
                      />
                    </View>
                  </View>

                  {/* Paint type pills */}
                  <View style={styles.paintTypePillsRow}>
                    {PAINT_TYPES.map((pt) => (
                      <AnimatedPressable
                        key={pt}
                        onPress={() => setNewPaintType(pt)}
                        style={[
                          styles.paintTypePill,
                          {
                            backgroundColor: newPaintType === pt ? (accentColor || colors.accent) : colors.background,
                            borderColor: newPaintType === pt ? (accentColor || colors.accent) : colors.border,
                          },
                        ]}
                        accessibilityRole="button"
                        accessibilityState={{ selected: newPaintType === pt }}
                        accessibilityLabel={`Paint type: ${pt}`}
                      >
                        <Text style={[
                          styles.paintTypePillText,
                          { color: newPaintType === pt ? '#fff' : colors.muted },
                        ]}>{pt}</Text>
                      </AnimatedPressable>
                    ))}
                  </View>

                  <AnimatedPressable
                    onPress={handleAddPaintToRecipe}
                    disabled={!newPaintBrand.trim() || !newPaintColor.trim()}
                    style={[
                      styles.addPaintBtn,
                      {
                        backgroundColor: newPaintBrand.trim() && newPaintColor.trim() ? (accentColor || colors.accent) + '15' : colors.background,
                        borderColor: newPaintBrand.trim() && newPaintColor.trim() ? (accentColor || colors.accent) : colors.border,
                      },
                    ]}
                    accessibilityRole="button"
                    accessibilityLabel="Add paint to recipe"
                  >
                    <Ionicons name="add" size={16} color={newPaintBrand.trim() && newPaintColor.trim() ? (accentColor || colors.accent) : colors.muted} />
                    <Text style={[styles.addPaintBtnText, { color: newPaintBrand.trim() && newPaintColor.trim() ? (accentColor || colors.accent) : colors.muted }]}>Add Paint</Text>
                  </AnimatedPressable>

                  {/* Technique notes */}
                  <TextInput
                    value={newRecipeNotes}
                    onChangeText={setNewRecipeNotes}
                    placeholder="Technique notes (e.g. thin coats, wet blend)"
                    placeholderTextColor={colors.muted}
                    multiline
                    style={[styles.addNoteInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                    accessibilityLabel="Technique notes"
                  />

                  {/* Save / Cancel */}
                  <View style={styles.addRow}>
                    <AnimatedPressable
                      onPress={() => { setAddingRecipe(false); setNewRecipeName(''); setNewRecipePaints([]); setNewRecipeNotes(''); }}
                      style={[styles.percentBtn, { borderColor: colors.border, flex: 1, alignItems: 'center' as const }]}
                      accessibilityRole="button"
                      accessibilityLabel="Cancel"
                    >
                      <Text style={[styles.percentBtnText, { color: colors.muted }]}>Cancel</Text>
                    </AnimatedPressable>
                    <AnimatedPressable
                      onPress={handleAddRecipe}
                      disabled={!newRecipeName.trim() || savingRecipes}
                      style={[
                        styles.saveBtn,
                        {
                          backgroundColor: newRecipeName.trim() ? (accentColor || colors.accent) : colors.border,
                          opacity: savingRecipes ? 0.7 : 1,
                          flex: 1,
                        },
                      ]}
                      accessibilityRole="button"
                      accessibilityLabel="Save recipe"
                    >
                      {savingRecipes ? (
                        <ActivityIndicator size="small" color="#fff" />
                      ) : (
                        <Text style={styles.saveBtnText}>Save Recipe</Text>
                      )}
                    </AnimatedPressable>
                  </View>
                </View>
              ) : (
                <AnimatedPressable
                  onPress={() => setAddingRecipe(true)}
                  style={[styles.applyTemplateBtn, { backgroundColor: (accentColor || colors.accent) + '15', borderColor: accentColor || colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Add a new paint recipe"
                >
                  <Ionicons name="add-circle-outline" size={18} color={accentColor || colors.accent} />
                  <View style={{ flex: 1, marginLeft: 8 }}>
                    <Text style={[styles.applyTemplateTitle, { color: accentColor || colors.accent }]}>
                      Add Paint Recipe
                    </Text>
                    <Text style={[styles.applyTemplateHint, { color: colors.muted }]}>
                      Track paints, brands, and techniques
                    </Text>
                  </View>
                </AnimatedPressable>
              )}
            </View>
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

function getPaintTypeColor(type: string): string {
  const map: Record<string, string> = {
    base: '#3B82F6',
    layer: '#22C55E',
    shade: '#8B5CF6',
    technical: '#F59E0B',
    contrast: '#EC4899',
    dry: '#94A3B8',
    texture: '#D97706',
    spray: '#6366F1',
  };
  return map[type] || '#94A3B8';
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
  categoryRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 6,
  },
  catDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  catDotSm: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  projectCategory: {
    fontSize: 13,
    fontWeight: "500",
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
  // Linked item card
  linkedItemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  linkedItemImg: {
    width: 56,
    height: 56,
    borderRadius: 10,
  },
  linkedItemName: {
    fontSize: 15,
    fontWeight: "600",
  },
  linkedItemMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
  },
  linkedItemCat: {
    fontSize: 12,
  },
  // Apply template
  applyTemplateBtn: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
  },
  applyTemplateTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  applyTemplateHint: {
    fontSize: 12,
    marginTop: 2,
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

  // ── Paint Recipes ──────────────────────────────────────────────────────
  recipesList: {
    marginBottom: 12,
  },
  recipeItem: {
    paddingVertical: 12,
  },
  recipeHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  recipeHeaderLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  recipeName: {
    fontSize: 15,
    fontWeight: "700",
    flex: 1,
  },
  paintsList: {
    marginTop: 6,
    gap: 4,
  },
  paintRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 3,
  },
  paintTypeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  paintText: {
    fontSize: 13,
    flex: 1,
  },
  paintTypeLabel: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "capitalize" as const,
  },
  recipeNotes: {
    fontSize: 12,
    lineHeight: 17,
    marginTop: 6,
    fontStyle: "italic" as const,
  },
  addRecipeForm: {
    marginTop: 8,
    gap: 8,
    borderTopWidth: 1,
    paddingTop: 12,
  },
  addPaintRow: {
    flexDirection: "row",
    gap: 8,
  },
  paintInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
  },
  paintTypePillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  paintTypePill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    borderWidth: 1,
  },
  paintTypePillText: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "capitalize" as const,
  },
  addPaintBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  addPaintBtnText: {
    fontSize: 13,
    fontWeight: "600",
  },
});
