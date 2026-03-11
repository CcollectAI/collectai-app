/**
 * SponsorKpiGrid — 4-metric KPI grid showing campaigns, reach, active, sent.
 */

import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

const SHADOW_SM = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 3 },
  android: { elevation: 1 },
  default: {},
}) as Record<string, unknown>;

interface KpiMetric {
  label: string;
  value: number;
  icon: React.ComponentProps<typeof Ionicons>['name'];
  color: string;
}

interface SponsorKpiGridProps {
  metrics: KpiMetric[];
}

export const SponsorKpiGrid = React.memo(function SponsorKpiGrid({
  metrics,
}: SponsorKpiGridProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.kpiGrid}>
      {metrics.map((metric) => (
        <View key={metric.label} style={[styles.kpiCard, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_SM]}>
          <View style={[styles.kpiIconCircle, { backgroundColor: metric.color + '12' }]}>
            <Ionicons name={metric.icon} size={16} color={metric.color} />
          </View>
          <Text style={[styles.kpiValue, { color: colors.text }]}>{metric.value}</Text>
          <Text style={[styles.kpiLabel, { color: colors.muted }]}>{metric.label}</Text>
        </View>
      ))}
    </View>
  );
});

const styles = StyleSheet.create({
  kpiGrid: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  kpiCard: { flex: 1, alignItems: 'center', borderRadius: 12, borderWidth: 1, paddingVertical: 14, paddingHorizontal: 4, gap: 6 },
  kpiIconCircle: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  kpiValue: { fontSize: 20, fontWeight: '800', letterSpacing: -0.5 },
  kpiLabel: { fontSize: 9, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
});
