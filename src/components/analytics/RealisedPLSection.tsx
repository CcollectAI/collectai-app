/**
 * RealisedPLSection — what a member ACTUALLY made, after every fee on both sides.
 *
 * `GET /portfolio/realised-pl` has existed since 2026-09-18 with ZERO callers
 * (class T), so the one number this app can state as a RESULT was computed and
 * displayed nowhere. The only Sales tab lives on `app/sell/dashboard.tsx`,
 * which `check:reachable` lists as having no inbound navigation.
 *
 * Why it sits beside `unrealizedPL` rather than replacing it: that figure is a
 * projection against a live estimate, and for every item without a purchase
 * price it measures how far the MODEL moved (see the comment above
 * `rankPositions` in `app/analytics.tsx`). This is the opposite — money that
 * changed hands.
 *
 * ⚠️ THE EXCLUSIONS ARE THE FEATURE. `docs/COLLECTOR_DEMAND.md` §5 exists
 * because a EUR 956.25 card sold for EUR 1000 looks like EUR 44 of profit and
 * is a EUR 104 LOSS once fees and postage land. A total that quietly folds in
 * sales with an unknown basis or unrecorded postage reproduces that error, so
 * both counts are shown and neither is summed into the headline. The server
 * already withholds them: `profit` is null unless `cost_basis_known` AND
 * `shipping_known`.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { text, fontWeight, radius } from '@/theme/tokens';
// `{ cents: true }` on every figure here: this card states a SETTLED result,
// and §5's worked example only works with them — a EUR 956.25 basis on a card
// sold for EUR 1000 looks like a EUR 44 gain and is a EUR 104.05 loss. The app
// default is whole euros because an ESTIMATE carrying two decimals claims a
// precision the model does not have. Nothing here is an estimate.
import { fmtCurrency } from '@/lib/format';
import { useSettings } from '@/lib/settings';
import type { RealisedPL } from '@/api/portfolioApi';

type Props = {
  data: RealisedPL | null;
  loading: boolean;
};

function RealisedPLSectionInner({ data, loading }: Props) {
  const { t } = useTranslation();
  // Every figure from this endpoint is EUR; fmtCurrency converts to the
  // member's display currency. Passing a per-sale code here would print a
  // converted amount under the wrong symbol.
  const { settings } = useSettings();
  const { colors } = useAppTheme();

  // Empty is NOT loading (docs/ui-playbook.md). While the fetch is in flight
  // render nothing rather than a skeleton the member cannot distinguish from
  // "you have never sold anything".
  if (loading || !data) return null;

  const hasSales = data.count > 0;
  const excluded = data.sales_without_cost_basis + data.sales_without_shipping;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardHeader}>
        <Ionicons name="cash-outline" size={18} color={colors.accent} />
        <Text style={[styles.cardTitle, { color: colors.text }]}>
          {t('analytics.realised_pl', { defaultValue: 'Realised P/L' })}
        </Text>
      </View>

      {!hasSales ? (
        <Text style={[styles.empty, { color: colors.muted }]}>
          {t('analytics.realised_pl_empty', {
            defaultValue:
              'Nothing sold yet. Record a sale and this shows what you actually made — purchase price and fees included, not an estimate.',
          })}
        </Text>
      ) : (
        <>
          <View style={styles.totals}>
            <View style={styles.total}>
              <Text style={[styles.totalLabel, { color: colors.muted }]}>
                {t('analytics.realised_profit', { defaultValue: 'Profit' })}
              </Text>
              <Text
                style={[
                  styles.totalValue,
                  { color: data.total_profit >= 0 ? colors.success : colors.danger },
                ]}
              >
                {fmtCurrency(data.total_profit, settings, { cents: true })}
              </Text>
            </View>
            <View style={styles.total}>
              <Text style={[styles.totalLabel, { color: colors.muted }]}>
                {t('analytics.net_proceeds', { defaultValue: 'Net proceeds' })}
              </Text>
              <Text style={[styles.totalValue, { color: colors.text }]}>
                {fmtCurrency(data.total_net_proceeds, settings, { cents: true })}
              </Text>
            </View>
          </View>

          {/* The excluded population, stated rather than folded in. Same rule
              the Positions card follows for items with no purchase price. */}
          {excluded > 0 ? (
            <Text style={[styles.caveat, { color: colors.muted }]}>
              {data.sales_without_cost_basis > 0
                ? t('analytics.sales_without_basis', {
                    defaultValue: '{{count}} sale(s) excluded — no purchase price recorded',
                    count: data.sales_without_cost_basis,
                  })
                : ''}
              {data.sales_without_cost_basis > 0 && data.sales_without_shipping > 0 ? ' · ' : ''}
              {data.sales_without_shipping > 0
                ? t('analytics.sales_without_postage', {
                    defaultValue: '{{count}} sale(s) excluded — postage not recorded',
                    count: data.sales_without_shipping,
                  })
                : ''}
            </Text>
          ) : null}

          {data.sales.slice(0, 8).map((s, idx) => {
            const known = s.cost_basis_known && s.shipping_known;
            return (
              <View
                key={s.id}
                style={[styles.row, { borderTopColor: colors.border }, idx === 0 && styles.rowFirst]}
              >
                <View style={styles.rowLeft}>
                  <Text style={[styles.rowName, { color: colors.text }]} numberOfLines={1}>
                    {s.item_name ?? t('common.unknown_item', { defaultValue: 'Unknown item' })}
                  </Text>
                  <Text style={[styles.rowSub, { color: colors.muted }]} numberOfLines={1}>
                    {s.net_proceeds != null ? fmtCurrency(s.net_proceeds, settings, { cents: true }) : '—'}
                    {!known
                      ? ` · ${
                          !s.cost_basis_known
                            ? t('analytics.basis_unknown', { defaultValue: 'no purchase price' })
                            : t('analytics.postage_unknown', { defaultValue: 'postage not recorded' })
                        }`
                      : ''}
                  </Text>
                </View>
                <Text
                  style={[
                    styles.rowValue,
                    {
                      color: !known
                        ? colors.muted
                        : (s.profit ?? 0) >= 0
                          ? colors.success
                          : colors.danger,
                    },
                  ]}
                >
                  {known && s.profit != null ? fmtCurrency(s.profit, settings, { cents: true }) : '—'}
                </Text>
              </View>
            );
          })}
        </>
      )}
    </View>
  );
}

