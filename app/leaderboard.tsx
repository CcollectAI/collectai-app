import React, { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { View, Text, ScrollView, StyleSheet, Animated, RefreshControl, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, Stack } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { USER_PROFILES } from '@/data/users';
import { collectorsApi } from '@/api/collectorsApi';
import { AnimatedPressable, useEnterReveal, useStaggerReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import logger from '@/utils/logger';
import { MEDAL_COLORS, TWITCH_PURPLE } from '@/constants/colors';
import { BETA_MODE, COMMUNITY_GATED } from '@/config/featureFlags';

const AvatarCircle = React.memo<{ name: string; color: string }>(({ name, color }) => {
  const initials =
    name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?';
  return (
    <View style={[styles.avatar, { backgroundColor: color }]}>
      <Text style={styles.avatarText}>{initials}</Text>
    </View>
  );
});

function getMedalColor(index: number, fallback: string): string {
  if (index === 0) return MEDAL_COLORS.gold;
  if (index === 1) return MEDAL_COLORS.silver;
  if (index === 2) return MEDAL_COLORS.bronze;
  return fallback;
}

const LeaderboardScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [apiEntries, setApiEntries] = useState<{
    rank: number;
    user_id: string;
    display_name: string;
    xp: number;
    level: number;
    avatar_url: string | null;
  }[] | null>(null);

  const loadLeaderboardRef = useRef<{ cancelled: boolean }>({ cancelled: false });

  const loadLeaderboard = useCallback(async () => {
    const guard = loadLeaderboardRef.current;
    try {
      const data = await collectorsApi.getLeaderboard();
      if (guard.cancelled) return;
      // gamification_router returns {leaderboard:[...], period, user_rank, total_count}.
      // Each entry has total_xp / level / current_streak (no `xp` field).
      if (data?.leaderboard?.length) {
        setApiEntries(
          data.leaderboard.map((r) => ({
            rank: r.rank,
            user_id: r.user_id,
            display_name: r.display_name ?? `Collector ${r.rank}`,
            xp: r.total_xp,
            level: r.level,
            avatar_url: r.avatar_url,
          })),
        );
      }
    } catch (err) {
      if (guard.cancelled) return;
      logger.error('[Leaderboard] API fetch failed, using local fallback:', err);
    } finally {
      if (!guard.cancelled) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const guard = { cancelled: false };
    loadLeaderboardRef.current = guard;
    loadLeaderboard();
    return () => {
      guard.cancelled = true;
    };
  }, [loadLeaderboard]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadLeaderboard();
    setRefreshing(false);
  }, [loadLeaderboard]);

  // Use API data if available, fall back to local USER_PROFILES
  const rankedUsers = useMemo(() => {
    if (apiEntries?.length) {
      return apiEntries.map((entry, i) => ({
        id: entry.user_id,
        displayName: entry.display_name,
        handle: entry.display_name.toLowerCase().replace(/\s+/g, ''),
        avatarColor: colors.accent,
        stats: {
          totalEstimatedValueEur: entry.xp,
          totalItems: entry.level,
          totalCategories: 0,
          rarityScore: entry.level,
        },
      }));
    }
    return [...USER_PROFILES].sort(
      (a, b) => b.stats.totalEstimatedValueEur - a.stats.totalEstimatedValueEur,
    );
  }, [apiEntries, colors.accent]);

  const { getItemStyle } = useStaggerReveal({
    count: rankedUsers.length,
    staggerMs: 60,
    enabled: settings.animationsEnabled,
  });

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Leaderboard' }} />
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>

        {/* Twitch Creators link — gated until twitch_creators table is populated */}
        {!BETA_MODE && !COMMUNITY_GATED && (
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push('/twitch-leaderboard');
            }}
            style={[styles.twitchLink, { backgroundColor: colors.card, borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="View Twitch creators leaderboard"
          >
            <Ionicons name="logo-twitch" size={18} color={TWITCH_PURPLE} />
            <Text style={[styles.twitchLinkText, { color: colors.text }]}>Twitch Creators</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.muted} />
          </AnimatedPressable>
        )}

        {/* Leaderboard list */}
        {rankedUsers.map((user, index) => {
          const medalColor = getMedalColor(index, colors.muted);
          const staggerStyle = getItemStyle(index);
          return (
            <Animated.View key={user.id} style={staggerStyle}>
            <AnimatedPressable
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.push(`/users/${encodeURIComponent(user.id)}`); }}
              style={[
                styles.card,
                { borderColor: colors.border, backgroundColor: colors.card },
              ]}
              accessibilityRole="button"
              accessibilityLabel={`Rank ${index + 1}, ${user.displayName}, ${formatPrice(user.stats.totalEstimatedValueEur)}, ${user.stats.totalItems} ${user.stats.totalItems === 1 ? 'item' : 'items'}`}
              accessibilityHint="Double tap to view collector profile"
            >
              {/* Rank */}
              <View style={styles.rankCol}>
                <Text style={[styles.rankText, { color: medalColor }]}>
                  #{index + 1}
                </Text>
                {index < 3 && (
                  <Ionicons name="trophy-outline" size={14} color={medalColor} />
                )}
              </View>

              {/* Avatar + main info */}
              <AvatarCircle name={user.displayName} color={user.avatarColor} />
              <View style={styles.infoCol}>
                <Text style={[styles.userName, { color: colors.text }]}>
                  {user.displayName}
                </Text>
                <Text style={[styles.userHandle, { color: colors.muted }]}>
                  @{user.handle}
                </Text>
                <Text style={[styles.userMeta, { color: colors.muted }]} numberOfLines={1}>
                  {user.stats.totalItems} {user.stats.totalItems === 1 ? 'item' : 'items'} · {user.stats.totalCategories} {user.stats.totalCategories === 1 ? 'category' : 'categories'}
                </Text>
              </View>

              {/* Value + key score */}
              <View style={styles.valueCol}>
                <Text style={[styles.valueText, { color: colors.text }]}>
                  {formatPrice(user.stats.totalEstimatedValueEur)}
                </Text>
                <Text style={[styles.rarityText, { color: colors.muted }]}>
                  Rarity {user.stats.rarityScore}
                </Text>
              </View>
            </AnimatedPressable>
            </Animated.View>
          );
        })}
        </Animated.View>
      </ScrollView>
      <QuickNavBar />
    </View>
  );
};

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  scrollContent: {
    paddingTop: 8,
    paddingBottom: 32,
    paddingHorizontal: 16,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    gap: 8,
  },
  backBtn: {
    padding: 4,
  },
  headerText: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
  },
  headerSubtitle: {
    marginTop: 2,
    fontSize: 12,
  },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 10,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  rankCol: {
    width: 30,
    alignItems: 'center',
    marginRight: 8,
  },
  rankText: {
    fontSize: 14,
    fontWeight: '700',
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
  infoCol: {
    marginLeft: 10,
    flex: 1,
  },
  userName: {
    fontSize: 14,
    fontWeight: '600',
  },
  userHandle: {
    fontSize: 11,
  },
  userMeta: {
    marginTop: 2,
    fontSize: 11,
  },
  valueCol: {
    alignItems: 'flex-end',
  },
  valueText: {
    fontSize: 13,
    fontWeight: '700',
  },
  rarityText: {
    marginTop: 2,
    fontSize: 11,
  },
  twitchLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 14,
    borderRadius: 14,
    borderWidth: 1,
    marginBottom: 16,
  },
  twitchLinkText: {
    flex: 1,
    fontSize: 15,
    fontWeight: '600',
  },
});

export default function LeaderboardScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Leaderboard">
      <LeaderboardScreen />
    </ScreenErrorBoundary>
  );
}
