/**
 * CategorySortChips — page-level sort chips for the category overview
 * (mockup: web/category-redesign-preview.html `.chips`). Sit directly under
 * the category header, OUTSIDE the rail card. Active chip = tiffany gradient
 * (#81D8D0 → #2C7873) with white text + soft shadow; inactive = white pill
 * with hairline border. "All" is just "All" (no live count), and "By set"
 * is NOT a chip — it has its own carousel under the main rail.
 */
import React from 'react';
import { ScrollView, View, Text, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { AnimatedPressable } from '@/motion';
import { colors as tokens } from '@/theme/tokens';
import type { AppTheme } from '@/hooks/useAppTheme';

export type CatalogSortKey = 'all' | 'value' | 'newest' | 'set';

const CHIPS: { key: CatalogSortKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: 'all', label: 'All', icon: 'grid-outline' },
  { key: 'value', label: 'Most valuable', icon: 'diamond-outline' },
  { key: 'newest', label: 'Newest', icon: 'sparkles-outline' },
];

type Props = {
  sort: CatalogSortKey;
  onChange: (sort: CatalogSortKey) => void;
  colors: AppTheme['colors'];
};

function CategorySortChips({ sort, onChange, colors }: Props) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {CHIPS.map((c) => {
        const active = c.key === sort;
        const label = c.label;
        const inner = (
          <>
            <Ionicons name={c.icon} size={13} color={active ? '#fff' : colors.muted} />
            <Text style={[styles.text, { color: active ? '#fff' : colors.muted }]}>{label}</Text>
          </>
        );
        return (
          <AnimatedPressable
            key={c.key}
            onPress={() => onChange(c.key)}
            accessibilityRole="button"
            accessibilityState={{ selected: active }}
            accessibilityLabel={`Sort by ${label}`}
            style={active ? styles.activeShadow : undefined}
          >
            {active ? (
              <LinearGradient
                colors={[tokens.brand.base, tokens.brand.deep]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={styles.chip}
              >
                {inner}
              </LinearGradient>
            ) : (
              <ScrollViewlessChip colors={colors}>{inner}</ScrollViewlessChip>
            )}
          </AnimatedPressable>
        );
      })}
    </ScrollView>
  );
}

// Plain inactive pill (kept tiny + local; the gradient variant above needs a
// different wrapper element, hence the split).
function ScrollViewlessChip({ children, colors }: { children: React.ReactNode; colors: AppTheme['colors'] }) {
  return (
    <View style={[styles.chip, styles.inactive, { backgroundColor: colors.card, borderColor: colors.border }]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { gap: 8, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingVertical: 7,
    paddingHorizontal: 13,
    borderRadius: 999,
    overflow: 'hidden',
  },
  inactive: { borderWidth: 1 },
  text: { fontSize: 12.5, fontWeight: '600' },
  activeShadow: Platform.select({
    ios: {
      shadowColor: '#2C7873',
      shadowOpacity: 0.32,
      shadowRadius: 8,
      shadowOffset: { width: 0, height: 3 },
    },
    default: { elevation: 4 },
  }) as object,
});

export default React.memo(CategorySortChips);
