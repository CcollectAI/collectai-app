/**
 * The catalogue item's PRO price block: 90-day range + weekly trend (2026-09-26).
 *
 * Merle's call after the teaser "Full price range & 90-day trend — Sparrow Pro"
 * was found selling nothing. Backed by GET /catalog/{cat}/items/{key}/price-range
 * (server-gated with require_plan("pro")). `locked` covers a free member AND a
 * server 403 — the client's plan read can lag the server's.
 */
import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import { PortfolioLineChart } from '@/components/PortfolioLineChart';
import type { Currency } from '@/lib/settings';

export type CatalogPriceRange = {
  p10: number | null;
  p90: number | null;
  comps_count: number;
  series: { t: string; v: number }[];
};

type Props = {
  state: 'idle' | 'loading' | 'ok' | 'failed' | 'locked';
  range: CatalogPriceRange | null;
  currency: Currency;
  fxRate: number;
  onUnlock: () => void;
};

export function CatalogPriceRangeBlock({ state, range, currency, fxRate, onUnlock }: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  if (state === 'locked') {
    return (
      <AnimatedPressable
        style={[styles.row, { borderColor: colors.border }]}
        onPress={onUnlock}
        accessibilityRole="button"
        accessibilityLabel={t('catalog.a11y_unlock_pro', { defaultValue: 'Unlock the price range and trend with Pro' })}
      >
        <Ionicons name="lock-closed" size={14} color={colors.muted} />
        <Text style={[styles.teaser, { color: colors.muted }]}>
          {t('catalog.pro_teaser', { defaultValue: 'Full price range & 90-day trend — Sparrow Pro' })}
        </Text>
        <Ionicons name="chevron-forward" size={14} color={colors.muted} />
      </AnimatedPressable>
    );
  }
  if (state === 'loading') {
    return <ActivityIndicator color={colors.accent} style={styles.spinner} />;
  }
  if (state === 'failed') {
    return (
      <Text style={[styles.sub, styles.gap, { color: colors.muted }]}>
        {t('catalog.range_failed', { defaultValue: "Couldn't load the 90-day range." })}
      </Text>
    );
  }
  if (state !== 'ok' || !range) return null;
  if (range.p10 == null || range.p90 == null) {
    return (
      <Text style={[styles.sub, styles.gap, { color: colors.muted }]}>
        {t('catalog.range_none', { defaultValue: 'No sales in the last 90 days.' })}
      </Text>
    );
  }
  return (
    <View style={[styles.block, { borderColor: colors.border }]}>
      <Text style={[styles.label, { color: colors.muted }]}>
        {t('catalog.range_label', { defaultValue: '90-day range' }).toUpperCase()}
      </Text>
      <Text style={[styles.value, { color: colors.text }]}>
        {`${formatPrice(range.p10)} – ${formatPrice(range.p90)}`}
      </Text>
      <Text style={[styles.sub, { color: colors.muted }]}>
        {t(range.comps_count === 1 ? 'catalog.range_caption_one' : 'catalog.range_caption_many', { count: range.comps_count })}
      </Text>
      {range.series.length >= 2 && (
        <PortfolioLineChart
          series={range.series}
          accentColor={colors.accent}
          showValueHeader={false}
          showAxisLabels={true}
          axisLabelColor={colors.muted}
          gridColor={colors.border}
          textColor={colors.text}
          dotFillColor={colors.card}
          currency={currency}
          fxRate={fxRate}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12, paddingTop: 12, borderTopWidth: 1 },
  teaser: { flex: 1, fontSize: 13, fontWeight: '500' },
  spinner: { marginTop: 12, alignSelf: 'flex-start' },
  gap: { marginTop: 12 },
  block: { marginTop: 12, paddingTop: 12, borderTopWidth: 1 },
  label: { fontSize: 11, fontWeight: '700', letterSpacing: 0.5 },
  value: { fontSize: 20, fontWeight: '900', marginTop: 6 },
  sub: { fontSize: 12, marginTop: 2 },
});
