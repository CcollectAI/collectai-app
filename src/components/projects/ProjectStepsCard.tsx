/**
 * ProjectStepsCard — Steps list with checkboxes, template apply button, and add-step input.
 */

import React from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import type { BuildPaintStep } from "@/data";
import type { BuildStepTemplate } from "@/constants/buildStepTemplates";

export interface ProjectStepsCardProps {
  steps: BuildPaintStep[];
  accentColor: string;
  newStepTitle: string;
  addingStep: boolean;
  applyingTemplate: boolean;
  canApplyTemplate: boolean;
  templateForCategory: BuildStepTemplate | null;
  onChangeStepTitle: (text: string) => void;
  onAddStep: () => void;
  onToggleStep: (stepId: string, currentIsDone: boolean) => void;
  onApplyTemplate: () => void;
}

export const ProjectStepsCard = React.memo(function ProjectStepsCard({
  steps,
  accentColor,
  newStepTitle,
  addingStep,
  applyingTemplate,
  canApplyTemplate,
  templateForCategory,
  onChangeStepTitle,
  onAddStep,
  onToggleStep,
  onApplyTemplate,
}: ProjectStepsCardProps) {
  const { colors } = useAppTheme();

  const doneSteps = steps.filter((s) => s.isDone).length;
  const totalSteps = steps.length;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardHeader}>
        <Text style={[styles.cardTitle, { color: colors.text }]}>Steps</Text>
        <Text style={[styles.cardSubtitle, { color: colors.muted }]}>
          {doneSteps}/{totalSteps} completed
        </Text>
      </View>

      {/* Apply Template button */}
      {canApplyTemplate && templateForCategory && (
        <AnimatedPressable
          onPress={onApplyTemplate}
          disabled={applyingTemplate}
          style={[
            styles.applyTemplateBtn,
            { backgroundColor: accentColor + "15", borderColor: accentColor },
          ]}
          accessibilityRole="button"
          accessibilityLabel={`Apply ${templateForCategory.displayName} workflow with ${templateForCategory.steps.length} steps`}
        >
          {applyingTemplate ? (
            <ActivityIndicator size="small" color={accentColor} />
          ) : (
            <>
              <Ionicons name="flash-outline" size={18} color={accentColor} />
              <View style={{ flex: 1, marginLeft: 8 }}>
                <Text style={[styles.applyTemplateTitle, { color: accentColor }]}>
                  Use {templateForCategory.displayName} workflow?
                </Text>
                <Text style={[styles.applyTemplateHint, { color: colors.muted }]}>
                  {templateForCategory.steps.length} steps will be added
                </Text>
              </View>
              <Ionicons name="arrow-forward" size={16} color={accentColor} />
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
              onPress={() => onToggleStep(step.id, step.isDone)}
              accessibilityRole="button"
              accessibilityLabel={`${step.title}, ${step.isDone ? "completed" : "not completed"}`}
            >
              <View
                style={[
                  styles.stepCheckbox,
                  {
                    backgroundColor: step.isDone ? accentColor : "transparent",
                    borderColor: step.isDone ? accentColor : colors.border,
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
          onChangeText={onChangeStepTitle}
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
              backgroundColor: newStepTitle.trim() ? accentColor : colors.border,
              opacity: addingStep ? 0.7 : 1,
            },
          ]}
          onPress={onAddStep}
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
  );
});

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
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
});
