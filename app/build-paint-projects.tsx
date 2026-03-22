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
  StyleSheet,
  Animated,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { dataProvider, type BuildPaintProject } from "@/data";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { useSettings } from "@/lib/settings";
import { SkeletonList } from "@/components/Skeleton";
import { useToast } from "@/components/Toast";
import { fireHaptic, HapticIntent } from "@/haptics";
import logger from "@/utils/logger";
import { QuickNavBar } from "@/components/QuickNavBar";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { CreateProjectModal } from "@/components/projects/CreateProjectModal";
import { ProjectFilters, type ProjectFilterStatus } from "@/components/projects/ProjectFilters";


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
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState<ProjectFilterStatus>('all');

  // Pre-fill values for CreateProjectModal (from item detail navigation)
  const [initialTitle, setInitialTitle] = useState('');
  const [initialCategoryId, setInitialCategoryId] = useState<string | null>(null);
  const [initialItem, setInitialItem] = useState<{ id: string; name: string } | null>(null);

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
      setInitialTitle(params.linkItemName);
      setInitialItem({ id: params.linkItemId, name: params.linkItemName });
      if (params.linkCategoryId) {
        setInitialCategoryId(params.linkCategoryId);
      }
      setShowCreateModal(true);
    }
  }, [params.linkItemId, params.linkItemName, params.linkCategoryId]);

  const handleProjectPress = useCallback((project: BuildPaintProject) => {
    router.push(`/projects/${project.id}`);
  }, [router]);

  const handleProjectCreated = useCallback(async () => {
    await loadProjects();
    showToast({ message: 'Project created!', type: 'success' });
  }, [loadProjects, showToast]);

  // Separate projects by pipeline status
  const wishlistProjects = useMemo(() => projects.filter((p) => !p.isCompleted && p.status === 'wishlist'), [projects]);
  const finishedProjects = useMemo(() => projects.filter((p) => p.isCompleted), [projects]);
  const inProgressProjects = useMemo(() => projects.filter((p) => !p.isCompleted && p.status !== 'wishlist'), [projects]);

  const filteredProjects = useMemo(() => {
    if (filterStatus === 'in_progress') return inProgressProjects;
    if (filterStatus === 'finished') return finishedProjects;
    if (filterStatus === 'wishlist') return wishlistProjects;
    return projects;
  }, [filterStatus, inProgressProjects, finishedProjects, wishlistProjects, projects]);

  const filterCounts = useMemo(() => ({
    all: projects.length,
    in_progress: inProgressProjects.length,
    finished: finishedProjects.length,
    wishlist: wishlistProjects.length,
  }), [projects.length, inProgressProjects.length, finishedProjects.length, wishlistProjects.length]);

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
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}>
        <Animated.View style={animatedStyle}>
          {/* Add button */}
          <View style={styles.actionRow}>
            <AnimatedPressable
              onPress={() => setShowCreateModal(true)}
              style={[styles.addBtn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Create new project"
            >
              <Ionicons name="add" size={20} color={colors.accentText} />
              <Text style={[styles.addBtnText, { color: colors.accentText }]}>New Project</Text>
            </AnimatedPressable>
          </View>

          {/* Error state */}
          {error && (
            <View style={[styles.errorBanner, { backgroundColor: colors.error + '20', borderColor: colors.error }]}>
              <Ionicons name="warning-outline" size={18} color={colors.error} />
              <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>
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
                  <Text style={[styles.emptyCtaBtnText, { color: colors.accentText }]}>Create Your First Project</Text>
                </AnimatedPressable>
              </View>
            </View>
          )}

          {/* Filter tabs */}
          {projects.length > 0 && (
            <ProjectFilters
              selected={filterStatus}
              onSelect={setFilterStatus}
              counts={filterCounts}
              hapticsEnabled={settings.hapticsEnabled}
            />
          )}

          {/* Projects list */}
          {filterStatus === 'all' ? (
            <>
              {inProgressProjects.length > 0 && (
                <View style={styles.section}>
                  <Text style={[styles.sectionTitle, { color: colors.muted }]}>
                    In Progress ({inProgressProjects.length})
                  </Text>
                  {inProgressProjects.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      onPress={() => handleProjectPress(project)}
                    />
                  ))}
                </View>
              )}
              {wishlistProjects.length > 0 && (
                <View style={styles.section}>
                  <Text style={[styles.sectionTitle, { color: colors.muted }]}>
                    Wishlist ({wishlistProjects.length})
                  </Text>
                  {wishlistProjects.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      onPress={() => handleProjectPress(project)}
                    />
                  ))}
                </View>
              )}
              {finishedProjects.length > 0 && (
                <View style={styles.section}>
                  <Text style={[styles.sectionTitle, { color: colors.muted }]}>
                    Finished ({finishedProjects.length})
                  </Text>
                  {finishedProjects.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      onPress={() => handleProjectPress(project)}
                    />
                  ))}
                </View>
              )}
            </>
          ) : (
            <View style={styles.section}>
              {filteredProjects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  onPress={() => handleProjectPress(project)}
                />
              ))}
              {filteredProjects.length === 0 && (
                <Text style={[styles.emptySubtitle, { color: colors.muted, textAlign: 'center', marginTop: 24 }]}>
                  No {filterStatus} projects
                </Text>
              )}
            </View>
          )}

          <View style={{ height: 24 }} />
        </Animated.View>
      </ScrollView>

      <CreateProjectModal
        visible={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleProjectCreated}
        initialTitle={initialTitle}
        initialCategoryId={initialCategoryId}
        initialItem={initialItem}
      />
      <QuickNavBar />
    </SafeAreaView>
  );
}

// ProjectCard, CreateProjectModal, and ProjectFilters extracted to src/components/projects/

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
  // (ProjectCard styles moved to src/components/projects/ProjectCard.tsx)
  // (Modal/picker/template styles moved to src/components/projects/CreateProjectModal.tsx)
});
