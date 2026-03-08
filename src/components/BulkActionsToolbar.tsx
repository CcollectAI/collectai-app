/**
 * Bulk-actions toolbar shown when items are selected in multi-select mode.
 *
 * Renders a header row with close / select-all and a contextual bar with
 * Move, Export, Archive, and Delete buttons.
 *
 * Extracted from app/(tabs)/items.tsx to reduce file size.
 */
import React from "react";
import { View, Text, ActivityIndicator, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";

// ── Semantic action colors (theme-independent) ──────────────────────────

const ACTION_COLORS = {
  archive: "#f97316",
  archiveBg: "#f9731610",
  danger: "#ef4444",
  dangerBg: "#ef444410",
} as const;

// ── Props interface ─────────────────────────────────────────────────────

interface BulkActionsToolbarProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    card: string;
  };
  selectedCount: number;
  totalCount: number;
  isAllSelected: boolean;
  loading: boolean;
  disabled: boolean;
  onExit: () => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
  onChangeCategory: () => void;
  onExport: () => void;
  onArchive: () => void;
  onDelete: () => void;
}

// ── Component ───────────────────────────────────────────────────────────

export const BulkActionsToolbar = React.memo(function BulkActionsToolbar({
  theme,
  selectedCount,
  totalCount,
  isAllSelected,
  loading,
  disabled,
  onExit,
  onSelectAll,
  onDeselectAll,
  onChangeCategory,
  onExport,
  onArchive,
  onDelete,
}: BulkActionsToolbarProps) {
  return (
    <>
      {/* Header row */}
      <View style={s.header}>
        <AnimatedPressable
          style={s.closeBtn}
          onPress={onExit}
          accessibilityRole="button"
          accessibilityLabel="Exit multi-select mode"
        >
          <Ionicons name="close" size={24} color={theme.text} />
        </AnimatedPressable>
        <Text style={[s.title, { color: theme.text }]}>
          {selectedCount} selected
        </Text>
        <View style={s.actions}>
          <AnimatedPressable
            style={s.actionBtn}
            onPress={isAllSelected ? onDeselectAll : onSelectAll}
            accessibilityRole="button"
            accessibilityLabel={isAllSelected ? "Deselect all items" : "Select all items"}
          >
            <Text style={[s.actionText, { color: theme.accent }]}>
              {isAllSelected ? "Deselect All" : "Select All"}
            </Text>
          </AnimatedPressable>
        </View>
      </View>

      {/* Bulk actions bar */}
      {selectedCount > 0 && (
        <View style={[s.bar, { backgroundColor: theme.card, borderColor: theme.border }]}>
          {loading ? (
            <ActivityIndicator size="small" color={theme.accent} />
          ) : (
            <View style={s.row}>
              <AnimatedPressable
                style={[s.btn, { backgroundColor: theme.accent + "10" }]}
                onPress={onChangeCategory}
                disabled={disabled}
                accessibilityRole="button"
                accessibilityLabel="Move selected items to category"
              >
                <Ionicons name="folder-outline" size={18} color={theme.accent} />
                <Text style={[s.btnText, { color: theme.accent }]}>Move</Text>
              </AnimatedPressable>

              <AnimatedPressable
                style={[s.btn, { backgroundColor: theme.accent + "10" }]}
                onPress={onExport}
                disabled={disabled}
                accessibilityRole="button"
                accessibilityLabel="Export selected items"
              >
                <Ionicons name="download-outline" size={18} color={theme.accent} />
                <Text style={[s.btnText, { color: theme.accent }]}>Export</Text>
              </AnimatedPressable>

              <AnimatedPressable
                style={[s.btn, { backgroundColor: ACTION_COLORS.archiveBg }]}
                onPress={onArchive}
                disabled={disabled}
                accessibilityRole="button"
                accessibilityLabel="Archive selected items"
              >
                <Ionicons name="archive-outline" size={18} color={ACTION_COLORS.archive} />
                <Text style={[s.btnText, { color: ACTION_COLORS.archive }]}>Archive</Text>
              </AnimatedPressable>

              <AnimatedPressable
                style={[s.btn, { backgroundColor: ACTION_COLORS.dangerBg }]}
                onPress={onDelete}
                disabled={disabled}
                accessibilityRole="button"
                accessibilityLabel="Delete selected items"
              >
                <Ionicons name="trash-outline" size={18} color={ACTION_COLORS.danger} />
                <Text style={[s.btnText, { color: ACTION_COLORS.danger }]}>Delete</Text>
              </AnimatedPressable>
            </View>
          )}
        </View>
      )}
    </>
  );
});

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    marginBottom: 8,
  },
  closeBtn: {
    padding: 4,
    marginRight: 12,
  },
  title: {
    flex: 1,
    fontSize: 18,
    fontWeight: "700",
  },
  actions: {
    flexDirection: "row",
    gap: 8,
  },
  actionBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  actionText: {
    fontSize: 14,
    fontWeight: "600",
  },
  bar: {
    marginBottom: 12,
    padding: 8,
    borderRadius: 12,
    borderWidth: 1,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
  },
  btn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 8,
    gap: 4,
  },
  btnText: {
    fontSize: 12,
    fontWeight: "600",
  },
});
