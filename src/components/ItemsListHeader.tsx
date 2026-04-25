/**
 * List header for the Items screen: search bar, filter button,
 * view-mode toggle, and "Select" entry point.
 *
 * Extracted from app/(tabs)/items.tsx to reduce file size.
 */
import React from "react";
import { useTranslation } from "react-i18next";
import { View, Text, TextInput, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";

// ── Props interface ─────────────────────────────────────────────────────

interface ItemsListHeaderProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
    card: string;
  };
  query: string;
  onQueryChange: (text: string) => void;
  viewMode: "list" | "gallery";
  onToggleViewList: () => void;
  onToggleViewGallery: () => void;
  hasActiveFilter: boolean;
  onOpenFilter: () => void;
  onEnterMultiSelect: () => void;
  isMultiSelectMode: boolean;
}

// ── Component ───────────────────────────────────────────────────────────

export const ItemsListHeader = React.memo(function ItemsListHeader({
  theme,
  query,
  onQueryChange,
  viewMode,
  onToggleViewList,
  onToggleViewGallery,
  hasActiveFilter,
  onOpenFilter,
  onEnterMultiSelect,
  isMultiSelectMode,
}: ItemsListHeaderProps) {
  const { t } = useTranslation();
  return (
    <>
      {/* Search row */}
      <View style={s.searchRow}>
        <View style={[s.searchInputWrapper, { backgroundColor: theme.card }]}>
          <Ionicons name="search" size={16} color={theme.muted} style={s.searchIcon} />
          <TextInput
            value={query}
            onChangeText={onQueryChange}
            placeholder={t('items_list_header.search_placeholder')}
            placeholderTextColor={theme.muted}
            accessibilityLabel={t('items_list_header.search_a11y')}
            style={[s.searchInput, { backgroundColor: theme.card, color: theme.text }]}
          />
        </View>

        {/* Filter button */}
        <AnimatedPressable
          style={[s.filterBtn, { backgroundColor: theme.card, borderColor: theme.border }]}
          onPress={onOpenFilter}
          accessibilityRole="button"
          accessibilityLabel={t('items_list_header.open_filters_a11y')}
        >
          <Ionicons name="options-outline" size={18} color={theme.accent} />
          {hasActiveFilter && (
            <View style={[s.filterDot, { backgroundColor: theme.accent }]} />
          )}
        </AnimatedPressable>
      </View>

      {/* Controls row: view toggle + select */}
      <View style={s.controlsRow}>
        {/* View mode toggle */}
        <View style={s.viewToggleRow}>
          <AnimatedPressable
            style={[
              s.viewToggleBtn,
              viewMode === "list" && { backgroundColor: theme.accent + "20" },
              { borderColor: theme.border },
            ]}
            onPress={onToggleViewList}
            accessibilityRole="button"
            accessibilityLabel={t('items_list_header.list_view_a11y')}
            accessibilityState={{ selected: viewMode === "list" }}
          >
            <Ionicons
              name="list"
              size={18}
              color={viewMode === "list" ? theme.accent : theme.muted}
            />
          </AnimatedPressable>
          <AnimatedPressable
            style={[
              s.viewToggleBtn,
              viewMode === "gallery" && { backgroundColor: theme.accent + "20" },
              { borderColor: theme.border },
            ]}
            onPress={onToggleViewGallery}
            accessibilityRole="button"
            accessibilityLabel={t('items_list_header.gallery_view_a11y')}
            accessibilityState={{ selected: viewMode === "gallery" }}
          >
            <Ionicons
              name="grid"
              size={18}
              color={viewMode === "gallery" ? theme.accent : theme.muted}
            />
          </AnimatedPressable>
        </View>

        {/* Spacer */}
        <View style={{ flex: 1 }} />

        {/* Select text button */}
        {!isMultiSelectMode && (
          <AnimatedPressable
            style={s.selectBtn}
            onPress={onEnterMultiSelect}
            accessibilityRole="button"
            accessibilityLabel={t('items_list_header.select_mode_a11y')}
          >
            <Text style={[s.selectText, { color: theme.accent }]}>Select</Text>
          </AnimatedPressable>
        )}
      </View>
    </>
  );
});

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 12,
  },
  searchInputWrapper: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 12,
    paddingLeft: 14,
    height: 44,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchInput: {
    flex: 1,
    borderRadius: 12,
    paddingHorizontal: 0,
    paddingVertical: 10,
    fontSize: 14,
  },
  filterBtn: {
    width: 44,
    height: 44,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  filterDot: {
    position: "absolute",
    top: 6,
    right: 6,
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  controlsRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  viewToggleRow: {
    flexDirection: "row",
    gap: 6,
  },
  viewToggleBtn: {
    padding: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  selectBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  selectText: {
    fontSize: 14,
    fontWeight: "600",
  },
});
