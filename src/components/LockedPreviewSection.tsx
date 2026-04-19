/**
 * LockedPreviewSection — renders a skeleton silhouette of a paid feature with
 * a lock overlay + upgrade CTA. Lets free-tier users preview the layout of
 * paid sections without making real API calls.
 *
 * Added 2026-04-18 when the items tab moved history / price-trend / valuation
 * report / marketplace listings behind the Pro paywall.
 */

import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { router, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

type PreviewType = 'chart' | 'list' | 'report';

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
  const silhouette = colors.border + '80';

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

      {/* Silhouette preview — dimmed so it reads as "locked" */}
      <View style={[styles.previewWrap, { opacity: 0.45 }]} pointerEvents="none">
        {previewType === 'chart' && <ChartSilhouette color={silhouette} />}
        {previewType === 'list' && <ListSilhouette color={silhouette} />}
        {previewType === 'report' && <ReportSilhouette color={silhouette} />}
      </View>

      <Text style={[styles.subtitle, { color: colors.muted }]}>
        {subtitle ?? `Unlock ${title.toLowerCase()} with ${requiredPlan}.`}
      </Text>

      <Pressable
        onPress={() => router.push('/settings' as Href)}
        style={[styles.cta, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel={`Upgrade to ${requiredPlan} to unlock ${title}`}
      >
        <Text style={[styles.ctaText, { color: colors.accentText }]}>
          Upgrade to {requiredPlan}
        </Text>
      </Pressable>
    </View>
  );
});

const ChartSilhouette: React.FC<{ color: string }> = ({ color }) => (
  <View style={chartStyles.wrap}>
    <View style={[chartStyles.bar, { height: 28, backgroundColor: color }]} />
    <View style={[chartStyles.bar, { height: 44, backgroundColor: color }]} />
    <View style={[chartStyles.bar, { height: 22, backgroundColor: color }]} />
    <View style={[chartStyles.bar, { height: 58, backgroundColor: color }]} />
    <View style={[chartStyles.bar, { height: 36, backgroundColor: color }]} />
    <View style={[chartStyles.bar, { height: 72, backgroundColor: color }]} />
    <View style={[chartStyles.bar, { height: 50, backgroundColor: color }]} />
  </View>
);

const ListSilhouette: React.FC<{ color: string }> = ({ color }) => (
  <View style={listStyles.wrap}>
    {[0.9, 0.75, 0.6].map((w, i) => (
      <View key={i} style={listStyles.row}>
        <View style={[listStyles.dot, { backgroundColor: color }]} />
        <View style={[listStyles.line, { width: `${w * 100}%`, backgroundColor: color }]} />
      </View>
    ))}
  </View>
);

const ReportSilhouette: React.FC<{ color: string }> = ({ color }) => (
  <View style={reportStyles.wrap}>
    <View style={[reportStyles.title, { backgroundColor: color }]} />
    <View style={[reportStyles.line, { width: '90%', backgroundColor: color }]} />
    <View style={[reportStyles.line, { width: '75%', backgroundColor: color }]} />
    <View style={[reportStyles.line, { width: '82%', backgroundColor: color }]} />
  </View>
);

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
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
  previewWrap: { marginBottom: 12 },
  subtitle: { fontSize: 12, marginBottom: 10 },
  cta: {
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: 'center',
  },
  ctaText: { fontSize: 13, fontWeight: '700' },
});

const chartStyles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: 80,
    gap: 6,
  },
  bar: { flex: 1, borderRadius: 3 },
});

const listStyles = StyleSheet.create({
  wrap: { gap: 10 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  line: { height: 10, borderRadius: 5 },
});

const reportStyles = StyleSheet.create({
  wrap: { gap: 8 },
  title: { height: 14, width: '50%', borderRadius: 4 },
  line: { height: 9, borderRadius: 4 },
});
