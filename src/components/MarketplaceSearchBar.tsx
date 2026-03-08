/**
 * Search bar for the marketplace screen.
 *
 * Renders a pill-shaped TextInput with search icon, plus a
 * circular filter button with active-filter count badge.
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from "react";
import {
  View,
  TextInput,
  TouchableOpacity,
  Text,
  StyleSheet,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";

// ── Props ───────────────────────────────────────────────────────────────

interface MarketplaceSearchBarProps {
  theme: {
    text: string;
    muted: string;
    accent: string;
    border: string;
  };
  query: string;
  onQueryChange: (text: string) => void;
  onSubmit: () => void;
  onOpenFilter: () => void;
  activeFilterCount: number;
}

// ── Component ───────────────────────────────────────────────────────────

function MarketplaceSearchBarInner({
  theme,
  query,
  onQueryChange,
  onSubmit,
  onOpenFilter,
  activeFilterCount,
}: MarketplaceSearchBarProps) {
  return (
    <View style={s.searchFilterRow}>
      <View style={[s.searchRow, { borderColor: theme.border, flex: 1 }]}>
        <Ionicons
          name="search-outline"
          size={18}
          color={theme.muted}
          style={{ marginRight: 8 }}
        />
        <TextInput
          value={query}
          onChangeText={onQueryChange}
          onSubmitEditing={onSubmit}
          placeholder="Search items & collections"
          placeholderTextColor={theme.muted}
          accessibilityLabel="Search items and collections"
          style={[s.searchInput, { color: theme.text }]}
        />
      </View>
      <TouchableOpacity
        onPress={onOpenFilter}
        style={[
          s.filterButton,
          {
            borderColor: theme.border,
            backgroundColor:
              activeFilterCount > 0 ? theme.accent + "15" : "transparent",
          },
        ]}
        accessibilityLabel={`Filters${activeFilterCount > 0 ? `, ${activeFilterCount} active` : ""}`}
        accessibilityRole="button"
      >
        <Ionicons
          name="options-outline"
          size={20}
          color={activeFilterCount > 0 ? theme.accent : theme.muted}
        />
        {activeFilterCount > 0 && (
          <View style={s.filterCountBadge}>
            <Text style={s.filterCountBadgeText}>{activeFilterCount}</Text>
          </View>
        )}
      </TouchableOpacity>
    </View>
  );
}

export const MarketplaceSearchBar = React.memo(MarketplaceSearchBarInner);

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  searchFilterRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 4,
  },
  filterButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
  },
  filterCountBadge: {
    position: "absolute",
    top: -4,
    right: -4,
    backgroundColor: "#EF4444",
    borderRadius: 9,
    minWidth: 18,
    height: 18,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  filterCountBadgeText: {
    color: "#fff",
    fontSize: 10,
    fontWeight: "700",
  },
});
