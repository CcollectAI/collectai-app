/**
 * Individual project card for the Build & Paint Projects list.
 *
 * Shows project title, category, linked item, progress bar, status pill, and footer.
 * Extracted from app/build-paint-projects.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { CATEGORIES } from '@/data/categories';
import { timeAgo } from '@/lib/timeAgo';
import { MS_PER_DAY } from '@/constants/time';
import type { BuildPaintProject } from '@/data';

const MS_PER_MONTH = 30 * MS_PER_DAY;

function formatRelativeDate(dateStr: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const diff = Date.now() - date.getTime();
  const diffDays = Math.floor(diff / MS_PER_DAY);

  if (diffDays === 0) return 'today';
  if (diffDays === 1) return 'yesterday';
  if (diff < MS_PER_MONTH) return timeAgo(date);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function statusColor(
  status: string | null | undefined,
  isCompleted: boolean,
  categoryId: string | null | undefined,
  themeColors: { accent: string; muted: string; border: string; success: string; warning: string },
) {
  if (isCompleted) return { bg: themeColors.success + '20', text: themeColors.success };

  const { getStatusDef } = require('@/constants/buildStepTemplates');
  const def = getStatusDef(categoryId, status || '');
  if (def) {
    const colorMap: Record<string, { bg: string; text: string }> = {
      muted: { bg: themeColors.muted + '15', text: themeColors.muted },
      info: { bg: '#3B82F620', text: '#3B82F6' },
      warning: { bg: themeColors.warning + '20', text: themeColors.warning },
      accent: { bg: themeColors.accent + '20', text: themeColors.accent },
      success: { bg: themeColors.success + '20', text: themeColors.success },
    };
    return colorMap[def.colorHint] ?? colorMap.muted;
  }

  // Fallback for legacy statuses
  const s = (status || '').toLowerCase();
  if (s === 'active') return { bg: themeColors.accent + '20', text: themeColors.accent };
  return { bg: themeColors.muted + '15', text: themeColors.muted };
}

interface ProjectCardProps {
  project: BuildPaintProject;
  onPress: () => void;
}

export const ProjectCard = React.memo(function ProjectCard({
  project,
  onPress,
}: ProjectCardProps) {
  const { colors } = useAppTheme();
  const statusColors = statusColor(project.status, project.isCompleted, project.categoryId, colors);
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
              {(() => {
                if (project.isCompleted) return 'Finished';
                const { getStatusDef } = require('@/constants/buildStepTemplates');
                const def = getStatusDef(project.categoryId, project.status || '');
                return def?.label ?? project.status ?? 'Wishlist';
              })()}
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
                  backgroundColor: project.isCompleted ? colors.success : accentColor || colors.accent,
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
});

const styles = StyleSheet.create({
  projectCard: {
    flexDirection: 'row',
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    overflow: 'hidden',
  },
  accentStrip: {
    width: 4,
  },
  projectCardInner: {
    flex: 1,
    padding: 16,
  },
  projectCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  projectTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  projectMeta: {
    marginTop: 4,
    gap: 4,
  },
  catPillRow: {
    flexDirection: 'row',
    alignItems: 'center',
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
    flexDirection: 'row',
    alignItems: 'center',
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
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  progressTrack: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 3,
  },
  progressText: {
    fontSize: 12,
    fontWeight: '600',
    minWidth: 36,
    textAlign: 'right',
  },
  projectNotes: {
    fontSize: 13,
    marginBottom: 8,
  },
  projectFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  projectDate: {
    fontSize: 11,
  },
});
