/**
 * UserAchievementsSection — badges grid + active challenges display.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import type { Achievement } from '@/lib/achievements';

// ─────────────────────────────────────────────────────────────────────────────
// SectionCard (local helper)
// ─────────────────────────────────────────────────────────────────────────────
const SectionCard = React.memo(function SectionCard({ title, icon, children }: {
  title: string;
  icon?: keyof typeof Ionicons.glyphMap;
  children: React.ReactNode;
}) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.sectionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.sectionHeader}>
        {icon && <Ionicons name={icon} size={16} color={colors.accent} />}
        <Text style={[styles.sectionTitle, { color: colors.muted }]}>{title}</Text>
      </View>
      {children}
    </View>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// BadgeItem
// ─────────────────────────────────────────────────────────────────────────────
const BadgeItem = React.memo(function BadgeItem({ achievement, earned, isRecent }: {
  achievement: Achievement;
  earned: boolean;
  isRecent?: boolean;
}) {
  const { colors } = useAppTheme();
  const tierColor = colors.tier[achievement.tier];

  return (
    <View style={[styles.badgeItem, { opacity: earned ? 1 : 0.4 }]}>
      <View style={[styles.badgeIcon, { backgroundColor: earned ? tierColor + '20' : colors.border + '40' }]}>
        <Ionicons
          name={achievement.icon as keyof typeof Ionicons.glyphMap}
          size={20}
          color={earned ? tierColor : colors.muted}
        />
        {isRecent && (
          <View style={[styles.newBadgeDot, { backgroundColor: colors.accent }]}>
            <Text style={[styles.newBadgeText, { color: colors.accentText }]}>!</Text>
          </View>
        )}
      </View>
      <Text
        style={[styles.badgeLabel, { color: earned ? colors.text : colors.muted }]}
        numberOfLines={1}
      >
        {achievement.title}
      </Text>
    </View>
  );
});

// ─────────────────────────────────────────────────────────────────────────────
// Props
// ─────────────────────────────────────────────────────────────────────────────
export interface ProfileBadge extends Achievement {
  earned: boolean;
}

interface ChallengeEntry {
  id: string;
  title: string;
  progress: number;
  target: number;
  reward_xp: number;
}

interface UserAchievementsSectionProps {
  profileBadges: ProfileBadge[];
  recentAchievementIds: Set<string>;
  challenges: ChallengeEntry[];
}

export const UserAchievementsSection = React.memo(function UserAchievementsSection({
  profileBadges,
  recentAchievementIds,
  challenges,
}: UserAchievementsSectionProps) {
  const { colors } = useAppTheme();

  return (
    <>
      {/* Badges */}
      {profileBadges.length > 0 && (
        <SectionCard title="Badges" icon="ribbon-outline">
          <View style={styles.badgesGrid}>
            {profileBadges.map((badge) => (
              <BadgeItem
                key={badge.id}
                achievement={badge}
                earned={badge.earned}
                isRecent={recentAchievementIds.has(badge.id)}
              />
            ))}
          </View>
        </SectionCard>
      )}

      {/* Active Challenges */}
      {challenges.length > 0 && (
        <SectionCard title="Active Challenges" icon="trophy-outline">
          {challenges.slice(0, 3).map((ch) => {
            const pct = ch.target > 0 ? Math.min(ch.progress / ch.target, 1) : 0;
            return (
              <View key={ch.id} style={styles.challengeRow}>
                <View style={styles.challengeInfo}>
                  <Text style={[styles.challengeTitle, { color: colors.text }]} numberOfLines={1}>{ch.title}</Text>
                  <Text style={[styles.challengeMeta, { color: colors.muted }]}>
                    {ch.progress}/{ch.target} · +{ch.reward_xp} XP
                  </Text>
                </View>
                <View style={[styles.challengeBar, { backgroundColor: colors.border }]}>
                  <View style={[styles.challengeBarFill, { width: `${Math.round(pct * 100)}%`, backgroundColor: colors.accent }]} />
                </View>
              </View>
            );
          })}
        </SectionCard>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  // Section card
  sectionCard: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 16,
    marginTop: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: textToken.sm,
    fontWeight: fw.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },

  // Badges
  badgesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  badgeItem: {
    alignItems: 'center',
    width: 72,
  },
  badgeIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  badgeLabel: {
    fontSize: textToken.xs,
    fontWeight: fw.semibold,
    textAlign: 'center',
  },
  newBadgeDot: {
    position: 'absolute',
    top: -2,
    right: -2,
    width: 14,
    height: 14,
    borderRadius: 7,
    alignItems: 'center',
    justifyContent: 'center',
  },
  newBadgeText: {
    fontSize: textToken.xs,
    fontWeight: fw.extrabold,
  },

  // Challenges
  challengeRow: {
    marginBottom: 12,
  },
  challengeInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  challengeTitle: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,
    flex: 1,
  },
  challengeMeta: {
    fontSize: textToken.xs,
    marginLeft: 8,
  },
  challengeBar: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  challengeBarFill: {
    height: 6,
    borderRadius: 3,
  },
});
