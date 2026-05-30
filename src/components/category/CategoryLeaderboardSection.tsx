/**
 * CategoryLeaderboardSection — auto-rotating carousel of top collectors.
 * Fetches from gamification leaderboard with category filter.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AutoRotatingCarousel } from '@/components/AutoRotatingCarousel';
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
  // Kept on the type so call sites don't break, but the server leaderboard
  // doesn't accept a category filter — only period (weekly/monthly/alltime).
  categoryId: string;
};

export default React.memo(function CategoryLeaderboardSection({ categoryId: _categoryId }: Props) {
  const { colors } = useAppTheme();
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    collectorsApi.getLeaderboard('weekly')
      .then((data) => {
        if (cancelled) return;
        const rows = data?.leaderboard ?? [];
        setEntries(
          rows.slice(0, 5).map((r) => ({
            user_id: r.user_id,
            display_name: r.display_name ?? `Collector ${r.rank}`,
            xp: r.total_xp,
            level: r.level,
            rank: r.rank,
          })),
        );
      })
      .catch((err) => logger.warn('[CategoryLeaderboard] fetch failed:', err));
    return () => { cancelled = true; };
  }, []);

  if (entries.length === 0) return null;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="podium-outline" size={18} color={colors.accent} />
        <Text style={[styles.title, { color: colors.text }]}>Top Collectors</Text>
      </View>

      <AutoRotatingCarousel intervalMs={5500} horizontalInset={30}>
        {entries.map((entry, idx) => {
          const medalColor = idx < 3 ? [MEDAL_COLORS.gold, MEDAL_COLORS.silver, MEDAL_COLORS.bronze][idx] : null;
          return (
            <View
              key={entry.user_id}
              style={[styles.card, { backgroundColor: colors.background, borderColor: colors.border }]}
              accessibilityLabel={`Rank ${idx + 1}: ${entry.display_name}, Level ${entry.level}, ${entry.xp} XP`}
            >
              <View style={styles.rankWrap}>
                {medalColor ? (
                  <Ionicons name="medal" size={36} color={medalColor} />
                ) : (
                  <Text style={[styles.rankBig, { color: colors.muted }]}>#{idx + 1}</Text>
                )}
              </View>
              <View style={styles.info}>
                <Text style={[styles.name, { color: colors.text }]} numberOfLines={1}>
                  {entry.display_name}
                </Text>
                <Text style={[styles.meta, { color: colors.muted }]}>
                  Level {entry.level} · {entry.xp.toLocaleString()} XP
                </Text>
              </View>
            </View>
          );
        })}
      </AutoRotatingCarousel>
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
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 4,
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 16,
    paddingHorizontal: 18,
    gap: 16,
    minHeight: 90,
  },
  rankWrap: {
    width: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankBig: {
    fontSize: 22,
    fontWeight: '800',
  },
  info: {
    flex: 1,
  },
  name: {
    fontSize: 18,
    fontWeight: '700',
  },
  meta: {
    fontSize: 13,
    marginTop: 4,
  },
});
