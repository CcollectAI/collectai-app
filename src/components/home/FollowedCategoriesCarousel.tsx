/**
 * Followed / personalized categories horizontal carousel.
 *
 * Displays a horizontal FlatList of category cards selected during
 * onboarding. Extracted from app/(tabs)/index.tsx.
 */
import React, { useCallback } from "react";
import { View, Text, FlatList, StyleSheet, type ListRenderItemInfo } from "react-native";
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
}

// ── Component ──────────────────────────────────────────────────────────

function FollowedCategoriesCarouselInner({
  theme,
  categories,
  onCategoryPress,
  hapticsEnabled = true,
}: FollowedCategoriesCarouselProps) {
  if (categories.length === 0) return null;

  const renderItem = useCallback(
    ({ item: catSlug }: ListRenderItemInfo<string>) => {
      const visual = CATEGORY_VISUAL[catSlug as CategoryId];
      if (!visual) return null;
      const displayName = catSlug
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
      return (
        <AnimatedPressable
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
        </AnimatedPressable>
      );
    },
    [theme.text, onCategoryPress, hapticsEnabled],
  );

  const keyExtractor = useCallback((item: string) => item, []);

  return (
    <>
      <View style={s.sectionHeader}>
        <Text style={[s.sectionTitle, { color: theme.text }]}>Your Categories</Text>
      </View>
      <FlatList
        data={categories}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={s.followedCatsRow}
        style={s.listContainer}
        maxToRenderPerBatch={10}
        windowSize={5}
      />
    </>
  );
}

export const FollowedCategoriesCarousel = React.memo(FollowedCategoriesCarouselInner);

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
  },
  listContainer: {
    marginBottom: 12,
  },
  followedCatsRow: {
    gap: 10,
    paddingHorizontal: 2,
    paddingVertical: 4,
  },
  followedCatCard: {
    width: 100,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    alignItems: "center",
  },
  followedCatIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  followedCatName: {
    fontSize: 12,
    fontWeight: "600",
    textAlign: "center",
  },
});
