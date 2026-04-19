/**
 * LockedPreviewSection — renders a realistic mock preview of a paid feature
 * with a lock overlay + upgrade CTA. Lets free-tier users preview the actual
 * content layout (not just silhouettes) so they know what they'd unlock.
 *
 * Added 2026-04-18, enhanced 2026-04-19 when the items tab moved history /
 * price-trend / valuation report / marketplace listings behind Pro paywall.
 */

import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { router, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import Svg, { Path, Line, Circle } from 'react-native-svg';
import { useAppTheme } from '@/hooks/useAppTheme';

type PreviewType = 'chart' | 'list' | 'report' | 'history';

type Props = {
  title: string;
  subtitle?: string;
  previewType: PreviewType;
  requiredPlan?: string;
};

export const LockedPreviewSection = React.memo(function LockedPreviewSection({
  title,
  subtitle,
  previewType,
  requiredPlan = 'Pro',
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: colors.card, borderColor: colors.border },
      ]}
    >
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors.text }]}>{title}</Text>
        <View style={[styles.badge, { backgroundColor: colors.warning + '20' }]}>
          <Ionicons name="lock-closed" size={11} color={colors.warning} />
          <Text style={[styles.badgeText, { color: colors.warning }]}>{requiredPlan}</Text>
        </View>
      </View>

      {/* Mock preview — dimmed so it reads as "locked" but still shows the UX */}
      <View style={styles.previewWrap} pointerEvents="none">
        {previewType === 'chart' && <MockChartPreview colors={colors} />}
        {previewType === 'list' && <MockMarketListPreview colors={colors} />}
        {previewType === 'history' && <MockHistoryPreview colors={colors} />}
        {previewType === 'report' && <MockReportPreview colors={colors} />}
      </View>

      <View style={[styles.overlayFooter, { borderTopColor: colors.border }]}>
        <Text style={[styles.subtitle, { color: colors.muted }]}>
          {subtitle ?? `Unlock ${title.toLowerCase()} with ${requiredPlan}.`}
        </Text>
        <Pressable
          onPress={() => router.push('/subscription' as Href)}
          style={[styles.cta, { backgroundColor: colors.accent }]}
          accessibilityRole="button"
          accessibilityLabel={`Upgrade to ${requiredPlan} to unlock ${title}`}
        >
          <Text style={[styles.ctaText, { color: colors.accentText }]}>
            Upgrade to {requiredPlan}
          </Text>
        </Pressable>
      </View>
    </View>
  );
});

// ─── Mock previews ────────────────────────────────────────────────────────

const MockChartPreview: React.FC<{ colors: ReturnType<typeof useAppTheme>['colors'] }> = ({ colors }) => {
  // Simulated price trend with q10-q90 confidence band
  const width = 260;
  const height = 100;
  const points = [0.42, 0.48, 0.45, 0.52, 0.58, 0.55, 0.62, 0.68, 0.65, 0.72, 0.75, 0.78];
  const toY = (v: number) => height - (v * height * 0.75) - 8;
  const step = width / (points.length - 1);
  const linePath = points.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i * step} ${toY(v)}`).join(' ');
  const bandTop = points.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i * step} ${toY(v + 0.08)}`).join(' ');
  const bandBot = points.slice().reverse().map((v, i) => `L ${(points.length - 1 - i) * step} ${toY(v - 0.08)}`).join(' ');
  return (
    <View style={{ opacity: 0.6 }}>
      <View style={mockChartStyles.labelRow}>
        <Text style={[mockChartStyles.axisLabel, { color: colors.muted }]}>€85</Text>
        <Text style={[mockChartStyles.axisLabel, { color: colors.muted }]}>€65</Text>
        <Text style={[mockChartStyles.axisLabel, { color: colors.muted }]}>€45</Text>
      </View>
      <Svg width={width} height={height} style={{ alignSelf: 'center' }}>
        {/* confidence band */}
        <Path d={`${bandTop} ${bandBot} Z`} fill={colors.accent + '25'} />
        {/* median line */}
        <Path d={linePath} stroke={colors.accent} strokeWidth={2.5} fill="none" />
        {/* endpoint dot */}
        <Circle cx={(points.length - 1) * step} cy={toY(points[points.length - 1])} r={4} fill={colors.accent} />
      </Svg>
      <View style={mockChartStyles.xAxis}>
        <Text style={[mockChartStyles.axisLabel, { color: colors.muted }]}>Jan</Text>
        <Text style={[mockChartStyles.axisLabel, { color: colors.muted }]}>Apr</Text>
        <Text style={[mockChartStyles.axisLabel, { color: colors.muted }]}>Jul</Text>
        <Text style={[mockChartStyles.axisLabel, { color: colors.muted }]}>Oct</Text>
      </View>
    </View>
  );
};

