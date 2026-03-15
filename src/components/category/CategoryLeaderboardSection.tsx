/**
 * CategoryLeaderboardSection — Top collectors for a category.
 * Fetches from gamification leaderboard with category filter.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { collectorsApi } from '@/api/collectorsApi';
import { MEDAL_COLORS } from '@/constants/colors';
import logger from '@/utils/logger';

type LeaderboardEntry = {
  user_id: string;
  display_name: string;
  xp: number;
  level: number;
  rank: number;
};

type Props = {
  categoryId: string;
};

export default React.memo(function CategoryLeaderboardSection({ categoryId }: Props) {
  const { colors } = useAppTheme();
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    collectorsApi.getLeaderboard('xp', categoryId)
      .then((data) => {
        if (cancelled) return;
        const arr = Array.isArray((data as { entries?: unknown[] })?.entries)
          ? (data as { entries: LeaderboardEntry[] }).entries
          : Array.isArray(data) ? data as LeaderboardEntry[] : [];
        setEntries(arr.slice(0, 5));
      })
      .catch((err) => logger.warn('[CategoryLeaderboard] fetch failed:', err));
    return () => { cancelled = true; };
  }, [categoryId]);

  if (entries.length === 0) return null;

  const medalColors = [MEDAL_COLORS.gold, MEDAL_COLORS.silver, MEDAL_COLORS.bronze];

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="podium-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Top Collectors</Text>
      </View>

      {entries.map((entry, idx) => (
        <View key={entry.user_id} style={[styles.row, { borderBottomColor: colors.border }]} accessibilityLabel={`Rank ${idx + 1}: ${entry.display_name || `Collector ${entry.rank}`}, Level ${entry.level}, ${entry.xp} XP`}>
          <View style={styles.rankWrap}>
            {idx < 3 ? (
              <Ionicons name="medal-outline" size={16} color={medalColors[idx]} />
            ) : (
              <Text style={[styles.rankText, { color: colors.muted }]}>{idx + 1}</Text>
            )}
          </View>
          <View style={styles.info}>
            <Text style={[styles.name, { color: colors.text }]} numberOfLines={1}>
              {entry.display_name || `Collector ${entry.rank}`}
            </Text>
            <Text style={[styles.meta, { color: colors.muted }]}>
              Level {entry.level} · {entry.xp.toLocaleString()} XP
            </Text>
          </View>
        </View>
      ))}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '700',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  rankWrap: {
    width: 28,
    alignItems: 'center',
  },
  rankText: {
    fontSize: 13,
    fontWeight: '700',
  },
  info: {
    flex: 1,
    marginLeft: 8,
  },
  name: {
    fontSize: 14,
    fontWeight: '600',
  },
  meta: {
    fontSize: 11,
    marginTop: 2,
  },
});
