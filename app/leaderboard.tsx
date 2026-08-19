import React, { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { View, Text, ScrollView, StyleSheet, Animated, RefreshControl, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, Stack, useLocalSearchParams } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { USER_PROFILES } from '@/data/users';
import { collectorsApi } from '@/api/collectorsApi';
import { getCategoryLeaderboard, type CategoryLeaderboardEntry } from '@/api/socialApi';
import { getCategoryById } from '@/data/categories';
import { AnimatedPressable, useEnterReveal, useStaggerReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings, type NumberLocale } from '@/lib/settings';
import { formatPrice, formatNumber } from '@/lib/format';
import logger from '@/utils/logger';
import { MEDAL_COLORS, TWITCH_PURPLE } from '@/constants/colors';
import { BETA_MODE, COMMUNITY_GATED } from '@/config/featureFlags';

/**
 * Category mode. `/leaderboard?categoryId=mtg` ranks the collectors of ONE
 * category; with no param the screen keeps its existing XP board.
 *
 * Ranked on real data (items owned, or value held) rather than XP, because XP
 * has no category dimension and its UI is gated off. The server drops anyone
 * who turned off "Allow discovery" or "Show item count", and the value board
 * additionally drops "Show collection value" — so a SHORT board is a correct
 * board and is never padded.
 */
function CategoryLeaderboard({ categoryId }: { categoryId: string }) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();
  const [metric, setMetric] = useState<'items' | 'value'>('items');
  // Bumping this re-runs the fetch effect. The failure copy tells people to
  // pull down, so a pull MUST actually retry — otherwise the screen promises a
  // gesture it does not implement.
  const [reloadKey, setReloadKey] = useState(0);
  const [rows, setRows] = useState<CategoryLeaderboardEntry[] | null>(null);
  const [yourRank, setYourRank] = useState<number | null>(null);
  const [totalRanked, setTotalRanked] = useState(0);
  const [failed, setFailed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const categoryName = getCategoryById(categoryId)?.name ?? categoryId;

  const doRefresh = useCallback(() => {
    setRefreshing(true);
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setFailed(false);
    getCategoryLeaderboard(categoryId, 25, metric)
      .then((d) => {
        if (cancelled) return;
        setRows(d?.leaderboard ?? []);
        setYourRank(d?.your_rank ?? null);
        setTotalRanked(d?.total_ranked ?? 0);
      })
      .catch((e) => {
        if (cancelled) return;
        logger.error('[Leaderboard] category fetch failed:', e);
        setFailed(true);
      })
      .finally(() => { if (!cancelled) setRefreshing(false); });
    return () => { cancelled = true; };
  }, [categoryId, metric, reloadKey]);

  // An empty board and a failed request are different facts and must not share
  // a rendering: "nobody qualifies yet" is true, "we could not ask" is not.
  const valuedRows = rows?.filter((r) => r.value_eur > 0) ?? [];
  const allZeroValue = metric === 'value' && (rows?.length ?? 0) > 0 && valuedRows.length === 0;

  // Same entrance as the XP board. Declared here, above every early return in
  // the JSX, because the hook has to run on every render regardless of whether
  // the board is loading, empty or failed.
  const { getItemStyle: getCatItemStyle } = useStaggerReveal({
    count: rows?.length ?? 0,
    staggerMs: 60,
    enabled: settings.animationsEnabled,
  });

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={styles.catWrap}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={doRefresh} tintColor={colors.accent} />
      }
    >
      <Text style={[styles.catTitle, { color: colors.text }]}>{categoryName} leaderboard</Text>
      <Text style={[styles.catSubtitle, { color: colors.muted }]}>
        Collectors who chose to be discoverable, ranked by what they hold in this category.
      </Text>

      <View style={styles.catToggle}>
        {(['items', 'value'] as const).map((m) => (
          <AnimatedPressable
            key={m}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              setMetric(m);
            }}
            style={[
              styles.catChip,
              { borderColor: colors.border },
              metric === m && { backgroundColor: colors.accent, borderColor: colors.accent },
            ]}
            accessibilityRole="button"
            accessibilityState={{ selected: metric === m }}
            accessibilityLabel={m === 'items' ? 'Rank by items owned' : 'Rank by value held'}
          >
            <Text style={[styles.catChipText, { color: metric === m ? colors.accentText : colors.text }]}>
              {m === 'items' ? 'Items' : 'Value'}
            </Text>
          </AnimatedPressable>
        ))}
      </View>

      {yourRank != null && totalRanked > 0 && !rows?.some((r) => r.is_you && r.rank <= 25) ? (
        <Text style={[styles.catYou, { color: colors.muted }]}>
          You are #{yourRank} of {totalRanked}
        </Text>
      ) : null}

      {failed ? (
        <Text style={[styles.catEmpty, { color: colors.muted }]}>
          Couldn&apos;t load the leaderboard. Pull down to try again.
        </Text>
      ) : !rows ? (
        <ActivityIndicator style={{ marginTop: 24 }} color={colors.accent} />
      ) : rows.length === 0 ? (
        <Text style={[styles.catEmpty, { color: colors.muted }]}>
          Nobody is ranked in {categoryName} yet. Collectors appear here once they own
          something in this category and allow discovery in Settings → Privacy.
        </Text>
      ) : allZeroValue ? (
        <Text style={[styles.catEmpty, { color: colors.muted }]}>
          No valuations yet for {categoryName}, so there is nothing to rank by value.
          Switch to Items, or check back once these collections have been priced.
        </Text>
      ) : (
        /* Same card as the XP board below — reported 2026-08-17 as wanting the
           two boards to look alike, and they were built weeks apart: this one
           was a bare bordered strip with no card fill, no medals, no handle, no
           second stat and no way into a profile, while the XP board had all
           five. Ranking is the same idea on both, so it gets the same object.

           Two things stay different ON PURPOSE. The rank is `r.rank` from the
           server, NOT the array index the XP board uses — ranks here can TIE
           (two collectors with nine items are both #4), and renumbering by
           position would silently invent an order the data does not have. And
           `is_you` keeps its accent fill, because "where am I" is the first
           question anyone asks of a board they might be on. */
        rows.map((r, index) => {
          const medalColor = getMedalColor(r.rank - 1, colors.muted);
          const stat =
            metric === 'value'
              ? formatPrice(r.value_eur, settings.currency, settings.numberLocale)
              : `${formatNumber(r.item_count, settings.numberLocale)} ${r.item_count === 1 ? 'item' : 'items'}`;
          const secondary =
            metric === 'value'
              ? `${formatNumber(r.item_count, settings.numberLocale)} ${r.item_count === 1 ? 'item' : 'items'}`
              : formatPrice(r.value_eur, settings.currency, settings.numberLocale);
          return (
            <Animated.View key={r.user_id} style={getCatItemStyle(index)}>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  router.push(`/users/${encodeURIComponent(r.user_id)}`);
                }}
                style={[
                  styles.card,
                  { borderColor: colors.border, backgroundColor: colors.card },
                  r.is_you && { backgroundColor: colors.accent + '12', borderColor: colors.accent },
                ]}
                accessibilityRole="button"
                accessibilityLabel={`Rank ${r.rank}, ${r.display_name}${r.is_you ? ', you' : ''}, ${stat}, ${secondary}`}
                accessibilityHint="Double tap to view collector profile"
              >
                <View style={styles.rankCol}>
                  <Text style={[styles.rankText, { color: medalColor }]}>#{r.rank}</Text>
                  {r.rank <= 3 && <Ionicons name="trophy-outline" size={14} color={medalColor} />}
                </View>

                <AvatarCircle name={r.display_name} color={colors.accent} />
                <View style={styles.infoCol}>
                  <Text style={[styles.userName, { color: colors.text }]} numberOfLines={1}>
                    {r.display_name}{r.is_you ? ' (you)' : ''}
                  </Text>
                  {/* `handle` is nullable on this endpoint, unlike the XP board
                      where it is derived from the name. Rendering `@` alone
                      would look like a truncation bug. */}
                  {r.handle ? (
                    <Text style={[styles.userHandle, { color: colors.muted }]} numberOfLines={1}>
                      @{r.handle}
                    </Text>
                  ) : null}
                </View>

                <View style={styles.valueCol}>
                  <Text style={[styles.valueText, { color: colors.text }]}>{stat}</Text>
                  <Text style={[styles.rarityText, { color: colors.muted }]}>{secondary}</Text>
                </View>
              </AnimatedPressable>
            </Animated.View>
          );
        })
      )}
    </ScrollView>
  );
}

