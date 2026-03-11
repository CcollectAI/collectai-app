/**
 * ProjectHeaderCard — Title, category badge, complete toggle, progress bar, project notes.
 */

import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Switch,
} from "react-native";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import type { BuildPaintProject } from "@/data";

export interface ProjectHeaderCardProps {
  project: BuildPaintProject;
  categoryName: string | undefined | null;
  accentColor: string;
  pendingPercent: number;
  savingProgress: boolean;
  togglingComplete: boolean;
  onDecrease: () => void;
  onIncrease5: () => void;
  onIncrease10: () => void;
  onSaveProgress: () => void;
  onToggleComplete: () => void;
}

export const ProjectHeaderCard = React.memo(function ProjectHeaderCard({
  project,
  categoryName,
  accentColor,
  pendingPercent,
  savingProgress,
  togglingComplete,
  onDecrease,
  onIncrease5,
  onIncrease10,
  onSaveProgress,
  onToggleComplete,
}: ProjectHeaderCardProps) {
  const { colors } = useAppTheme();
  const progressBarColor = project.isCompleted ? "#34D399" : accentColor;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.projectTitle, { color: colors.text }]}>{project.title}</Text>
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
              onValueChange={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                onToggleComplete();
              }}
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
            onPress={onDecrease}
            accessibilityRole="button"
            accessibilityLabel="Decrease progress by 5 percent"
          >
            <Text style={[styles.percentBtnText, { color: colors.text }]}>-5</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.percentBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
            onPress={onIncrease5}
            accessibilityRole="button"
            accessibilityLabel="Increase progress by 5 percent"
          >
            <Text style={[styles.percentBtnText, { color: colors.text }]}>+5</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.percentBtn, { backgroundColor: colors.background, borderColor: colors.border }]}
            onPress={onIncrease10}
            accessibilityRole="button"
            accessibilityLabel="Increase progress by 10 percent"
          >
            <Text style={[styles.percentBtnText, { color: colors.text }]}>+10</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[
              styles.saveBtn,
              {
                backgroundColor: pendingPercent !== project.percent ? accentColor : colors.border,
                opacity: savingProgress ? 0.7 : 1,
              },
            ]}
            onPress={onSaveProgress}
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

      {/* Project Notes */}
      {project.notes && (
        <View style={[styles.notesSection, { borderTopColor: colors.border }]}>
          <Text style={[styles.sectionLabel, { color: colors.muted }]}>Project Notes</Text>
          <Text style={[styles.notesText, { color: colors.text }]}>{project.notes}</Text>
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
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
});
