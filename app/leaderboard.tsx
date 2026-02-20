import React, { useMemo } from 'react';
import { View, Text, ScrollView, StyleSheet, Animated } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { USER_PROFILES } from '@/data/users';
import { AnimatedPressable, useEnterReveal, useStaggerReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';

const MEDAL_GOLD = '#eab308';
const MEDAL_SILVER = '#9ca3af';
const MEDAL_BRONZE = '#b45309';

const AvatarCircle: React.FC<{ name: string; color: string }> = ({ name, color }) => {
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
};

function getMedalColor(index: number, fallback: string): string {
  if (index === 0) return MEDAL_GOLD;
  if (index === 1) return MEDAL_SILVER;
  if (index === 2) return MEDAL_BRONZE;
  return fallback;
}

const LeaderboardScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  const rankedUsers = useMemo(
    () =>
      [...USER_PROFILES].sort(
        (a, b) =>
          b.stats.totalEstimatedValueEur - a.stats.totalEstimatedValueEur,
      ),
    [],
  );

  const { getItemStyle } = useStaggerReveal({
    count: rankedUsers.length,
    staggerMs: 60,
    enabled: settings.animationsEnabled,
  });

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
        {/* Header */}
        <View style={styles.headerRow}>
          <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); router.back(); }} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
          <View style={styles.headerText}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Collector Leaderboard
            </Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>
              Ranked by estimated portfolio value
            </Text>
          </View>
        </View>

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
              accessibilityLabel={`Rank ${index + 1}, ${user.displayName}, ${formatPrice(user.stats.totalEstimatedValueEur)}, ${user.stats.totalItems} items`}
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
                  {user.stats.totalItems} items · {user.stats.totalCategories} categories
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
    </SafeAreaView>
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
});

export default LeaderboardScreen;
