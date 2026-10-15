/**
 * Item + postage = total, the way Vinted shows a price (2026-10-16).
 *
 * Walked as a buyer: a EUR 20 + EUR 2,50 listing, an accepted EUR 19 offer, and
 * "Pay the seller" said "Agreed amount EUR 19" — the postage reached nothing
 * after the listing page, so the buyer could not tell whether to send 19 or
 * 21,50. Vinted's rule: an offer is on the ITEM only, postage is set by the
 * seller, cannot be negotiated, and is added on top; the buyer sees all three
 * numbers before paying.
 *
 * Three numbers are safe to show together only because member prices now
 * render to the cent (formatMemberPrice, `exact`): rounded, 42,50 + 6,50 read
 * "43 + 7 = 49" — the reason the listing used to print the total alone.
 *
 * `shipping` null = the seller stated no postage: say so, never add 0.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTranslation } from 'react-i18next';

type Props = {
  amount: number;
  shipping: number | null | undefined;
  format: (amount: number) => string;
  colors: { text: string; muted: string; border: string };
  /** Label of the first row: "Your offer", "Item (agreed)", … */
  itemLabel?: string;
  totalLabel?: string;
};

export function PostageBreakdown({ amount, shipping, format, colors, itemLabel, totalLabel }: Props) {
  const { t } = useTranslation();
  const known = shipping != null;
  return (
    <View style={styles.box} accessibilityRole="summary">
      <Row label={itemLabel ?? t('postage.item', { defaultValue: 'Item' })} value={format(amount)} color={colors.text} muted={colors.muted} />
      <Row
        label={t('postage.postage', { defaultValue: 'Postage' })}
        value={known
          ? (shipping === 0 ? t('postage.free', { defaultValue: 'Free' }) : format(shipping))
          : t('postage.not_stated', { defaultValue: 'Not stated — agree it with the seller' })}
        color={known ? colors.text : colors.muted}
        muted={colors.muted}
      />
      {known ? (
        <View style={[styles.totalRow, { borderTopColor: colors.border }]}>
          <Text style={[styles.totalLabel, { color: colors.text }]}>{totalLabel ?? t('postage.total', { defaultValue: 'Total' })}</Text>
          <Text selectable style={[styles.totalValue, { color: colors.text }]}>{format(Math.round((amount + shipping) * 100) / 100)}</Text>
        </View>
      ) : null}
      <Text style={[styles.note, { color: colors.muted }]}>
        {t('postage.note', { defaultValue: 'Offers are for the item. Postage is set by the seller and added on top.' })}
      </Text>
    </View>
  );
}

function Row({ label, value, color, muted }: { label: string; value: string; color: string; muted: string }) {
  return (
    <View style={styles.row}>
      <Text style={[styles.label, { color: muted }]}>{label}</Text>
      <Text style={[styles.value, { color }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: 6 },
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  label: { fontSize: 14 },
  value: { fontSize: 14, fontWeight: '500', flexShrink: 1, textAlign: 'right' },
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: StyleSheet.hairlineWidth, paddingTop: 8, marginTop: 2 },
  totalLabel: { fontSize: 15, fontWeight: '700' },
  totalValue: { fontSize: 15, fontWeight: '700' },
  note: { fontSize: 12, marginTop: 4 },
});
