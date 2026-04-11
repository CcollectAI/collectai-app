/**
 * AutoSetProgressList — displays auto-detected set completion using
 * the ProgressRing component.
 *
 * Pulls from useAutoSetProgress (which uses structured attributes_json).
 * Shows nothing when the user has no qualifying sets.
 */

import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';
import { ProgressRing } from '@/components/ProgressRing';
import { useAutoSetProgress } from '@/hooks/useAutoSetProgress';

interface AutoSetProgressListProps {
  /** Optional category filter */
  category?: string;
  /** Maximum number of sets to display */
  limit?: number;
}

export function AutoSetProgressList({ category, limit = 5 }: AutoSetProgressListProps) {
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const { sets, loading, error } = useAutoSetProgress(category);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }

  if (error || sets.length === 0) {
    return null; // hide gracefully
  }

  const displaySets = sets.slice(0, limit);

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors.text }]}>{t('set_completion.title')}</Text>
        <Text style={[styles.subtitle, { color: colors.muted }]}>
          {t('home.sets_in_progress', { count: sets.length })}
        </Text>
      </View>

      {displaySets.map((set) => {
        const fillColor = set.completionPct >= 80 ? '#0BA86C' : colors.accent;
        return (
          <View key={`${set.category}-${set.setName}`} style={styles.row}>
            <ProgressRing
              progress={set.completionPct / 100}
              size={48}
              strokeWidth={5}
              progressColor={fillColor}
            />
            <View style={styles.rowText}>
              <Text style={[styles.setName, { color: colors.text }]} numberOfLines={1}>
                {set.setName}
              </Text>
              <Text style={[styles.setMeta, { color: colors.muted }]}>
                {set.ownedCount}/{set.catalogTotal} • {Math.round(set.completionPct)}%
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginVertical: 8,
  },
  loadingContainer: {
    paddingVertical: 12,
    alignItems: 'center',
  },
  header: {
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
  },
  rowText: {
    flex: 1,
  },
  setName: {
    fontSize: 14,
    fontWeight: '600',
  },
  setMeta: {
    fontSize: 12,
    marginTop: 2,
  },
});
