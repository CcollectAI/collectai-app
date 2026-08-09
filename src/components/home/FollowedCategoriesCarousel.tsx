/**
 * Followed / personalized categories, as full-width banners.
 *
 * Was a horizontal carousel of small square tiles. A square tile wastes the
 * row it occupies (one short word in a 100pt box) and, with only a couple of
 * followed categories, a horizontal scroller reads as a stray block rather
 * than a list. Full-width banners stack, use the row, and leave room for the
 * name plus a chevron affordance.
 *
 * Rendered with .map rather than a FlatList: the list is a handful of items and
 * the parent is a ScrollView — a nested vertical VirtualizedList there both
 * warns and breaks scrolling.
 */
import React, { useCallback } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { CATEGORY_VISUAL, type CategoryId } from "@/data/categories";

// ── Props ──────────────────────────────────────────────────────────────

interface FollowedCategoriesCarouselProps {
  theme: {
    text: string;
  };
  categories: string[];
  onCategoryPress: (categorySlug: string) => void;
  hapticsEnabled?: boolean;
  /** Home renders its own "Your Categories" heading so the summary stats can
   *  sit between the heading and these banners. */
  showHeader?: boolean;
}

// ── Component ──────────────────────────────────────────────────────────

function FollowedCategoriesCarouselInner({
  theme,
  categories,
  onCategoryPress,
  hapticsEnabled = true,
  showHeader = true,
}: FollowedCategoriesCarouselProps) {
  const renderItem = useCallback(
    (catSlug: string) => {
      const visual = CATEGORY_VISUAL[catSlug as CategoryId];
      if (!visual) return null;
      const displayName = catSlug
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
      return (
        <AnimatedPressable
          key={catSlug}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            onCategoryPress(catSlug);
          }}
          style={[
            s.followedCatCard,
            { backgroundColor: visual.accentColor + "15", borderColor: visual.accentColor + "40" },
          ]}
          accessibilityRole="button"
          accessibilityLabel={`Browse ${displayName}`}
        >
          <View style={[s.followedCatIcon, { backgroundColor: visual.accentColor + "25" }]}>
            <Ionicons
              name={(visual.iconName || "cube") as keyof typeof Ionicons.glyphMap}
              size={20}
              color={visual.accentColor}
            />
          </View>
          <Text style={[s.followedCatName, { color: theme.text }]} numberOfLines={1}>
            {displayName}
          </Text>
          <Ionicons name="chevron-forward" size={18} color={visual.accentColor} />
        </AnimatedPressable>
      );
    },
    [theme.text, onCategoryPress, hapticsEnabled],
  );

  // After the hooks — an early return above them changes hook order between
  // renders, which React treats as an error.
  if (categories.length === 0) return null;

  return (
    <View style={s.listContainer}>
      {showHeader && (
        <View style={s.sectionHeader}>
          <Text style={[s.sectionTitle, { color: theme.text }]}>Your Categories</Text>
        </View>
      )}
      {categories.map(renderItem)}
    </View>
  );
}

export const FollowedCategoriesCarousel = React.memo(FollowedCategoriesCarouselInner);

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    // 10 put the first tile hard under the heading, so the two read as one
    // clumped block and the tile crowded the section above it.
    marginTop: 8,
    marginBottom: 18,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
  },
  listContainer: {
    marginBottom: 12,
    gap: 10,
  },
  // Full-width banner: icon, name, chevron on one row.
  followedCatCard: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: 14,
    borderWidth: 1,
    paddingVertical: 14,
    paddingHorizontal: 14,
  },
  followedCatIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  followedCatName: {
    // flex:1 pushes the chevron to the trailing edge and lets a long category
    // name ellipsize instead of shoving it off the banner.
    flex: 1,
    fontSize: 15,
    fontWeight: "700",
  },
});
