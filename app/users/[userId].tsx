/**
 * User Profile Screen — Pro-grade collector profile with opt-in sections.
 * Route: /users/[userId]
 * Uses DataProvider for profile data; hides sections when data unavailable.
 */

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Modal,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { radius, text as textToken, fontWeight as fw } from '@/theme/tokens';
import { useToast } from '@/components/Toast';
import { getJSON, setJSON } from '@/lib/storage';
import { ACHIEVEMENTS, type Achievement } from '@/lib/achievements';
import { collectorsApi } from '@/api/collectorsApi';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { PresenceIndicator } from '@/components/PresenceIndicator';
import { useAsync } from '@/hooks/useAsync';
import useAuth from '@/hooks/useAuth';
import logger from '@/utils/logger';
import { track } from '@/analytics/track';
import { UserStatsSection } from '@/components/users/UserStatsSection';
import { TradeReputationSection } from '@/components/users/TradeReputationSection';
import { UserAchievementsSection } from '@/components/users/UserAchievementsSection';
import { UserCategoriesSection } from '@/components/users/UserCategoriesSection';
import { UserCollectionPreview } from '@/components/users/UserCollectionPreview';
import { safeGoBack } from '@/lib/goBack';

type DmStatusType = 'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined';

// ─────────────────────────────────────────────────────────────────────────────
// Avatar Component
// ─────────────────────────────────────────────────────────────────────────────
const AvatarCircle = React.memo(function AvatarCircle({ name, size = 64 }: { name: string; size?: number }) {
  const { colors } = useAppTheme();
  const initials = name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || '?';

  return (
    <View
      style={[
        styles.avatar,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: colors.accent,
        },
      ]}
    >
      <Text style={[styles.avatarText, { fontSize: size * 0.35, color: colors.accentText }]}>{initials}</Text>
    </View>
  );
});


