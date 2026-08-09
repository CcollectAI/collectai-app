/**
 * OfferAmountSheet — pick an offer amount as a percentage of a reference price,
 * or type your own.
 *
 * ONE component for both directions of the negotiation:
 *
 *   buyer  (app/listing/[id].tsx) reference = the ASKING price
 *   seller (app/offers.tsx)       reference = the asking price too, falling back
 *                                 to the buyer's offer when the listing row is
 *                                 gone (`listing_price` null)
 *
 * Two copies would drift — the same reason `collectorsApi` namespaces the P2P
 * methods and the offer column list lives in one constant server-side.
 *
 * ── Why this replaces an Alert ──────────────────────────────────────────────
 * Both ladders were `Alert.alert` with three hardcoded multipliers (buyer
 * 0.9/0.8/0.7, seller 1.1/1.2/1.35) and money-only labels, so:
 *   - the percentage was invisible: "€360" tells you nothing about the discount
 *     you are proposing without doing the arithmetic against the asking price
 *   - there was NO way to offer any other number. `Alert.prompt` is iOS-only, so
 *     a free-text amount was impossible in that container — the ladder was a
 *     workaround for the container, presented as a product decision.
 *
 * ── The percentages ────────────────────────────────────────────────────────
 * −10 / −5 / +5 / +10 of the reference, and they are signed on purpose. Above
 * asking is a real move on a scarce collectible, and for a SELLER countering,
 * a percentage below asking is exactly the concession a counter usually is.
 *
 * Steps are derived from the reference at render time rather than stored, so a
 * listing whose price changed under us (PATCH /p2p/listings, spec §8b) cannot
 * present a stale ladder.
 *
 * ── Bounds ─────────────────────────────────────────────────────────────────
 * `amount` is `gt=0, le=1_000_000` on both server models, so the custom field
 * enforces the same range HERE and says which one failed. Sending 0 to be told
 * "422: ensure this value is greater than 0" is a server error message doing a
 * client's job. There is deliberately no floor tied to the asking price: the
 * server does not impose one (its price verdict is advisory, never a rejection),
 * and inventing one client-side would block a legitimate lowball the seller is
 * free to decline.
 */
import React, { useCallback, useMemo, useState } from 'react';
import { View, Text, StyleSheet, TextInput, ActivityIndicator } from 'react-native';

import { BottomSheetModal } from '@/components/BottomSheetModal';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { formatPrice, getCurrencySymbol } from '@/lib/format';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';
import type { Currency, NumberLocale } from '@/lib/settings';

/** The colour slots this sheet uses. Structural, matching BottomSheetModal's own
 *  prop rather than importing a theme type that does not exist — `useAppTheme()`
 *  returns a wider object and any caller can pass it. */
type SheetColors = {
  text: string;
  muted: string;
  card: string;
  border: string;
  accent: string;
  accentText: string;
  background: string;
  [key: string]: unknown;
};

/** Server bound: `amount: float = Field(..., gt=0, le=1_000_000)`. */
const MAX_AMOUNT = 1_000_000;

/** Signed, ordered low → high so the row reads like a dial. Not exported: it was,
 *  and nothing imported it — an exported constant with no consumer is the shape
 *  that later gets edited in one place and read from another. */
const OFFER_STEPS = [-10, -5, 5, 10] as const;

export type OfferAmountSheetProps = {
  visible: boolean;
  onClose: () => void;
  /** Sheet heading, e.g. "Make an offer" / "Counter offer". */
  title: string;
  /** The price the percentages are computed FROM. */
  reference: number;
  /** What that price is, in words: "Asking" / "Their offer". Shown to the user,
   *  because a percentage with an unstated basis is not information. */
  referenceLabel: string;
  /** Typed, not `string`: formatPrice/getCurrencySymbol are keyed on the 7
   *  supported currencies, and a bare string silently misses a new one. */
  currency: Currency;
  numberLocale?: NumberLocale;
  submitLabel: string;
  busy?: boolean;
  colors: SheetColors;
  hapticsEnabled?: boolean;
  onSubmit: (amount: number) => void;
};

