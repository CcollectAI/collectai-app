import React from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { BuildPaintProject } from '@/data';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  isBuildable: boolean;
  buildProjects: BuildPaintProject[];
  buildProjectsLoading: boolean;
  accentColor: string;
  onProjectPress: (projectId: string) => void;
  onSeeAll: () => void;
  onStartNew: () => void;
  colors: AppTheme['colors'];
};

const BuildProjectsSection: React.FC<Props> = ({
  isBuildable,
  buildProjects,
  buildProjectsLoading,
  accentColor,
  onProjectPress,
  onSeeAll,
  onStartNew,
  colors,
}) => {
  if (!isBuildable) return null;

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Build & Paint Projects</Text>
        {buildProjects.length > 0 && (
          <Text style={[styles.sectionCount, { color: colors.muted }]}>
            {buildProjects.length} project{buildProjects.length !== 1 ? 's' : ''}
          </Text>
        )}
      </View>
      {buildProjectsLoading ? (
        <ActivityIndicator size="small" color={accentColor} style={{ marginVertical: 12 }} />
      ) : buildProjects.length > 0 ? (
        <>
          {buildProjects.slice(0, 3).map((project) => {
            const pct = project.percent ?? 0;

            return (
              <AnimatedPressable
                key={project.id}
                style={[styles.buildProjectCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                onPress={() => onProjectPress(project.id)}
                accessibilityRole="button"
                accessibilityLabel={`${project.title}, ${pct}% complete`}
              >
                <View style={[styles.buildProjectAccent, { backgroundColor: accentColor }]} />
                <View style={styles.buildProjectInfo}>
                  <Text style={[styles.buildProjectTitle, { color: colors.text }]} numberOfLines={1}>
                    {project.title}
                  </Text>
                  <View style={styles.buildProjectProgressRow}>
                    <View style={[styles.buildProjectProgressBg, { backgroundColor: colors.border }]}>
                      <View style={[styles.buildProjectProgressFill, { backgroundColor: accentColor, width: `${pct}%` }]} />
                    </View>
                    <Text style={[styles.buildProjectPct, { color: colors.muted }]}>{pct}%</Text>
                  </View>
                </View>
                <Ionicons name="chevron-forward" size={18} color={colors.muted} />
              </AnimatedPressable>
            );
          })}
          {buildProjects.length > 3 && (
            <AnimatedPressable
              style={styles.seeAllButton}
              onPress={onSeeAll}
              accessibilityRole="link"
              accessibilityLabel={`See all ${buildProjects.length} build projects`}
            >
              <Text style={[styles.seeAllText, { color: accentColor }]}>
                See all {buildProjects.length} projects
              </Text>
              <Ionicons name="arrow-forward" size={14} color={accentColor} />
            </AnimatedPressable>
          )}
        </>
      ) : (
        <Text style={[styles.emptyText, { color: colors.muted }]}>
          No build projects in this category yet.
        </Text>
      )}
      <AnimatedPressable
        style={[styles.startBuildBtn, { backgroundColor: accentColor }]}
        onPress={onStartNew}
        accessibilityRole="button"
        accessibilityLabel="Start a new build project"
      >
        <Ionicons name="construct-outline" size={16} color="#fff" />
        <Text style={styles.startBuildBtnText}>Start New Build</Text>
      </AnimatedPressable>
    </View>
  );
};

export default React.memo(BuildProjectsSection);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  sectionCount: {
    fontSize: 13,
    fontWeight: '500',
  },
  emptyText: {
    fontSize: 13,
  },
  buildProjectCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: 8,
  },
  buildProjectAccent: {
    width: 4,
    alignSelf: 'stretch',
  },
  buildProjectInfo: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  buildProjectTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 6,
  },
  buildProjectProgressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  buildProjectProgressBg: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  buildProjectProgressFill: {
    height: '100%',
    borderRadius: 2,
  },
  buildProjectPct: {
    fontSize: 11,
    fontWeight: '600',
    minWidth: 28,
    textAlign: 'right',
  },
  startBuildBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
    marginTop: 8,
  },
  startBuildBtnText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
  seeAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    gap: 4,
  },
  seeAllText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