const MockMarketListPreview: React.FC<{ colors: ReturnType<typeof useAppTheme>['colors'] }> = ({ colors }) => {
  const samples = [
    { provider: 'eBay', title: 'Charizard VMAX PSA 10', price: '€218', cond: 'PSA 10' },
    { provider: 'Mercari', title: 'Charizard VMAX (Holo)', price: '€184', cond: 'Near Mint' },
    { provider: 'Vinted', title: 'Pokemon Charizard VMAX 20/185', price: '€165', cond: 'Excellent' },
  ];
  return (
    <View style={{ opacity: 0.55 }}>
      {samples.map((s, i) => (
        <View key={i} style={[mockListStyles.row, { borderTopColor: colors.border }, i === 0 && { borderTopWidth: 0 }]}>
          <View style={mockListStyles.left}>
            <View style={[mockListStyles.providerPill, { backgroundColor: colors.border + '66' }]}>
              <Text style={[mockListStyles.providerText, { color: colors.muted }]}>{s.provider}</Text>
            </View>
            <Text style={[mockListStyles.title, { color: colors.text }]} numberOfLines={1}>{s.title}</Text>
          </View>
          <View style={mockListStyles.right}>
            <Text style={[mockListStyles.price, { color: colors.accent }]}>{s.price}</Text>
            <Text style={[mockListStyles.cond, { color: colors.muted }]}>{s.cond}</Text>
          </View>
        </View>
      ))}
    </View>
  );
};

const MockHistoryPreview: React.FC<{ colors: ReturnType<typeof useAppTheme>['colors'] }> = ({ colors }) => {
  const events = [
    { icon: 'shield-checkmark' as const, title: 'Authenticity verified', meta: 'PSA Grading • 2024-08' },
    { icon: 'receipt' as const, title: 'Sold at auction', meta: 'Heritage Auctions • €185' },
    { icon: 'cube' as const, title: 'First appearance', meta: 'Pokemon Center Japan • 2020' },
  ];
  return (
    <View style={{ opacity: 0.55, gap: 10 }}>
      {events.map((e, i) => (
        <View key={i} style={mockHistoryStyles.row}>
          <View style={[mockHistoryStyles.iconWrap, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name={e.icon} size={14} color={colors.accent} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[mockHistoryStyles.title, { color: colors.text }]}>{e.title}</Text>
            <Text style={[mockHistoryStyles.meta, { color: colors.muted }]}>{e.meta}</Text>
          </View>
        </View>
      ))}
    </View>
  );
};

const MockReportPreview: React.FC<{ colors: ReturnType<typeof useAppTheme>['colors'] }> = ({ colors }) => {
  return (
    <View style={{ opacity: 0.55 }}>
      <View style={mockReportStyles.metricRow}>
        <View style={[mockReportStyles.metric, { backgroundColor: colors.background }]}>
          <Text style={[mockReportStyles.label, { color: colors.muted }]}>FAIR VALUE</Text>
          <Text style={[mockReportStyles.value, { color: colors.text }]}>€72</Text>
        </View>
        <View style={[mockReportStyles.metric, { backgroundColor: colors.background }]}>
          <Text style={[mockReportStyles.label, { color: colors.muted }]}>CONFIDENCE</Text>
          <Text style={[mockReportStyles.value, { color: colors.success }]}>94%</Text>
        </View>
        <View style={[mockReportStyles.metric, { backgroundColor: colors.background }]}>
          <Text style={[mockReportStyles.label, { color: colors.muted }]}>COMPS</Text>
          <Text style={[mockReportStyles.value, { color: colors.text }]}>42</Text>
        </View>
      </View>
      <View style={{ marginTop: 8, gap: 4 }}>
        <Text style={[mockReportStyles.bullet, { color: colors.text }]}>• 30-day range: €65 – €82</Text>
        <Text style={[mockReportStyles.bullet, { color: colors.text }]}>• Top marketplace: eBay (63% of comps)</Text>
        <Text style={[mockReportStyles.bullet, { color: colors.text }]}>• Trend: +12% over last 30 days</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  title: { fontSize: 15, fontWeight: '700' },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  badgeText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.3 },
  previewWrap: { paddingHorizontal: 14, paddingBottom: 12 },
  overlayFooter: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderTopWidth: 1,
  },
  subtitle: { fontSize: 12, marginBottom: 8 },
  cta: {
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: 'center',
  },
  ctaText: { fontSize: 13, fontWeight: '700' },
});

const mockChartStyles = StyleSheet.create({
  labelRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  xAxis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  axisLabel: { fontSize: 10, fontWeight: '600' },
});

const mockListStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  left: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  right: { alignItems: 'flex-end' },
  providerPill: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  providerText: { fontSize: 9, fontWeight: '700' },
  title: { fontSize: 12, fontWeight: '600', flex: 1 },
  price: { fontSize: 13, fontWeight: '800' },
  cond: { fontSize: 10, marginTop: 1 },
});

const mockHistoryStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  iconWrap: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 12, fontWeight: '600' },
  meta: { fontSize: 10, marginTop: 1 },
});

const mockReportStyles = StyleSheet.create({
  metricRow: { flexDirection: 'row', gap: 6 },
  metric: { flex: 1, padding: 8, borderRadius: 8, alignItems: 'center' },
  label: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5, marginBottom: 3 },
  value: { fontSize: 15, fontWeight: '800' },
  bullet: { fontSize: 11 },
});