export function OfferAmountSheet({
  visible, onClose, title, reference, referenceLabel, currency, numberLocale,
  submitLabel, busy = false, colors, hapticsEnabled = true, onSubmit,
}: OfferAmountSheetProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const [custom, setCustom] = useState('');

  const steps = useMemo(
    () => OFFER_STEPS.map((pct) => ({
      pct,
      // Round to cents, not to whole units: a 5% step off €18.99 is €18.04, and
      // rounding that to €18 quietly changes the offer the label promises.
      amount: Math.round(reference * (1 + pct / 100) * 100) / 100,
    })).filter((s) => s.amount > 0),
    [reference],
  );

  /** Parsed custom amount, or null when the box is empty or unusable. Accepts a
   *  comma decimal separator — most of the app's currencies are written that
   *  way, and rejecting "18,50" as unparseable reads as the field being broken. */
  const parsedCustom = useMemo(() => {
    const cleaned = custom.replace(/[^0-9.,]/g, '').replace(',', '.');
    if (!cleaned) return null;
    const n = parseFloat(cleaned);
    if (!Number.isFinite(n) || n <= 0 || n > MAX_AMOUNT) return null;
    return Math.round(n * 100) / 100;
  }, [custom]);

  const customTouched = custom.trim().length > 0;
  /** A typed amount always wins over a tapped chip — it is the more specific
   *  intent, and it is what the user did last.
   *
   *  NOT `parsedCustom ?? selected`. That was wrong in one specific way: type an
   *  UNUSABLE amount ("0", "abc") after tapping a chip and `parsedCustom` is
   *  null, so it fell back to the chip — while `active` below already showed the
   *  chip as deselected. The sheet displayed no selection, the button read
   *  "Send offer · €360", and pressing it sent the chip the user had visibly
   *  abandoned. Once the box has anything in it, the box is the answer: valid
   *  means submit that, invalid means submit nothing. */
  const amount = customTouched ? parsedCustom : selected;

  /** The percentage a custom amount represents, so a typed number stays legible
   *  in the same terms as the chips. */
  const customPct = useMemo(() => {
    if (parsedCustom == null || reference <= 0) return null;
    return Math.round(((parsedCustom - reference) / reference) * 1000) / 10;
  }, [parsedCustom, reference]);

  const customError = useMemo(() => {
    if (!customTouched || parsedCustom != null) return null;
    const cleaned = custom.replace(/[^0-9.,]/g, '').replace(',', '.');
    const n = parseFloat(cleaned);
    if (Number.isFinite(n) && n > MAX_AMOUNT) {
      return `The most you can offer is ${formatPrice(MAX_AMOUNT, currency, numberLocale)}.`;
    }
    if (Number.isFinite(n) && n <= 0) return 'Enter an amount above zero.';
    return 'Enter an amount, e.g. 45 or 45,50.';
  }, [custom, customTouched, parsedCustom, currency, numberLocale]);

  const handleClose = useCallback(() => {
    setSelected(null);
    setCustom('');
    onClose();
  }, [onClose]);

  const handleSubmit = useCallback(() => {
    if (amount == null || busy) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: hapticsEnabled });
    setSelected(null);
    setCustom('');
    onSubmit(amount);
  }, [amount, busy, hapticsEnabled, onSubmit]);

  return (
    <BottomSheetModal
      visible={visible}
      onClose={handleClose}
      title={title}
      colors={colors}
      maxHeight="70%"
    >
      <View style={styles.body}>
        <Text style={[styles.basis, { color: colors.muted }]}>
          {referenceLabel} {formatPrice(reference, currency, numberLocale)}
        </Text>

        <View style={styles.chips}>
          {steps.map(({ pct, amount: stepAmount }) => {
            // A tapped chip is deselected visually once something is typed, so
            // the sheet never shows two different answers as both chosen.
            const active = !customTouched && selected === stepAmount;
            return (
              <AnimatedPressable
                key={pct}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                  setCustom('');
                  setSelected(stepAmount);
                }}
                style={[
                  styles.chip,
                  { borderColor: active ? colors.accent : colors.border, backgroundColor: colors.card },
                  active && { backgroundColor: colors.accent + '1E' },
                ]}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={
                  `${pct > 0 ? 'Plus' : 'Minus'} ${Math.abs(pct)} percent, `
                  + `${formatPrice(stepAmount, currency, numberLocale)}`
                }
              >
                <Text style={[styles.chipPct, { color: active ? colors.accent : colors.text }]}>
                  {/* U+2212 MINUS, not a hyphen: at 12pt a hyphen next to a
                      digit reads as a dash in the price. */}
                  {pct > 0 ? '+' : '−'}{Math.abs(pct)}%
                </Text>
                <Text style={[styles.chipAmount, { color: colors.muted }]}>
                  {formatPrice(stepAmount, currency, numberLocale)}
                </Text>
              </AnimatedPressable>
            );
          })}
        </View>

        <Text style={[styles.label, { color: colors.text }]}>Custom offer</Text>
        <View style={[styles.field, { borderColor: colors.border, backgroundColor: colors.card }]}>
          <Text style={[styles.currency, { color: colors.muted }]}>
            {getCurrencySymbol(currency)}
          </Text>
          <TextInput
            value={custom}
            onChangeText={setCustom}
            placeholder="Any amount"
            placeholderTextColor={colors.muted}
            keyboardType="decimal-pad"
            maxLength={12}
            style={[styles.input, { color: colors.text }]}
            accessibilityLabel="Custom offer amount"
          />
          {customPct != null ? (
            <Text style={[styles.customPct, { color: colors.muted }]}>
              {customPct > 0 ? '+' : customPct < 0 ? '−' : ''}
              {Math.abs(customPct)}%
            </Text>
          ) : null}
        </View>
        {customError ? (
          <Text style={[styles.error, { color: colors.muted }]}>{customError}</Text>
        ) : null}

        <AnimatedPressable
          onPress={handleSubmit}
          disabled={amount == null || busy}
          style={[
            styles.cta,
            amount != null && !busy
              ? { backgroundColor: colors.accent }
              // accentText is ONLY legible on an accent fill — on a border fill
              // it is invisible in high-contrast dark (docs/ui-playbook.md).
              : { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
          ]}
          accessibilityRole="button"
          accessibilityState={{ disabled: amount == null || busy }}
          accessibilityLabel={
            amount != null
              ? `${submitLabel} of ${formatPrice(amount, currency, numberLocale)}`
              : submitLabel
          }
        >
          {/* A spinner while the request is in flight. The buyer's path keeps
              this sheet OPEN across the call (so a 409 lands with the amount
              still in the box), so without this the button sits greyed with
              static text and the send reads as "nothing happened" — the same
              rule applied to the barcode watchlist button. */}
          {busy ? (
            <ActivityIndicator size="small" color={colors.muted} />
          ) : (
            <Text
              style={[
                styles.ctaText,
                { color: amount != null ? colors.accentText : colors.muted },
              ]}
            >
              {amount != null
                ? `${submitLabel} · ${formatPrice(amount, currency, numberLocale)}`
                : submitLabel}
            </Text>
          )}
        </AnimatedPressable>
      </View>
    </BottomSheetModal>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, paddingBottom: 28, gap: 10 },
  basis: { fontSize: textToken.sm },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 2 },
  chip: {
    flex: 1, minWidth: 72, alignItems: 'center', gap: 2,
    borderWidth: 1, borderRadius: radius.md,
    paddingHorizontal: 10, paddingVertical: 10,
  },
  chipPct: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  chipAmount: { fontSize: textToken.sm },
  label: { fontSize: textToken.sm, fontWeight: fontWeight.semibold, marginTop: 10 },
  field: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    borderWidth: 1, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 11,
  },
  currency: { fontSize: textToken.md },
  input: { flex: 1, fontSize: textToken.lg, padding: 0 },
  customPct: { fontSize: textToken.sm },
  error: { fontSize: textToken.sm },
  cta: { alignItems: 'center', borderRadius: radius.sm, paddingVertical: 13, marginTop: 12 },
  ctaText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
});

export default OfferAmountSheet;
