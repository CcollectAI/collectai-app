/**
 * Says WHERE an item's value came from.
 *
 * Until 2026-08-19 the app rendered all four links of the value chain
 * identically: a EUR 185 backed by sold comps and a EUR 185 someone typed into
 * a text field were the same pixels. That is hardest to spot exactly where it
 * matters most — the 40+ categories with no sold-comp source, where the
 * displayed "value" IS the member's own guess wearing the app's authority.
 *
 * Reads `v_item_values_v1.value_source`. One component, so the item card and
 * the detail screen cannot end up describing the same number two ways.
 *
 * Renders NOTHING for an unknown source rather than guessing. "We don't know
 * where this came from" is not a claim worth making, and an always-present chip
 * that sometimes says nothing is the empty-grey-box shape from the ui-playbook.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

import { useAppTheme } from '@/hooks/useAppTheme';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';

/** Sources that rest on market data rather than on somebody's opinion. */
const MARKET_SOURCES = new Set(['catalog_daily', 'catalog_model', 'quick_scan']);

export function isMarketBacked(source?: string | null): boolean {
  return !!source && MARKET_SOURCES.has(source);
}

type Descriptor = { label: string; tone: 'market' | 'estimate' };

export function describeValueSource(source?: string | null): Descriptor | null {
  switch (source) {
    // Both are the catalogue model; a member does not need to know which table
    // answered, only that we did not make the number up.
    case 'catalog_daily':
    case 'catalog_model':
    case 'quick_scan':
      return { label: 'Market estimate', tone: 'market' };
    // The scan's own vision guess. NOT "your estimate" — the member did not
    // say it, and blaming them for the app's number is the wrong way round.
    case 'app_estimate':
      return { label: 'App estimate', tone: 'estimate' };
    case 'user_estimate':
      return { label: 'Your estimate', tone: 'estimate' };
    // 'none' means the value is 0 because nothing answered. Saying "no
    // estimate" beside a EUR 0.00 is the honest reading.
    case 'none':
      return { label: 'Not priced yet', tone: 'estimate' };
    default:
      return null;
  }
}

interface ValueSourceChipProps {
  source?: string | null;
  /** Compact form for list rows: text only, no pill. */
  inline?: boolean;
}

export const ValueSourceChip = React.memo(function ValueSourceChip({
  source,
  inline = false,
}: ValueSourceChipProps) {
  const { colors } = useAppTheme();
  const d = describeValueSource(source);
  if (!d) return null;

  /**
   * ONE treatment for every source (2026-08-20).
   *
   * The tone used to pick the colour — accent for market-backed, muted for an
   * estimate — so the same chip was teal on one item and grey on the next.
   * Reported by putting two item cards side by side: *"the label color, format
   * and size should be the same across all items."*
   *
   * The colour was a SECOND encoding of what the word already says. "Market
   * estimate", "Your estimate", "App estimate" and "Not priced yet" are four
   * different sentences; painting them two different colours adds nothing a
   * reader did not already have, and it cost the screen its consistency. The
   * provenance signal is not lost — it is in the label, where it is readable
   * rather than inferred, and where a colour-blind member gets it too.
   *
   * `tone` is still returned by `describeValueSource` and still used by the
   * analytics split; it just no longer decides how this chip looks.
   */
  const tint = colors.muted;

  if (inline) {
    return (
      <Text style={[styles.inline, { color: tint }]} numberOfLines={1}>
        {d.label}
      </Text>
    );
  }

  return (
    <View
      style={[
        styles.chip,
        // An alpha of the tone, never the tone itself, so the label stays on a
        // theme colour and cannot go invisible when the palette swaps.
        { backgroundColor: tint + '1E', borderColor: tint + '40' },
      ]}
    >
      <Text style={[styles.chipText, { color: tint }]}>{d.label}</Text>
    </View>
  );
});

const styles = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
    borderWidth: 1,
  },
  // `sm` (12), not `xs` (10). The type scale bans 10pt for anything a user
  // reads, and this chip is the only thing on the card that says where the
  // number came from — the one line that must not be squinted at.
  chipText: { fontSize: textToken.sm, fontWeight: fw.semibold },
  inline: { fontSize: textToken.sm, fontWeight: fw.semibold },
});

export default ValueSourceChip;
