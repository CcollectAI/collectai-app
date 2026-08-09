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
  /**
   * Render as a pinned bar: opaque background + hairline underline, so a
   * scrolling list passes cleanly UNDER it.
   *
   * Only for callers where the chips sit OUTSIDE the scroll container
   * (category-browse). On the category page the chips scroll with the content,
   * and the underline would read as a stray divider in the middle of the page.
   */
  pinned?: boolean;
};

function CategorySortChips({ sort, onChange, colors, pinned = false }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      // A horizontal ScrollView in a flex COLUMN parent has an unconstrained
      // cross axis and will grow past its content. flexGrow:0 pins it to the
      // chip height so the grid below starts where it looks like it should.
      style={[
        styles.bar,
        pinned && [styles.pinnedBar, { backgroundColor: colors.background, borderBottomColor: colors.border }],
      ]}
      contentContainerStyle={styles.row}
    >
      {CHIPS.map((c) => {
        const active = c.key === sort;
        const label = c.label;
        const inner = (
          <>
            <Ionicons name={c.icon} size={13} color={active ? '#fff' : colors.muted} allowFontScaling={false} />
            {/* Cap Dynamic Type on this compact pill: an unbounded system text
                size scales the label past the chip and overflow:hidden shears
                the bottoms ("only the tops visible"). 1.2x stays legible. */}
            <Text
              maxFontSizeMultiplier={1.2}
              style={[styles.text, { color: active ? '#fff' : colors.muted }]}
            >
              {label}
            </Text>
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
  // Applies ALWAYS — a horizontal ScrollView in a flex-column parent has an
  // unconstrained cross axis and grows past its content without this.
  bar: {
    flexGrow: 0,
  },
  // `pinned` only. When the chips sit outside the scroll container, grid rows
  // slide up to meet them; with edge-to-edge tiles and no boundary a
  // half-scrolled row sits flush under the pills and reads as the background
  // cutting the chip bar off. An opaque background + hairline + zIndex makes
  // this a defined edge that content passes under — the same treatment
  // ScreenHeader uses, for the same reason.
  pinnedBar: {
    zIndex: 5,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  row: { gap: 8, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    paddingVertical: 7,
    paddingHorizontal: 13,
    // Tall enough for the full label line box.
    minHeight: 34,
    borderRadius: 999,
    // NO `overflow: 'hidden'` — it was shearing the label's bottoms ("words look
    // halved") whenever the line box was a hair taller than the content area.
    // borderRadius already rounds the gradient/pill, so hidden overflow bought
    // nothing but the clipping bug. Text scaling is bounded via
    // maxFontSizeMultiplier on the <Text>, so nothing overflows the pill anyway.
  },
  inactive: { borderWidth: 1 },
  // No fixed lineHeight — a hard value would itself clip Dynamic-Type-scaled
  // text. Scaling is bounded via maxFontSizeMultiplier on the <Text> instead,
  // and the pill grows within that cap (minHeight floor above).
  // includeFontPadding/textAlignVertical center the glyphs on Android.
  text: {
    fontSize: 12.5,
    fontWeight: '600',
    includeFontPadding: false,
    textAlignVertical: 'center',
  },
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
