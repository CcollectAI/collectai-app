/**
 * UserStatsSection — quick stats row (items, value, level/categories) + streak badge.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import type { PublicUserProfile } from '@/data';

interface UserStatsSectionProps {
  profile: PublicUserProfile;
  gamProfile: { xp: number; level: number; streak_days: number } | null;
}

export const UserStatsSection = React.memo(function UserStatsSection({
  profile,
  gamProfile,
}: UserStatsSectionProps) {
  const { colors } = useAppTheme();

  return (
    <>
      {/* Quick stats row */}
      <View style={[styles.quickStatsRow, { backgroundColor: colors.background, borderColor: colors.border }]}>
        <View style={styles.quickStat}>
          <Text style={[styles.quickStatValue, { color: colors.text }]}>{profile.collectionCount ?? 0}</Text>
          <Text style={[styles.quickStatLabel, { color: colors.muted }]}>Items</Text>
        </View>
        <View style={[styles.quickStatDivider, { backgroundColor: colors.border }]} />
        <View style={styles.quickStat}>
          <Text style={[styles.quickStatValue, { color: colors.text }]}>
            {profile.collectionValueEur ? `\u20AC${Math.round(profile.collectionValueEur / 1000)}k` : '\u2014'}
          </Text>
          <Text style={[styles.quickStatLabel, { color: colors.muted }]}>Value</Text>
        </View>
        <View style={[styles.quickStatDivider, { backgroundColor: colors.border }]} />
        {gamProfile ? (
          <View style={styles.quickStat}>
            <Text style={[styles.quickStatValue, { color: colors.text }]}>Lv.{gamProfile.level}</Text>
            <Text style={[styles.quickStatLabel, { color: colors.muted }]}>{gamProfile.xp} XP</Text>
          </View>
        ) : (
          <View style={styles.quickStat}>
            <Text style={[styles.quickStatValue, { color: colors.text }]}>{profile.interests?.length ?? 0}</Text>
            <Text style={[styles.quickStatLabel, { color: colors.muted }]}>Categories</Text>
          </View>
        )}
      </View>

      {/* Streak badge */}
      {gamProfile && gamProfile.streak_days > 0 && (
        <View style={[styles.streakBadge, { backgroundColor: colors.tier.gold + '15', borderColor: colors.tier.gold + '30' }]}>
          <Ionicons name="flame-outline" size={14} color={colors.tier.gold} />
          <Text style={[styles.streakText, { color: colors.tier.gold }]}>
            {gamProfile.streak_days} day streak
          </Text>
        </View>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  quickStatsRow: {
    flexDirection: 'row',
    marginTop: 20,
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderRadius: radius.md,
    borderWidth: 1,
    width: '100%',
  },
  quickStat: {
    flex: 1,
    alignItems: 'center',
  },
  quickStatDivider: {
    width: 1,
    height: 32,
    marginHorizontal: 8,
  },
  quickStatValue: {
    fontSize: textToken.xl,
    fontWeight: fw.bold,
  },
  quickStatLabel: {
    fontSize: textToken.sm,
    marginTop: 2,
  },
  streakBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.md,
    borderWidth: 1,
    marginTop: 12,
  },
  streakText: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
  },
});