// Type scale per docs/ui-playbook.md: `xs` (10pt) is banned for anything a
// member reads, the floor is `sm`, and the hierarchy is built by pushing the
// LEAD up rather than everything else down. Sizes match this screen's own
// cards (cardTitle `lg`, posName `md`, posBasis `sm`) so the section does not
// read as a different app — the mistake `app/offers.tsx` was reported for
// twice, first for being too small and then for being uniformly bumped flat.
const styles = StyleSheet.create({
  card: { borderRadius: radius.lg, borderWidth: 1, padding: 16, marginBottom: 12 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  cardTitle: { fontSize: text.lg, fontWeight: fontWeight.bold },
  empty: { fontSize: text.md, lineHeight: 21 },
  totals: { flexDirection: 'row', gap: 24, marginBottom: 10 },
  total: { flex: 1 },
  totalLabel: { fontSize: text.sm, marginBottom: 2 },
  // The amount leads — it is the one number this whole feature exists to state.
  totalValue: { fontSize: text.xl, fontWeight: fontWeight.bold },
  caveat: { fontSize: text.sm, lineHeight: 18, marginBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, paddingVertical: 10, gap: 12 },
  rowFirst: { marginTop: 4 },
  rowLeft: { flex: 1 },
  rowName: { fontSize: text.md, fontWeight: fontWeight.semibold },
  rowSub: { fontSize: text.sm, lineHeight: 17, marginTop: 2 },
  rowValue: { fontSize: text.md, fontWeight: fontWeight.bold },
});

export const RealisedPLSection = React.memo(RealisedPLSectionInner);
export default RealisedPLSection;