const AvatarCircle = React.memo<{ name: string; color: string }>(function AvatarCircle({ name, color }) {
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

/** One row of the leaderboard, already formatted for display. */
export type LeaderboardRow = {
  id: string;
  displayName: string;
  handle: string;
  primary: string;
  secondary: string;
  meta: string;
};

/**
 * Map an XP-board API entry to display strings.
 *
 * Exported and pure so the display seam is testable: the bug this replaced was
 * invisible to types and to every status-code check, because the wrong value
 * rendered perfectly — 40 XP as "€40.00".
 */
export function apiEntryToRow(entry: {
  rank: number;
  user_id: string;
  display_name: string | null;
  total_xp: number;
  level: number;
  current_streak: number;
}, locale: NumberLocale = 'de-DE'): LeaderboardRow {
  const displayName = entry.display_name ?? `Collector ${entry.rank}`;
  return {
    id: entry.user_id,
    displayName,
    handle: displayName.toLowerCase().replace(/\s+/g, ''),
    // Number formatting follows `user_settings.locale` (NumberLocale), NOT the
    // device locale and NOT the i18n UI language — see docs/ARCHITECTURE.md
    // "user_settings: currency / region / locale". A bare `toLocaleString()`
    // here rendered 12500 as "12.500 XP" on a Dutch phone and "12,500 XP" on a
    // US one, ignoring the locale the user actually chose.
    primary: `${formatNumber(entry.total_xp, locale)} XP`,
    secondary: `Level ${entry.level}`,
    meta: entry.current_streak > 0 ? `${entry.current_streak} day streak` : 'No active streak',
  };
}

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
  // `/leaderboard?categoryId=mtg` switches this screen into category mode.
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();

  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [apiEntries, setApiEntries] = useState<{
    rank: number;
    user_id: string;
    display_name: string;
    xp: number;
    level: number;
    streak: number;
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
            // Returned by the API and previously dropped on the floor; it is the
            // natural secondary stat for an XP board.
            streak: r.current_streak,
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

  // Use API data if available, fall back to local USER_PROFILES.
  //
  // These two sources measure DIFFERENT things, so each supplies its own
  // display strings. The API board ranks by XP; the local sample ranks by
  // collection value. Until 2026-07-31 the API branch was poured into the
  // sample's shape — `totalEstimatedValueEur: entry.xp` — and the card renders
  // that field through `formatPrice`, so a collector with 40 XP was shown as
  // **"€40.00"**, their level as "1 item", and "0 categories" for everyone.
  const rankedUsers = useMemo(() => {
    if (apiEntries?.length) {
      return apiEntries.map((entry) => ({
        ...apiEntryToRow({
          rank: entry.rank,
          user_id: entry.user_id,
          display_name: entry.display_name,
          total_xp: entry.xp,
          level: entry.level,
          current_streak: entry.streak,
        }, settings.numberLocale),
        avatarColor: colors.accent,
      }));
    }
    return [...USER_PROFILES]
      .sort((a, b) => b.stats.totalEstimatedValueEur - a.stats.totalEstimatedValueEur)
      .map((u) => ({
        id: u.id,
        displayName: u.displayName,
        handle: u.handle,
        avatarColor: u.avatarColor,
        primary: formatPrice(u.stats.totalEstimatedValueEur),
        secondary: `Rarity ${u.stats.rarityScore}`,
        meta: `${u.stats.totalItems} ${u.stats.totalItems === 1 ? 'item' : 'items'} · ${u.stats.totalCategories} ${u.stats.totalCategories === 1 ? 'category' : 'categories'}`,
      }));
  }, [apiEntries, colors.accent, settings.numberLocale]);

  const { getItemStyle } = useStaggerReveal({
    count: rankedUsers.length,
    staggerMs: 60,
    enabled: settings.animationsEnabled,
  });

  // Category mode. Placed AFTER every hook above so hook order never changes
  // between renders — an early return before them would break the rules of
  // hooks the moment a param appeared.
  if (categoryId) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        {/* No native title in category mode: CategoryLeaderboard renders
            "<Category> leaderboard" as its own heading, so a bar title is a
            duplicate — and on iOS a CENTRED duplicate, since native-stack
            ignores headerTitleAlign there. The global XP mode below keeps its
            native title because it has no in-body heading. */}
        <Stack.Screen options={{ headerTitle: '' }} />
        <CategoryLeaderboard categoryId={categoryId} />
        <QuickNavBar />
      </View>
    );
  }

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
              accessibilityLabel={`Rank ${index + 1}, ${user.displayName}, ${user.primary}, ${user.secondary}, ${user.meta}`}
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
                  {user.meta}
                </Text>
              </View>

              {/* Value + key score */}
              <View style={styles.valueCol}>
                <Text style={[styles.valueText, { color: colors.text }]}>
                  {user.primary}
                </Text>
                <Text style={[styles.rarityText, { color: colors.muted }]}>
                  {user.secondary}
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
  catWrap: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 24 },
  catTitle: { fontSize: 24, fontWeight: '800', lineHeight: 30 },
  catSubtitle: { fontSize: 13, marginTop: 4, lineHeight: 18 },
  catToggle: { flexDirection: 'row', gap: 8, marginTop: 14, marginBottom: 12 },
  catChip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999, borderWidth: 1 },
  catChipText: { fontSize: 14, fontWeight: '600' },
  catEmpty: { fontSize: 14, lineHeight: 20, marginTop: 20 },
  catYou: { fontSize: 13, marginBottom: 10 },
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
