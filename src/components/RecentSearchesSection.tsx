/**
 * Recent searches chip row for the marketplace screen.
 *
 * Renders a "Recent searches" heading and a row of pressable
 * chips for previously-entered search terms.
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { AnimatedPressable } from "@/motion";

// ── Props ───────────────────────────────────────────────────────────────

interface RecentSearchesSectionProps {
  theme: {
    text: string;
    accent: string;
  };
  recentSearches: string[];
  onChipPress: (term: string) => void;
}

// ── Component ───────────────────────────────────────────────────────────

function RecentSearchesSectionInner({
  theme,
  recentSearches,
  onChipPress,
}: RecentSearchesSectionProps) {
  if (recentSearches.length === 0) return null;

  return (
    <View style={s.section}>
      <Text style={[s.sectionTitle, { color: theme.text }]}>Recent searches</Text>
      <View style={s.chipRow}>
        {recentSearches.map((term) => (
          <AnimatedPressable
            key={term}
            style={[s.chip, { backgroundColor: theme.accent + "15" }]}
            onPress={() => onChipPress(term)}
            accessibilityRole="button"
            accessibilityLabel={`Search for ${term}`}
          >
            <Text style={[s.chipText, { color: theme.text }]}>{term}</Text>
          </AnimatedPressable>
        ))}
      </View>
    </View>
  );
}

export const RecentSearchesSection = React.memo(RecentSearchesSectionInner);

// ── Styles ──────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  section: {
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 6,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  chip: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  chipText: {
    fontSize: 12,
    fontWeight: "500",
  },
});