// ─────────────────────────────────────────────────────────────────────────────
// Main Screen
// ─────────────────────────────────────────────────────────────────────────────
function UserProfileScreen() {
  const { t } = useTranslation();
  const { userId } = useLocalSearchParams<{ userId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { user: currentUser } = useAuth();

  const [isFollowing, setIsFollowing] = useState(false);
  const [isUserBlocked, setIsUserBlocked] = useState(false);
  const [dmStatus, setDmStatus] = useState<DmStatusType>('none');
  const [showMenu, setShowMenu] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const { showToast } = useToast();

  const { data: profileData, loading, error, retry } = useAsync(
    () => {
      if (!userId) return Promise.reject(new Error('No user ID provided'));
      return dataProvider.getPublicUserProfile(userId);
    },
    [userId],
  );

  const profile = profileData ?? null;

  // Track profile view
  useEffect(() => {
    if (!userId) return;
    track({ name: 'profile_viewed', properties: { userId } });
  }, [userId]);

  // Load follow state from AsyncStorage on mount
  useEffect(() => {
    if (!userId) return;
    getJSON<string[]>('followed_users', []).then((ids) => {
      setIsFollowing(ids.includes(userId));
    });
  }, [userId]);

  // Load DM status and block state on mount
  useEffect(() => {
    if (!userId) return;

    const checkState = async () => {
      try {
        const [blocked, status] = await Promise.all([
          dataProvider.isBlocked(userId),
          dataProvider.getDmStatus(userId),
        ]);
        setIsUserBlocked(blocked);
        setDmStatus(status);
      } catch (e) {
        logger.error('[silent-fallback] users: profile action failed:', e);
        // Silently ignore state check errors
      }
    };

    checkState();
  }, [userId]);

  const handleFollowToggle = useCallback(async () => {
    if (!userId) return;
    const next = !isFollowing;
    setIsFollowing(next);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: true });
    const ids = await getJSON<string[]>('followed_users', []);
    if (next) {
      if (!ids.includes(userId)) ids.push(userId);
    } else {
      const idx = ids.indexOf(userId);
      if (idx !== -1) ids.splice(idx, 1);
    }
    await setJSON('followed_users', ids);
    showToast({ message: next ? 'Following!' : 'Unfollowed', type: 'success' });
  }, [userId, isFollowing, showToast]);

  const handleBlockToggle = useCallback(async () => {
    if (!userId) return;
    setShowMenu(false);

    if (isUserBlocked) {
      // Unblock
      try {
        await dataProvider.unblockUser(userId);
        setIsUserBlocked(false);
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        showToast({ message: 'Unblocked', type: 'success' });
      } catch (err: unknown) {
        showToast({ message: err instanceof Error ? err.message : 'Failed to unblock user', type: 'error' });
      }
    } else {
      // Block
      Alert.alert(
        'Block User',
        `Block ${profile?.displayName ?? 'this user'}? They won't be able to message you, and pending requests will be declined. You can unblock them later.`,
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Block',
            style: 'destructive',
            onPress: async () => {
              try {
                await dataProvider.blockUser(userId);
                setIsUserBlocked(true);
                setDmStatus('none');
                fireHaptic(HapticIntent.ALERT_TRIGGERED);
                showToast({ message: 'Blocked', type: 'success' });
              } catch (err: unknown) {
                showToast({ message: err instanceof Error ? err.message : 'Failed to block user', type: 'error' });
              }
            },
          },
        ]
      );
    }
  }, [userId, isUserBlocked, profile, showToast]);

  const handleMessagePress = useCallback(() => {
    if (!userId || isUserBlocked) return;

    if (dmStatus === 'accepted') {
      router.push('/inbox');
    } else if (dmStatus === 'pending_incoming') {
      router.push('/inbox');
    } else {
      router.push({
        pathname: '/chat/new',
        params: { toUserId: userId },
      });
    }
  }, [userId, dmStatus, isUserBlocked, router]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await retry();
    setRefreshing(false);
  }, [retry]);

  // Fetch real achievements from backend, fall back to client-side derivation
  const [apiAchievements, setApiAchievements] = useState<{ id: string; title: string; tier: string; earned: boolean }[] | null>(null);
  // Fetch gamification profile (XP, level, streak)
  const [gamProfile, setGamProfile] = useState<{ xp: number; level: number; streak_days: number } | null>(null);
  // Fetch active challenges
  const [challenges, setChallenges] = useState<{ id: string; title: string; progress: number; target: number; reward_xp: number }[]>([]);
  // Recent achievements (for "New!" badges)
  const [recentAchievementIds, setRecentAchievementIds] = useState<Set<string>>(new Set());

  /**
   * Is this me?
   *
   * Computed ONCE here because it now decides what renders, not just what is
   * fetched. It used to live inside a single effect while three render sites
   * recomputed `userId === currentUser?.id` inline — fine while nothing could
   * navigate here, and wrong the moment Settings → "View public profile"
   * existed (2026-08-20): the CTA row offered Message and Follow, so you could
   * open a DM with yourself and follow yourself.
   */
  // `!!userId &&` first: with no param AND no session both sides are
  // `undefined`, `undefined === undefined` is TRUE, and the screen would hide
  // the CTA row and claim a stranger's profile was your own.
  const isSelf = !!userId && userId === currentUser?.id;

  useEffect(() => {
    if (!userId) return;
    const isOwnProfile = isSelf;

    if (isOwnProfile) {
      // Fetch full gamification data for authenticated user
      collectorsApi.getAchievements()
        .then((data) => {
          // Server returns achievements with `unlocked` / `unlocked_at` (not
          // `earned` / `earned_at`). Mapping at the boundary.
          if (data?.achievements?.length) {
            setApiAchievements(data.achievements.map((a) => ({
              id: a.id, title: a.title, tier: a.tier, earned: a.unlocked,
            })));
          }
        })
        .catch((err) => logger.info('[UserProfile] API fallback:', err));

      collectorsApi.getGamificationProfile()
        .then((data) => {
          // Server wraps the payload in {profile: {...}} and uses `total_xp`
          // / `current_streak` (not `xp` / `streak_days`).
          const p = data?.profile;
          if (p && p.level != null) {
            setGamProfile({ xp: p.total_xp, level: p.level, streak_days: p.current_streak });
          }
        })
        .catch((err) => logger.info('[UserProfile] API fallback:', err));

      collectorsApi.getActiveChallenges()
        .then((data) => {
          if (data?.challenges?.length) setChallenges(data.challenges);
        })
        .catch((err) => logger.info('[UserProfile] API fallback:', err));

      collectorsApi.getRecentAchievements()
        .then((data) => {
          if (data?.achievements?.length) {
            setRecentAchievementIds(new Set(data.achievements.map((a) => a.id)));
          }
        })
        .catch((err) => logger.info('[UserProfile] API fallback:', err));
    } else {
      // Fetch public gamification profile for other users
      collectorsApi.getPublicGamificationProfile(userId)
        .then((data) => {
          if (data?.profile) {
            const p = data.profile;
            setGamProfile({ xp: p.total_xp, level: p.level, streak_days: p.current_streak });

            // Map recent achievements into the badges display
            if (p.recent_achievements?.length) {
              setApiAchievements(p.recent_achievements.map((a) => ({
                id: a.id, title: a.title, tier: a.tier, earned: true,
              })));
              setRecentAchievementIds(new Set(p.recent_achievements.map((a) => a.id)));
            }
          }
        })
        .catch((err) => logger.info('[UserProfile] Public gamification fallback:', err));
    }
  }, [userId, isSelf]);

  const profileBadges = useMemo(() => {
    // Use real backend data if available
    if (apiAchievements?.length) {
      return apiAchievements.slice(0, 8).map((a) => {
        const localMatch = ACHIEVEMENTS.find((la) => la.id === a.id);
        return {
          ...(localMatch ?? { id: a.id, title: a.title, description: '', icon: 'ribbon-outline', category: 'collection' as const, tier: a.tier as 'bronze' | 'silver' | 'gold' | 'platinum', condition: () => a.earned }),
          earned: a.earned,
        };
      });
    }
    // Fallback: derive from profile stats
    if (!profile) return [];
    const stats = {
      itemCount: profile.collectionCount ?? 0,
      totalValue: profile.collectionValueEur ?? 0,
      categoryCount: profile.interests?.length ?? 0,
      scanCount: 0,
      streakDays: 0,
      feedbackCount: 0,
      joinedDaysAgo: 0,
    };
    const earned = ACHIEVEMENTS.filter((a) => a.condition(stats));
    const locked = ACHIEVEMENTS.filter((a) => !a.condition(stats)).slice(0, Math.max(0, 8 - earned.length));
    return [...earned.map((a) => ({ ...a, earned: true })), ...locked.map((a) => ({ ...a, earned: false }))].slice(0, 8);
  }, [profile, apiAchievements]);

  // Message button label based on DM status
  const messageButtonLabel = useMemo(() => {
    if (isUserBlocked) return 'Blocked';
    switch (dmStatus) {
      case 'pending_outgoing': return 'Request Sent';
      case 'pending_incoming': return 'Respond';
      case 'accepted': return 'Message';
      default: return 'Message';
    }
  }, [dmStatus, isUserBlocked]);

  const messageButtonDisabled = isUserBlocked || dmStatus === 'pending_outgoing';

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  // Error / Not found state
  if (error || !profile) {
    /**
     * YOUR OWN profile missing is a different fact, and it has a cause.
     *
     * `user_public_profile_v1` ends in
     * `WHERE COALESCE(NULLIF(display_name,''), NULLIF(username,'')) IS NOT NULL`
     * — a member who has never set a display name or a username has NO ROW in
     * the view, so the read returns nothing. Verified on prod 2026-08-20: the
     * sim account (display_name NULL) has 0 rows, Lena V. has 1.
     *
     * Telling that member "this profile doesn't exist" is telling them they do
     * not exist, and the Settings → View public profile row added the same day
     * would walk them straight into it — a door that leads to an error page,
     * for exactly the accounts least likely to have filled anything in. So the
     * self branch says what is actually true and what fixes it.
     */
    if (isSelf && !error) {
      return (
        <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
          <View style={styles.centerContainer}>
            <Ionicons name="person-circle-outline" size={48} color={colors.muted} />
            <Text style={[styles.errorTitle, { color: colors.text }]}>
              Your public profile isn&apos;t set up yet
            </Text>
            <Text style={[styles.errorSubtitle, { color: colors.muted }]}>
              Add a display name so other collectors can find you and see what
              you collect.
            </Text>
            <AnimatedPressable
              style={[styles.retryBtn, { borderColor: colors.accent, backgroundColor: colors.accent }]}
              onPress={() => router.push('/settings' as Href)}
              accessibilityRole="button"
              accessibilityLabel="Open settings to add a display name"
            >
              <Text style={[styles.retryBtnText, { color: colors.accentText }]}>Add a display name</Text>
            </AnimatedPressable>
            <AnimatedPressable
              style={styles.plainBackBtn}
              onPress={() => safeGoBack(router)}
              accessibilityRole="button"
              accessibilityLabel={t('common.go_back_a11y')}
            >
              <Text style={[styles.retryBtnText, { color: colors.muted }]}>{t('common.go_back')}</Text>
            </AnimatedPressable>
          </View>
        </SafeAreaView>
      );
    }

    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.centerContainer}>
          <Ionicons name="person-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorTitle, { color: colors.text }]}>
            {error || 'Collector not found'}
          </Text>
          <Text style={[styles.errorSubtitle, { color: colors.muted }]}>
            This profile doesn&apos;t exist or couldn&apos;t be loaded.
          </Text>
          <AnimatedPressable
            style={[styles.retryBtn, { borderColor: colors.border }]}
            onPress={() => safeGoBack(router)}
            accessibilityRole="button"
            accessibilityLabel={t('common.go_back_a11y')}
          >
            <Text style={[styles.retryBtnText, { color: colors.text }]}>{t('common.go_back')}</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        {/* No back control: no other screen in the app carries an inline "‹ Back"
            row, and this one is always reached by a push (a listing's seller, a
            search result, a chat), so the platform's own affordances apply — the
            iOS edge swipe and the Android system back, both handled by
            expo-router. The error state below keeps an explicit "Go back",
            because a dead end must offer a way out. */}
        <View style={styles.topRow}>
          <AnimatedPressable
            onPress={() => setShowMenu(true)}
            style={styles.menuBtn}
            accessibilityRole="button"
            accessibilityLabel={t('common.more_options_a11y')}
          >
            <Ionicons name="ellipsis-horizontal" size={22} color={colors.text} />
          </AnimatedPressable>
        </View>

        {/* Blocked banner */}
        {isUserBlocked && (
          <View style={[styles.blockedBanner, { backgroundColor: colors.danger + '15' }]}>
            <Ionicons name="ban-outline" size={16} color={colors.danger} />
            <Text style={[styles.blockedBannerText, { color: colors.danger }]}>{t('user_profile.blocked_user')}</Text>
          </View>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            A) Profile Header Card
        ═══════════════════════════════════════════════════════════════════ */}
        {/* The identity block, rebuilt 2026-08-20.

            It used to open with an 80pt accent banner, a 60pt top pad and a
            ringed 80pt avatar hanging into it, then centre the name, the
            handle and the presence dot — roughly 140pt of decoration before
            the first fact about the collector, and a centre axis that nothing
            below it shared (stats were centred, collects and trading are
            left-aligned rows). Reported as the card that had not changed while
            everything around it had.

            One row now: avatar, then name / handle / presence stacked beside
            it, on the SAME left edge as every section under it. The accent
            survives as the avatar ring — a colour cue costs nothing; an 80pt
            band costs the fold. */}
        <View style={[styles.profileCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={styles.identityRow}>
            <View style={[styles.avatarRing, { borderColor: colors.accent + '40' }]}>
              <AvatarCircle name={profile.displayName} size={56} />
            </View>

            <View style={styles.profileInfo}>
              <View style={styles.nameRow}>
                <Text style={[styles.displayName, { color: colors.text }]} numberOfLines={1}>
                  {profile.displayName}
                </Text>
                {profile.collectionCount != null && profile.collectionCount > 50 && (
                  <View style={[styles.verifiedBadge, { backgroundColor: colors.accent }]}>
                    <Ionicons name="checkmark" size={10} color={colors.accentText} />
                  </View>
                )}
              </View>
              {profile.handle && (
                <Text style={[styles.handle, { color: colors.muted }]} numberOfLines={1}>
                  @{profile.handle}
                </Text>
              )}
              {userId && <PresenceIndicator userId={userId} size={8} showLabel />}
            </View>
          </View>

          <UserStatsSection profile={profile} gamProfile={gamProfile} />

          {/* Can I trade with this person? Directly under the stats and above
              the categories: "who is this collector" is answered by the row
              above, and this is the next question anyone browsing from a
              listing actually has. Renders nothing until they have traded, so
              it costs no space on a profile with no history. */}
          {userId && !isUserBlocked ? (
            <TradeReputationSection userId={userId} isSelf={isSelf} />
          ) : null}

          {/* What they actually collect, and where they place in each category
              (2026-08-17). Above the CTA row on purpose: the answer to "who is
              this collector" should come before "message / follow them". */}
          {userId && !isUserBlocked ? (
            <UserCategoriesSection userId={userId} isSelf={isSelf} />
          ) : null}

          {/* 4. On your own profile the card ends with what it IS, rather than
                 with two controls aimed at somebody else. Without this line a
                 member arriving from Settings sees their own face above a
                 "Message" button and reasonably reads it as broken. */}
          {isSelf ? (
            <Text style={[styles.selfNote, { color: colors.muted }]}>
              This is what other collectors see.
            </Text>
          ) : null}

          {/* CTA Row — never on your own profile (3): "Message" would open a
              DM with yourself and "Follow" would follow yourself. */}
          {!isUserBlocked && !isSelf && (
            <View style={styles.ctaRow}>
              <AnimatedPressable
                style={[
                  styles.ctaBtn,
                  styles.ctaBtnPrimary,
                  {
                    backgroundColor: messageButtonDisabled ? colors.border : colors.accent,
                    opacity: messageButtonDisabled ? 0.6 : 1,
                  },
                ]}
                onPress={handleMessagePress}
                disabled={messageButtonDisabled}
                accessibilityRole="button"
                accessibilityLabel={`${messageButtonLabel} ${profile.displayName}`}
              >
                <Ionicons
                  name={dmStatus === 'pending_outgoing' ? 'hourglass-outline' : 'chatbubble-outline'}
                  size={18}
                  color={colors.accentText}
                />
                <Text style={[styles.ctaBtnTextLight, { color: colors.accentText }]}>{messageButtonLabel}</Text>
              </AnimatedPressable>

              <AnimatedPressable
                style={[
                  styles.ctaBtn,
                  {
                    backgroundColor: isFollowing ? colors.accent + '20' : colors.background,
                    borderColor: isFollowing ? colors.accent : colors.border,
                    borderWidth: 1,
                  },
                ]}
                onPress={handleFollowToggle}
                accessibilityRole="button"
                accessibilityLabel={isFollowing ? `Unfollow ${profile.displayName}` : `Follow ${profile.displayName}`}
              >
                <Ionicons
                  name={isFollowing ? 'person-remove-outline' : 'person-add-outline'}
                  size={16}
                  color={isFollowing ? colors.accent : colors.text}
                />
                <Text style={[styles.ctaBtnText, { color: isFollowing ? colors.accent : colors.text }]}>
                  {isFollowing ? 'Following' : 'Follow'}
                </Text>
              </AnimatedPressable>
            </View>
          )}
        </View>

        {/* Achievements (badges + challenges) */}
        <UserAchievementsSection
          profileBadges={profileBadges}
          recentAchievementIds={recentAchievementIds}
          challenges={challenges}
        />

        {/* Bio + Interests */}
        <UserCollectionPreview profile={profile} />

        {/* Bottom spacing */}
        <View style={{ height: 32 }} />
      </ScrollView>

      {/* 3-dot menu modal */}
      <Modal
        visible={showMenu}
        transparent
        animationType="fade"
        onRequestClose={() => setShowMenu(false)}
      >
        <AnimatedPressable
          style={styles.menuOverlay}
          onPress={() => setShowMenu(false)}
          accessibilityRole="button"
          accessibilityLabel={t('common.close_menu_a11y')}
        >
          <View style={[styles.menuSheet, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <AnimatedPressable
              style={styles.menuItem}
              onPress={handleBlockToggle}
              accessibilityRole="button"
              accessibilityLabel={isUserBlocked ? 'Unblock user' : 'Block user'}
            >
              <Ionicons
                name={isUserBlocked ? 'checkmark-circle-outline' : 'ban-outline'}
                size={20}
                color={isUserBlocked ? colors.accent : colors.danger}
              />
              <Text style={[styles.menuItemText, { color: isUserBlocked ? colors.text : colors.danger }]}>
                {isUserBlocked ? 'Unblock User' : 'Block User'}
              </Text>
            </AnimatedPressable>

            <View style={[styles.menuDivider, { backgroundColor: colors.border }]} />

            <AnimatedPressable
              style={styles.menuItem}
              onPress={() => setShowMenu(false)}
              accessibilityRole="button"
              accessibilityLabel="Cancel"
            >
              <Text style={[styles.menuItemText, { color: colors.muted }]}>Cancel</Text>
            </AnimatedPressable>
          </View>
        </AnimatedPressable>
      </Modal>
      <QuickNavBar />
    </SafeAreaView>
  );
}

export default function UserProfileScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="User Profile">
      <UserProfileScreen />
    </ScreenErrorBoundary>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  // Holds the menu button alone since the inline Back row was removed, so it
  // pushes to the right rather than justifying two children apart.
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  menuBtn: {
    padding: 8,
  },
  blockedBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: radius.sm,
    marginBottom: 12,
  },
  blockedBannerText: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,
  },
  errorTitle: {
    fontSize: textToken.xl,
    fontWeight: fw.bold,
    marginTop: 16,
  },
  errorSubtitle: {
    fontSize: textToken.md,
    textAlign: 'center',
    marginTop: 8,
  },
  retryBtn: {
    marginTop: 24,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: radius.sm,
    borderWidth: 1,
  },
  retryBtnText: {
    fontSize: textToken.md,
    fontWeight: fw.semibold,
  },

  // Profile card
  profileCard: {
    borderRadius: radius.lg,
    borderWidth: 1,
    padding: 20,
    overflow: 'hidden',
  },
  identityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  avatarRing: {
    padding: 3,
    borderRadius: radius.pill,
    borderWidth: 2,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  verifiedBadge: {
    width: 18,
    height: 18,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatar: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontWeight: fw.bold,
  },
  profileInfo: {
    flex: 1,
    // `flex: 1` and nothing else: the column claims the rest of the row so a
    // long display name truncates against the card edge instead of pushing
    // the layout wider than the card.
    gap: 2,
  },
  displayName: {
    fontSize: textToken.xl,
    fontWeight: fw.bold,
  },
  handle: {
    fontSize: textToken.md,
  },
  plainBackBtn: {
    marginTop: 10,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  selfNote: {
    fontSize: textToken.sm,
    lineHeight: 17,
    marginTop: 16,
  },
  ctaRow: {
    flexDirection: 'row',
    marginTop: 24,
    gap: 12,
    width: '100%',
  },
  ctaBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderRadius: radius.md,
    gap: 8,
  },
  ctaBtnPrimary: {},
  ctaBtnText: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },
  ctaBtnTextLight: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },


  // Menu modal
  menuOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  menuSheet: {
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderWidth: 1,
    borderBottomWidth: 0,
    paddingVertical: 8,
    paddingBottom: 32,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  menuItemText: {
    fontSize: textToken.lg,
    fontWeight: fw.medium,
  },
  menuDivider: {
    height: 1,
    marginHorizontal: 16,
  },
});
