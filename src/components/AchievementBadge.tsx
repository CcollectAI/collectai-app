/**
 * AchievementBadge - Displays a single achievement with progress.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Achievement, getTierColor, formatTier } from '@/lib/achievements';

interface Props {
  achievement: Achievement & { earned: boolean; earnedAt?: string };
  stats?: { current: number; target: number };
  size?: 'small' | 'medium' | 'large';
  colors: {
    card: string;
    text: string;
    muted: string;
    border: string;
  };
}

export function AchievementBadge({
  achievement,
  stats,
  size = 'medium',
  colors,
}: Props) {
  const tierColor = getTierColor(achievement.tier);
  const isEarned = achievement.earned;

  const iconSize = size === 'small' ? 20 : size === 'large' ? 32 : 24;
  const badgeSize = size === 'small' ? 44 : size === 'large' ? 72 : 56;

  const progressPercent = stats
    ? Math.min(100, Math.round((stats.current / stats.target) * 100))
    : isEarned
    ? 100
    : 0;

  return (
    <View style={[styles.container, { backgroundColor: colors.card }]}>
      {/* Badge icon */}
      <View
        style={[
          styles.badge,
          {
            width: badgeSize,
            height: badgeSize,
            borderRadius: badgeSize / 2,
            backgroundColor: isEarned ? tierColor + '30' : colors.border,
            borderColor: isEarned ? tierColor : colors.border,
          },
        ]}
      >
        <Ionicons
          name={achievement.icon as any}
          size={iconSize}
          color={isEarned ? tierColor : colors.muted}
        />
      </View>

      {/* Info */}
      <View style={styles.info}>
        <View style={styles.titleRow}>
          <Text
            style={[
              styles.title,
              { color: isEarned ? colors.text : colors.muted },
              size === 'small' && styles.titleSmall,
            ]}
            numberOfLines={1}
          >
            {achievement.title}
          </Text>
          {isEarned && (
            <View style={[styles.earnedBadge, { backgroundColor: tierColor }]}>
              <Text style={styles.earnedText}>{formatTier(achievement.tier)}</Text>
            </View>
          )}
        </View>

        <Text
          style={[
            styles.description,
            { color: colors.muted },
            size === 'small' && styles.descriptionSmall,
          ]}
          numberOfLines={size === 'small' ? 1 : 2}
        >
          {achievement.description}
        </Text>

        {/* Progress bar (if not earned and has progress) */}
        {!isEarned && stats && (
          <View style={styles.progressContainer}>
            <View style={[styles.progressBar, { backgroundColor: colors.border }]}>
              <View
                style={[
                  styles.progressFill,
                  {
                    width: `${progressPercent}%`,
                    backgroundColor: tierColor,
                  },
                ]}
              />
            </View>
            <Text style={[styles.progressText, { color: colors.muted }]}>
              {stats.current}/{stats.target}
            </Text>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: 12,
    gap: 12,
  },
  badge: {
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  info: {
    flex: 1,
    justifyContent: 'center',
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  title: {
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  titleSmall: {
    fontSize: 12,
  },
  earnedBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  earnedText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  description: {
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },
  descriptionSmall: {
    fontSize: 11,
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 8,
  },
  progressBar: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 3,
  },
  progressText: {
    fontSize: 11,
    fontWeight: '500',
    minWidth: 40,
    textAlign: 'right',
  },
});

export default AchievementBadge;
