/**
 * Build & Paint Projects Screen — List view with Current/Completed sections.
 * Category-aware with structured pickers and step template preview.
 */

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
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
  FlatList,
  Image,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { dataProvider, type BuildPaintProject, type Item } from "@/data";
import { CATEGORIES, CATEGORY_VISUAL } from "@/data/categories";
import { BUILDABLE_CATEGORIES, getStepTemplateForCategory } from "@/constants/buildStepTemplates";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { useSettings } from "@/lib/settings";
import { formatPrice } from "@/lib/format";
import { SkeletonList } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import { fireHaptic, HapticIntent } from "@/haptics";
import logger from "@/utils/logger";
import { QuickNavBar } from "@/components/QuickNavBar";

const statusColor = (
  status: string | null | undefined,
  isCompleted: boolean,
  themeColors: { accent: string; muted: string; border: string },
) => {
  // Completed → success green tint
  if (isCompleted) return { bg: "#10B981" + "20", text: "#10B981" };
  const s = (status || "").toLowerCase();
  // Active → accent tint
  if (s === "active") return { bg: themeColors.accent + "20", text: themeColors.accent };
  // Backlog / default → muted tint
  return { bg: themeColors.muted + "15", text: themeColors.muted };
};

export default function BuildPaintProjectsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Build & Paint">
      <BuildPaintProjectsScreen />
    </ScreenErrorBoundary>
  );
}

function BuildPaintProjectsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  // Accept optional params from item detail "Start Build Project" button
  const params = useLocalSearchParams<{ linkItemId?: string; linkItemName?: string; linkCategoryId?: string }>();

  const [projects, setProjects] = useState<BuildPaintProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [creating, setCreating] = useState(false);
  const [showCategoryPicker, setShowCategoryPicker] = useState(false);
  const [showItemPicker, setShowItemPicker] = useState(false);
  const [showAllCategories, setShowAllCategories] = useState(false);
  const [categoryItems, setCategoryItems] = useState<Item[]>([]);
  const [loadingItems, setLoadingItems] = useState(false);
  const [showStepPreview, setShowStepPreview] = useState(false);

  const [refreshing, setRefreshing] = useState(false);
  const { showToast } = useToast();

  const loadProjects = useCallback(async () => {
    try {
      const data = await dataProvider.listBuildPaintProjects();
      setProjects(data);
      setError(null);
    } catch (err: unknown) {
      logger.warn("[BuildPaintProjects] loadProjects error:", err);
      setError((err as Error)?.message || "Failed to load projects");
    } finally {
      setLoading(false);
    }
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadProjects();
    setRefreshing(false);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
  }, [loadProjects, settings.hapticsEnabled]);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  // Auto-open create modal when navigated from item detail with params
  useEffect(() => {
    if (params.linkItemId && params.linkItemName) {
      setNewTitle(params.linkItemName);
      setSelectedItem({ id: params.linkItemId, name: params.linkItemName } as Item);
      if (params.linkCategoryId) {
        setSelectedCategoryId(params.linkCategoryId);
      }
      setShowCreateModal(true);
    }
  }, [params.linkItemId, params.linkItemName, params.linkCategoryId]);

  // Categories sorted: buildable first, then all others
  const sortedCategories = useMemo(() => {
    const buildable = CATEGORIES.filter((c) =>
      (BUILDABLE_CATEGORIES as readonly string[]).includes(c.id)
    );
    const others = CATEGORIES.filter(
      (c) => !(BUILDABLE_CATEGORIES as readonly string[]).includes(c.id)
    );
    return showAllCategories ? [...buildable, ...others] : buildable;
  }, [showAllCategories]);

  // Step template preview for selected category
  const selectedTemplate = useMemo(() => {
    if (!selectedCategoryId) return null;
    return getStepTemplateForCategory(selectedCategoryId);
  }, [selectedCategoryId]);

  // Load items when category is selected
  const handleSelectCategory = useCallback(async (catId: string) => {
    setSelectedCategoryId(catId);
    setSelectedItem(null);
    setShowCategoryPicker(false);

    // Load portfolio items for this category
    setLoadingItems(true);
    try {
      const items = await dataProvider.listItems();
      setCategoryItems(items.filter((i) => i.category === catId));
    } catch {
      setCategoryItems([]);
    } finally {
      setLoadingItems(false);
    }
  }, []);

  const handleSelectItem = useCallback((item: Item) => {
    setSelectedItem(item);
    setNewTitle(item.name);
    setShowItemPicker(false);
  }, []);

  const handleCreateProject = async () => {
    if (!newTitle.trim() || creating) return;

    setCreating(true);
    try {
      const catName = selectedCategoryId
        ? CATEGORIES.find((c) => c.id === selectedCategoryId)?.name ?? null
        : null;

      await dataProvider.createBuildPaintProject({
        title: newTitle.trim(),
        category: catName,
        categoryId: selectedCategoryId,
        itemId: selectedItem?.id ?? null,
      });
      resetCreateModal();
      await loadProjects();
      showToast({ message: 'Project created!', type: 'success' });
    } catch (err: unknown) {
      logger.warn("[BuildPaintProjects] create error:", err);
      showToast({ message: 'Failed to create project', type: 'error' });
    } finally {
      setCreating(false);
    }
  };

  const resetCreateModal = () => {
    setNewTitle("");
    setSelectedCategoryId(null);
    setSelectedItem(null);
    setShowCreateModal(false);
    setShowAllCategories(false);
    setShowStepPreview(false);
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
          <SkeletonList count={4} type="card" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#81D8D0" />}>
        <Animated.View style={animatedStyle}>
          {/* Add button */}
          <View style={styles.actionRow}>
            <AnimatedPressable
              onPress={() => setShowCreateModal(true)}
              style={[styles.addBtn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Create new project"
            >
              <Ionicons name="add" size={20} color="#fff" />
              <Text style={styles.addBtnText}>New Project</Text>
            </AnimatedPressable>
          </View>

          {/* Error state */}
          {error && (
            <View style={[styles.errorBanner, { backgroundColor: "#EF444420", borderColor: "#EF4444" }]}>
              <Ionicons name="warning-outline" size={18} color="#EF4444" />
              <Text style={[styles.errorText, { color: "#EF4444" }]}>{error}</Text>
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
              <View style={styles.emptyCtaContainer}>
                <AnimatedPressable
                  onPress={() => setShowCreateModal(true)}
                  style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel="Create your first project"
                >
                  <Text style={styles.emptyCtaBtnText}>Create Your First Project</Text>
                </AnimatedPressable>
              </View>
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
        onRequestClose={resetCreateModal}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          style={styles.modalOverlay}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <ScrollView showsVerticalScrollIndicator={false}>
              <View style={styles.modalHeader}>
                <Text style={[styles.modalTitle, { color: colors.text }]}>New Project</Text>
                <AnimatedPressable onPress={resetCreateModal} accessibilityRole="button" accessibilityLabel="Close">
                  <Ionicons name="close" size={24} color={colors.muted} />
                </AnimatedPressable>
              </View>

              {/* Category Picker */}
              <Text style={[styles.inputLabel, { color: colors.text }]}>Category</Text>
              <AnimatedPressable
                onPress={() => setShowCategoryPicker(true)}
                style={[styles.pickerBtn, { borderColor: colors.border, backgroundColor: colors.background }]}
                accessibilityRole="button"
                accessibilityLabel="Select category"
              >
                {selectedCategoryId ? (
                  <View style={styles.pickerSelected}>
                    <View style={[styles.catDot, { backgroundColor: colors.accent }]} />
                    <Text style={[styles.pickerText, { color: colors.text }]}>
                      {CATEGORIES.find((c) => c.id === selectedCategoryId)?.name ?? selectedCategoryId}
                    </Text>
                  </View>
                ) : (
                  <Text style={[styles.pickerPlaceholder, { color: colors.muted }]}>
                    Select a category...
                  </Text>
                )}
                <Ionicons name="chevron-down" size={18} color={colors.muted} />
              </AnimatedPressable>

              {/* Item Picker (only when category is selected) */}
              {selectedCategoryId && (
                <>
                  <Text style={[styles.inputLabel, { color: colors.text, marginTop: 16 }]}>
                    Link to Item (optional)
                  </Text>
                  {loadingItems ? (
                    <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 8 }} />
                  ) : selectedItem ? (
                    <View style={[styles.linkedItemRow, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      {selectedItem.imageUrl && (
                        <Image source={{ uri: selectedItem.imageUrl }} style={styles.linkedItemImg} />
                      )}
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.linkedItemName, { color: colors.text }]} numberOfLines={1}>
                          {selectedItem.name}
                        </Text>
                        {selectedItem.price > 0 && (
                          <Text style={[styles.linkedItemPrice, { color: colors.muted }]}>
                            ~{formatPrice(selectedItem.price, settings.currency)}
                          </Text>
                        )}
                      </View>
                      <AnimatedPressable onPress={() => setSelectedItem(null)} accessibilityRole="button" accessibilityLabel="Remove linked item">
                        <Ionicons name="close-circle" size={20} color={colors.muted} />
                      </AnimatedPressable>
                    </View>
                  ) : categoryItems.length > 0 ? (
                    <AnimatedPressable
                      onPress={() => setShowItemPicker(true)}
                      style={[styles.pickerBtn, { borderColor: colors.border, backgroundColor: colors.background }]}
                      accessibilityRole="button"
                      accessibilityLabel="Link to portfolio item"
                    >
                      <Text style={[styles.pickerPlaceholder, { color: colors.muted }]}>
                        Link to a portfolio item ({categoryItems.length} items)
                      </Text>
                      <Ionicons name="chevron-down" size={18} color={colors.muted} />
                    </AnimatedPressable>
                  ) : (
                    <Text style={[styles.noItemsText, { color: colors.muted }]}>
                      No portfolio items in this category
                    </Text>
                  )}
                </>
              )}

              {/* Title */}
              <Text style={[styles.inputLabel, { color: colors.text, marginTop: 16 }]}>Title *</Text>
              <TextInput
                value={newTitle}
                onChangeText={setNewTitle}
                placeholder="e.g., Warhammer Kill Team squad"
                placeholderTextColor={colors.muted}
                accessibilityLabel="Project title"
                style={[
                  styles.textInput,
                  { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
                ]}
              />

              {/* Step template preview */}
              {selectedTemplate && selectedTemplate.steps.length > 0 && (
                <View style={styles.templatePreview}>
                  <AnimatedPressable
                    onPress={() => setShowStepPreview(!showStepPreview)}
                    style={styles.templateHeader}
                    accessibilityRole="button"
                    accessibilityLabel={showStepPreview ? "Collapse step preview" : "Expand step preview"}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.templateTitle, { color: colors.text }]}>
                        {selectedTemplate.steps.length} steps for {selectedTemplate.displayName}
                      </Text>
                      <Text style={[styles.templateHint, { color: colors.muted }]}>
                        Template steps will be added after creation
                      </Text>
                    </View>
                    <Ionicons
                      name={showStepPreview ? "chevron-up" : "chevron-down"}
                      size={18}
                      color={colors.muted}
                    />
                  </AnimatedPressable>
                  {showStepPreview && (
                    <View style={[styles.templateSteps, { borderTopColor: colors.border }]}>
                      {selectedTemplate.steps.map((s) => (
                        <View key={s.id} style={styles.templateStepRow}>
                          <Text style={[styles.templateStepNum, { color: colors.muted }]}>{s.order}.</Text>
                          <Text style={[styles.templateStepLabel, { color: colors.text }]}>{s.label}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              )}

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
                accessibilityRole="button"
                accessibilityLabel={creating ? 'Creating project' : 'Create project'}
              >
                {creating ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.createBtnText}>Create Project</Text>
                )}
              </AnimatedPressable>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Category Picker Modal */}
      <Modal
        visible={showCategoryPicker}
        animationType="slide"
        transparent
        onRequestClose={() => setShowCategoryPicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.pickerModalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Select Category</Text>
              <AnimatedPressable onPress={() => setShowCategoryPicker(false)} accessibilityRole="button" accessibilityLabel="Close">
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>
            <FlatList
              data={sortedCategories}
              keyExtractor={(item) => item.id}
              renderItem={({ item: cat }) => {
                const vis = CATEGORY_VISUAL[cat.id];
                const isBuildable = (BUILDABLE_CATEGORIES as readonly string[]).includes(cat.id);
                return (
                  <AnimatedPressable
                    onPress={() => handleSelectCategory(cat.id)}
                    style={[styles.catPickerRow, { borderBottomColor: colors.border }]}
                    accessibilityRole="button"
                    accessibilityLabel={cat.name}
                  >
                    <View style={[styles.catDot, { backgroundColor: colors.accent }]} />
                    <Ionicons name={(vis?.iconName || 'cube-outline') as any} size={20} color={colors.accent} />
                    <View style={{ flex: 1, marginLeft: 10 }}>
                      <Text style={[styles.catPickerName, { color: colors.text }]}>{cat.name}</Text>
                    </View>
                    {isBuildable && (
                      <View style={[styles.buildBadge, { backgroundColor: colors.accent + '20' }]}>
                        <Text style={[styles.buildBadgeText, { color: colors.accent }]}>Build</Text>
                      </View>
                    )}
                  </AnimatedPressable>
                );
              }}
              ListFooterComponent={
                !showAllCategories ? (
                  <AnimatedPressable
                    onPress={() => setShowAllCategories(true)}
                    style={styles.showAllBtn}
                    accessibilityRole="button"
                    accessibilityLabel="Show all categories"
                  >
                    <Text style={[styles.showAllText, { color: colors.accent }]}>
                      Show All Categories ({CATEGORIES.length - BUILDABLE_CATEGORIES.length} more)
                    </Text>
                  </AnimatedPressable>
                ) : null
              }
            />
          </View>
        </View>
      </Modal>

      {/* Item Picker Modal */}
      <Modal
        visible={showItemPicker}
        animationType="slide"
        transparent
        onRequestClose={() => setShowItemPicker(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.pickerModalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Link Item</Text>
              <AnimatedPressable onPress={() => setShowItemPicker(false)} accessibilityRole="button" accessibilityLabel="Close">
                <Ionicons name="close" size={24} color={colors.muted} />
              </AnimatedPressable>
            </View>
            <FlatList
              data={categoryItems}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <AnimatedPressable
                  onPress={() => handleSelectItem(item)}
                  style={[styles.itemPickerRow, { borderBottomColor: colors.border }]}
                  accessibilityRole="button"
                  accessibilityLabel={item.name}
                >
                  {item.imageUrl ? (
                    <Image source={{ uri: item.imageUrl }} style={styles.itemPickerImg} />
                  ) : (
                    <View style={[styles.itemPickerImgPlaceholder, { backgroundColor: colors.border }]}>
                      <Ionicons name="cube-outline" size={20} color={colors.muted} />
                    </View>
                  )}
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.itemPickerName, { color: colors.text }]} numberOfLines={1}>
                      {item.name}
                    </Text>
                    {item.price > 0 && (
                      <Text style={[styles.itemPickerPrice, { color: colors.muted }]}>
                        ~{formatPrice(item.price, settings.currency)}
                      </Text>
                    )}
                  </View>
                </AnimatedPressable>
              )}
              ListHeaderComponent={
                <AnimatedPressable
                  onPress={() => setShowItemPicker(false)}
                  style={[styles.itemPickerRow, { borderBottomColor: colors.border }]}
                  accessibilityRole="button"
                  accessibilityLabel="Skip"
                >
                  <Ionicons name="remove-circle-outline" size={20} color={colors.muted} style={{ marginRight: 12 }} />
                  <Text style={[styles.itemPickerName, { color: colors.muted }]}>Skip — no linked item</Text>
                </AnimatedPressable>
              }
            />
          </View>
        </View>
      </Modal>
      <QuickNavBar />
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
  colors: ReturnType<typeof useAppTheme>['colors'];
  onPress: () => void;
}) {
  const statusColors = statusColor(project.status, project.isCompleted, colors);
  const accentColor = colors.accent;

  return (
    <AnimatedPressable
      onPress={onPress}
      style={[styles.projectCard, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="button"
      accessibilityLabel={`${project.title}, ${project.percent}% complete, ${project.isCompleted ? 'completed' : project.status || 'backlog'}`}
    >
      {/* Category accent strip */}
      <View style={[styles.accentStrip, { backgroundColor: accentColor }]} />

      <View style={[styles.projectCardInner, { paddingLeft: 12 }]}>
        <View style={styles.projectCardHeader}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.projectTitle, { color: colors.text }]} numberOfLines={1}>
              {project.title}
            </Text>
            <View style={styles.projectMeta}>
              {project.categoryId && (
                <View style={styles.catPillRow}>
                  <View style={[styles.catDotSm, { backgroundColor: accentColor || colors.accent }]} />
                  <Text style={[styles.projectCategory, { color: colors.muted }]} numberOfLines={1}>
                    {CATEGORIES.find((c) => c.id === project.categoryId)?.name ?? project.category}
                  </Text>
                </View>
              )}
              {!project.categoryId && project.category && (
                <Text style={[styles.projectCategory, { color: colors.muted }]} numberOfLines={1}>
                  {project.category}
                </Text>
              )}
              {project.itemName && (
                <View style={styles.linkedBadge}>
                  <Ionicons name="link-outline" size={12} color={colors.muted} />
                  <Text style={[styles.linkedBadgeText, { color: colors.muted }]} numberOfLines={1}>
                    {project.itemName}
                  </Text>
                </View>
              )}
            </View>
          </View>
          {project.itemImageUrl && (
            <Image source={{ uri: project.itemImageUrl }} style={styles.projectThumb} />
          )}
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
                  backgroundColor: project.isCompleted ? "#10B981" : accentColor || colors.accent,
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
  emptyCtaContainer: {
    alignItems: "center",
    marginTop: 16,
  },
  emptyCtaBtn: {
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 12,
  },
  emptyCtaBtnText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#FFFFFF",
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
    flexDirection: "row",
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    overflow: "hidden",
  },
  accentStrip: {
    width: 4,
  },
  projectCardInner: {
    flex: 1,
    padding: 16,
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
  projectMeta: {
    marginTop: 4,
    gap: 4,
  },
  catPillRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  catDotSm: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  projectCategory: {
    fontSize: 12,
  },
  linkedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  linkedBadgeText: {
    fontSize: 11,
  },
  projectThumb: {
    width: 36,
    height: 36,
    borderRadius: 6,
    marginLeft: 8,
  },
  statusPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    marginLeft: 8,
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
    maxHeight: "85%",
  },
  pickerModalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
    maxHeight: "70%",
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
  pickerBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  pickerSelected: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  pickerText: {
    fontSize: 15,
  },
  pickerPlaceholder: {
    fontSize: 15,
  },
  catDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  catPickerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    gap: 8,
  },
  catPickerName: {
    fontSize: 15,
    fontWeight: "500",
  },
  buildBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  buildBadgeText: {
    fontSize: 11,
    fontWeight: "600",
  },
  showAllBtn: {
    paddingVertical: 16,
    alignItems: "center",
  },
  showAllText: {
    fontSize: 14,
    fontWeight: "600",
  },
  linkedItemRow: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 12,
    padding: 10,
    gap: 10,
  },
  linkedItemImg: {
    width: 40,
    height: 40,
    borderRadius: 8,
  },
  linkedItemName: {
    fontSize: 14,
    fontWeight: "500",
  },
  linkedItemPrice: {
    fontSize: 12,
    marginTop: 2,
  },
  noItemsText: {
    fontSize: 13,
    fontStyle: "italic",
    marginVertical: 4,
  },
  itemPickerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    gap: 12,
  },
  itemPickerImg: {
    width: 40,
    height: 40,
    borderRadius: 8,
  },
  itemPickerImgPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  itemPickerName: {
    fontSize: 15,
    fontWeight: "500",
  },
  itemPickerPrice: {
    fontSize: 12,
    marginTop: 2,
  },
  templatePreview: {
    marginTop: 16,
  },
  templateHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
  },
  templateTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  templateHint: {
    fontSize: 12,
    marginTop: 2,
  },
  templateSteps: {
    borderTopWidth: 1,
    paddingTop: 8,
    marginTop: 4,
  },
  templateStepRow: {
    flexDirection: "row",
    paddingVertical: 4,
    gap: 8,
  },
  templateStepNum: {
    fontSize: 12,
    width: 20,
    textAlign: "right",
  },
  templateStepLabel: {
    fontSize: 13,
    flex: 1,
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
