/**
 * WatchlistFilterSort — Category filter chips, sort pill, and sort dropdown menu.
 */
import React from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";

type SortKey = 'priority' | 'newest' | 'price_asc' | 'price_desc' | 'custom';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'priority', label: 'Priority (High\u2192Low)' },
  { key: 'newest', label: 'Newest first' },
  { key: 'price_asc', label: 'Price (Low\u2192High)' },
  { key: 'price_desc', label: 'Price (High\u2192Low)' },
  { key: 'custom', label: 'Custom order' },
];

type ThemeColors = {
  accent: string;
  border: string;
  muted: string;
  text: string;
  card: string;
};

type Props = {
  colors: ThemeColors;
  hapticsEnabled: boolean;
  activeCategory: string | null;
  setActiveCategory: (cat: string | null) => void;
  sortKey: SortKey;
  setSortKey: (key: SortKey) => void;
  showSortMenu: boolean;
  setShowSortMenu: (v: boolean) => void;
  uniqueCategories: string[];
  categoryDisplayName: (slug: string) => string;
};

export { SortKey, SORT_OPTIONS };

export const WatchlistFilterSort = React.memo(function WatchlistFilterSort({
  colors,
  hapticsEnabled,
  activeCategory,
  setActiveCategory,
  sortKey,
  setSortKey,
  showSortMenu,
  setShowSortMenu,
  uniqueCategories,
  categoryDisplayName,
}: Props) {
  return (
    <>
      <View style={styles.filterSortRow}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.filterChipScroll}
          contentContainerStyle={styles.filterChipContent}
        >
          {/* "All" chip */}
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
              setActiveCategory(null);
            }}
            style={[
              styles.filterChip,
              { borderColor: !activeCategory ? colors.accent : colors.border },
              !activeCategory && { backgroundColor: colors.accent + '15' },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Show all categories"
            accessibilityState={{ selected: !activeCategory }}
          >
            <Text style={[styles.filterChipText, { color: !activeCategory ? colors.accent : colors.muted }]}>
              All
            </Text>
          </AnimatedPressable>

          {/* Category chips */}
          {uniqueCategories.map((catSlug) => {
            const isActive = activeCategory === catSlug;
            return (
              <AnimatedPressable
                key={catSlug}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                  setActiveCategory(isActive ? null : catSlug);
                }}
                style={[
                  styles.filterChip,
                  { borderColor: isActive ? colors.accent : colors.border },
                  isActive && { backgroundColor: colors.accent + '15' },
                ]}
                accessibilityRole="button"
                accessibilityLabel={`Filter by ${categoryDisplayName(catSlug)}`}
                accessibilityState={{ selected: isActive }}
              >
                <Text style={[styles.filterChipText, { color: isActive ? colors.accent : colors.muted }]}>
                  {categoryDisplayName(catSlug)}
                </Text>
              </AnimatedPressable>
            );
          })}
        </ScrollView>

        {/* Sort pill */}
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            setShowSortMenu(!showSortMenu);
          }}
          style={[styles.sortPill, { borderColor: colors.border, backgroundColor: colors.card }]}
          accessibilityRole="button"
          accessibilityLabel="Sort watchlist"
        >
          <Ionicons name="swap-vertical-outline" size={14} color={colors.accent} />
          <Text style={[styles.sortPillText, { color: colors.text }]} numberOfLines={1}>
            {SORT_OPTIONS.find((o) => o.key === sortKey)?.label.split(' ')[0] ?? 'Sort'}
          </Text>
        </AnimatedPressable>
      </View>

      {/* Sort dropdown menu */}
      {showSortMenu && (
        <View style={[styles.sortMenu, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {SORT_OPTIONS.map((opt) => {
            const isActive = sortKey === opt.key;
            return (
              <AnimatedPressable
                key={opt.key}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                  setSortKey(opt.key);
                  setShowSortMenu(false);
                }}
                style={[
                  styles.sortMenuItem,
                  isActive && { backgroundColor: colors.accent + '12' },
                ]}
                accessibilityRole="button"
                accessibilityState={{ selected: isActive }}
                accessibilityLabel={`Sort by ${opt.label}`}
              >
                <Text style={[styles.sortMenuItemText, { color: isActive ? colors.accent : colors.text }]}>
                  {opt.label}
                </Text>
                {isActive && (
                  <Ionicons name="checkmark" size={16} color={colors.accent} />
                )}
              </AnimatedPressable>
            );
          })}
        </View>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  filterSortRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
    gap: 8,
  },
  filterChipScroll: {
    flex: 1,
  },
  filterChipContent: {
    flexDirection: "row",
    alignItems: "center",
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    marginRight: 8,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
  },
  sortPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  sortPillText: {
    fontSize: 12,
    fontWeight: "600",
  },
  sortMenu: {
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    overflow: "hidden",
  },
  sortMenuItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  sortMenuItemText: {
    fontSize: 13,
    fontWeight: "500",
  },
});
