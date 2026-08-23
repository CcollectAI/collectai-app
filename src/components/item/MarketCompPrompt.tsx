/**
 * "We found a market comp — use it, or keep yours?"
 *
 * WHAT THIS REPLACES
 * Manual add already did this silently. It saves what you typed, then fires
 * `revalueItem`, which writes a catalogue-derived valuation into
 * `quick_predictions` — the TOP of the value chain. So a catalogue-linked item
 * started showing our number while the member's own figure sat in
 * `estimated_value`, never displayed, with nothing saying it had happened.
 *
 * Same mechanism, but the member is told and gets to choose. Deliberately NOT
 * a modal on save: the save succeeds first, and this asks afterwards, so the
 * question can be ignored without blocking anything.
 *
 * "Keep mine" is honoured by `v_item_values_v1`, which puts an explicit
 * `attrs.value_choice = 'mine'` ABOVE the model. Without that branch the
 * question would be dishonest — both prediction tables outrank
 * `estimated_value`, and the catalogue model cannot be deleted out of the way
 * because it is global data, not this member's row.
 *
 * Recording the answer is what stops a later revalue silently overturning a
 * deliberate decision.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import { isMarketBacked } from '@/components/ValueSourceChip';

export type ValueChoice = 'market' | 'mine';

interface OfferInput {
  /** `v_item_values_v1.value_source` for the value currently shown. */
  valueSource?: string | null;
  /** The value currently shown (the market number, when market-backed). */
  currentValue?: number | null;
  /** What the member typed, from `items.estimated_value`. */
  userEstimate?: number | null;
  /** `attrs.value_choice`, if they have already answered. */
  existingChoice?: string | null;
}

/**
 * Ask only when there is a real, ANSWERABLE question.
 *
 * All four conditions matter:
 *  - the shown value is market-backed (otherwise there is no comp to offer)
 *  - the member actually typed something (otherwise there is nothing to keep)
 *  - they have not already answered (asking twice reads as the app ignoring you)
 *  - the two numbers differ (offering a choice between €50 and €50 is noise)
 */
export function shouldOfferComp(input: OfferInput): boolean {
  const { valueSource, currentValue, userEstimate, existingChoice } = input;
  if (existingChoice === 'mine' || existingChoice === 'market') return false;
  if (!isMarketBacked(valueSource)) return false;
  if (typeof currentValue !== 'number' || !(currentValue > 0)) return false;
  if (typeof userEstimate !== 'number' || !(userEstimate > 0)) return false;
  // Compared in CENTS, not with an epsilon. `Math.abs(50.01 - 50) >= 0.01` is
  // FALSE in floating point (the difference is 0.00999...), so a genuine
  // one-cent disagreement silently failed to prompt. Rounding to integer cents
  // is exact for money and removes the question of how big an epsilon should
  // be. Caught by the boundary case in the test rather than in use.
  return Math.round(currentValue * 100) !== Math.round(userEstimate * 100);
}

interface MarketCompPromptProps {
  marketValue: number;
  userEstimate: number;
  onChoose: (choice: ValueChoice) => void;
  busy?: boolean;
}

export const MarketCompPrompt = React.memo(function MarketCompPrompt({
  marketValue,
  userEstimate,
  onChoose,
  busy = false,
}: MarketCompPromptProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const cur = settings.currency;

  return (
    <View
      style={[
        styles.card,
        // Alpha of the accent, never the accent itself, so the text stays on a
        // theme colour when the palette swaps.
        { backgroundColor: colors.accent + '12', borderColor: colors.accent + '40' },
      ]}
    >
      <Text style={[styles.title, { color: colors.text }]}>
        We found a market price for this
      </Text>
      <Text style={[styles.body, { color: colors.muted }]}>
        Our comps say {formatPrice(marketValue, cur)}. You said{' '}
        {formatPrice(userEstimate, cur)}. Which should we show?
      </Text>

      <View style={styles.actions}>
        <AnimatedPressable
          onPress={() => onChoose('market')}
          disabled={busy}
          style={[styles.btn, { backgroundColor: colors.accent }]}
          accessibilityRole="button"
          accessibilityLabel={`Use the market price, ${formatPrice(marketValue, cur)}`}
        >
          <Text style={[styles.btnText, { color: colors.accentText }]} numberOfLines={1}>
            Use {formatPrice(marketValue, cur)}
          </Text>
        </AnimatedPressable>

        <AnimatedPressable
          onPress={() => onChoose('mine')}
          disabled={busy}
          style={[styles.btn, styles.btnGhost, { borderColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel={`Keep my estimate, ${formatPrice(userEstimate, cur)}`}
        >
          <Text style={[styles.btnText, { color: colors.text }]} numberOfLines={1}>
            Keep {formatPrice(userEstimate, cur)}
          </Text>
        </AnimatedPressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  card: {
    // NO `marginHorizontal` — `app/item/[id].tsx`'s scroll `content` already
    // pads 16, so this was the only card on the screen inset 32 while every
    // other one sat at 16. That is the reported "the alignment is off".
    //
    // `marginBottom` matches `marginTop`: the valuation card directly below
    // carries its own margins now, but this card must not depend on that —
    // when it was the only one with a top margin and no bottom one, the two
    // bordered boxes touched.
    marginTop: 12,
    marginBottom: 12,
    padding: 14,
    borderWidth: 1,
    borderRadius: radius.md,
    gap: 6,
  },
  title: { fontSize: textToken.lg, fontWeight: fw.bold },
  body: { fontSize: textToken.sm },
  // nowrap + shrink: a third action is not coming, and a wrapped button reads
  // as a separate decision (ui-playbook).
  actions: { flexDirection: 'row', flexWrap: 'nowrap', gap: 8, marginTop: 8 },
  btn: {
    flex: 1,
    flexShrink: 1,
    minHeight: 44,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
  btnGhost: { borderWidth: 1, backgroundColor: 'transparent' },
  btnText: { fontSize: textToken.sm, fontWeight: fw.bold, textAlign: 'center' },
});

export default MarketCompPrompt;
