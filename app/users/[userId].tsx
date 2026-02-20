/**
 * User Profile Screen — Pro-grade collector profile with opt-in sections.
 * Route: /users/[userId]
 * Uses DataProvider for profile data; hides sections when data unavailable.
 */

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import logger from '@/utils/logger';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import { getJSON, setJSON } from '@/lib/storage';
import { ACHIEVEMENTS, type Achievement } from '@/lib/achievements';

type DmStatusType = 'none' | 'pending_outgoing' | 'pending_incoming' | 'accepted' | 'declined';

// ─────────────────────────────────────────────────────────────────────────────
// Avatar Component
// ─────────────────────────────────────────────────────────────────────────────
const AvatarCircle: React.FC<{ name: string; size?: number }> = ({ name, size = 64 }) => {
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
      <Text style={[styles.avatarText, { fontSize: size * 0.35 }]}>{initials}</Text>
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Section Card Component
// ─────────────────────────────────────────────────────────────────────────────
const SectionCard: React.FC<{
  title: string;
  icon?: string;
  children: React.ReactNode;
}> = ({ title, icon, children }) => {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.sectionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.sectionHeader}>
        {icon && <Ionicons name={icon as any} size={16} color={colors.accent} />}
        <Text style={[styles.sectionTitle, { color: colors.muted }]}>{title}</Text>
      </View>
      {children}
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Badge Item Component
// ─────────────────────────────────────────────────────────────────────────────
const TIER_COLORS = {
  bronze: '#CD7F32',
  silver: '#C0C0C0',
  gold: '#FFD700',
  platinum: '#E5E4E2',
};

const BadgeItem: React.FC<{ achievement: Achievement; earned: boolean }> = ({ achievement, earned }) => {
  const { colors } = useAppTheme();
  const tierColor = TIER_COLORS[achievement.tier];

  return (
    <View style={[styles.badgeItem, { opacity: earned ? 1 : 0.4 }]}>
      <View style={[styles.badgeIcon, { backgroundColor: earned ? tierColor + '20' : colors.border + '40' }]}>
        <Ionicons
          name={achievement.icon as any}
          size={20}
          color={earned ? tierColor : colors.muted}
        />
      </View>
      <Text
        style={[styles.badgeLabel, { color: earned ? colors.text : colors.muted }]}
        numberOfLines={1}
      >
        {achievement.title}
      </Text>
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Main Screen
// ─────────────────────────────────────────────────────────────────────────────
export default function UserProfileScreen() {
  const { userId } = useLocalSearchParams<{ userId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();

  const [profile, setProfile] = useState<PublicUserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFollowing, setIsFollowing] = useState(false);
  const [isUserBlocked, setIsUserBlocked] = useState(false);
  const [dmStatus, setDmStatus] = useState<DmStatusType>('none');
  const [showMenu, setShowMenu] = useState(false);
  const { showToast } = useToast();

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
      } catch (err) {
        logger.warn('[UserProfile] checkState error:', err);
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
        Alert.alert('Error', err instanceof Error ? err.message : 'Failed to unblock user');
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
                Alert.alert('Error', err instanceof Error ? err.message : 'Failed to block user');
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

  const loadProfile = useCallback(async () => {
    if (!userId) {
      setError('No user ID provided');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const profileData = await dataProvider.getPublicUserProfile(userId);
      setProfile(profileData);
    } catch (err: unknown) {
      logger.warn('[UserProfile] loadProfile error:', err);
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // Derive badges from profile data
  const profileBadges = useMemo(() => {
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
    // Show up to 8 relevant badges (earned first, then locked)
    const earned = ACHIEVEMENTS.filter((a) => a.condition(stats));
    const locked = ACHIEVEMENTS.filter((a) => !a.condition(stats)).slice(0, Math.max(0, 8 - earned.length));
    return [...earned.map((a) => ({ ...a, earned: true })), ...locked.map((a) => ({ ...a, earned: false }))].slice(0, 8);
  }, [profile]);

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
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.centerContainer}>
          <AnimatedPressable onPress={() => router.back()} style={styles.floatingBack} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={22} color={colors.text} />
          </AnimatedPressable>
          <Ionicons name="person-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorTitle, { color: colors.text }]}>
            {error || 'Collector not found'}
          </Text>
          <Text style={[styles.errorSubtitle, { color: colors.muted }]}>
            This profile doesn't exist or couldn't be loaded.
          </Text>
          <AnimatedPressable
            style={[styles.retryBtn, { borderColor: colors.border }]}
            onPress={() => router.back()}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Text style={[styles.retryBtnText, { color: colors.text }]}>Go back</Text>
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
      >
        {/* Top row with back + menu */}
        <View style={styles.topRow}>
          <AnimatedPressable
            onPress={() => router.back()}
            style={styles.backRow}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Ionicons name="chevron-back" size={22} color={colors.text} />
            <Text style={[styles.backText, { color: colors.text }]}>Back</Text>
          </AnimatedPressable>

          <AnimatedPressable
            onPress={() => setShowMenu(true)}
            style={styles.menuBtn}
            accessibilityRole="button"
            accessibilityLabel="More options"
          >
            <Ionicons name="ellipsis-horizontal" size={22} color={colors.text} />
          </AnimatedPressable>
        </View>

        {/* Blocked banner */}
        {isUserBlocked && (
          <View style={[styles.blockedBanner, { backgroundColor: '#EF444415' }]}>
            <Ionicons name="ban-outline" size={16} color="#EF4444" />
            <Text style={styles.blockedBannerText}>You have blocked this user</Text>
          </View>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            A) Profile Header Card
        ═══════════════════════════════════════════════════════════════════ */}
        <View style={[styles.profileCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {/* Accent banner at top */}
          <View style={[styles.profileBanner, { backgroundColor: colors.accent + '20' }]} />

          {/* Avatar with accent ring */}
          <View style={[styles.avatarRing, { borderColor: colors.accent + '40', backgroundColor: colors.card }]}>
            <AvatarCircle name={profile.displayName} size={80} />
          </View>

          <View style={styles.profileInfo}>
            <View style={styles.nameRow}>
              <Text style={[styles.displayName, { color: colors.text }]}>
                {profile.displayName}
              </Text>
              {profile.collectionCount != null && profile.collectionCount > 50 && (
                <View style={[styles.verifiedBadge, { backgroundColor: colors.accent }]}>
                  <Ionicons name="checkmark" size={10} color="#fff" />
                </View>
              )}
            </View>
            {profile.handle && (
              <Text style={[styles.handle, { color: colors.muted }]}>
                @{profile.handle}
              </Text>
            )}
          </View>

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
            <View style={styles.quickStat}>
              <Text style={[styles.quickStatValue, { color: colors.text }]}>{profile.interests?.length ?? 0}</Text>
              <Text style={[styles.quickStatLabel, { color: colors.muted }]}>Categories</Text>
            </View>
          </View>

          {/* CTA Row */}
          {!isUserBlocked && (
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
                  color="#FFFFFF"
                />
                <Text style={styles.ctaBtnTextLight}>{messageButtonLabel}</Text>
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

        {/* ═══════════════════════════════════════════════════════════════════
            B) Bio Card
        ═══════════════════════════════════════════════════════════════════ */}
        {profile.bio && (
          <SectionCard title="About" icon="person-outline">
            <Text style={[styles.bioText, { color: colors.text }]}>{profile.bio}</Text>
          </SectionCard>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            C) Badges Card — derived from achievements system
        ═══════════════════════════════════════════════════════════════════ */}
        {profileBadges.length > 0 && (
          <SectionCard title="Badges" icon="ribbon-outline">
            <View style={styles.badgesGrid}>
              {profileBadges.map((badge) => (
                <BadgeItem key={badge.id} achievement={badge} earned={badge.earned} />
              ))}
            </View>
          </SectionCard>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            D) Interests Card
        ═══════════════════════════════════════════════════════════════════ */}
        {profile.interests && profile.interests.length > 0 && (
          <SectionCard title="Interests" icon="heart-outline">
            <View style={styles.interestsRow}>
              {profile.interests.map((interest, idx) => (
                <AnimatedPressable
                  key={idx}
                  style={[styles.interestPill, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}
                  onPress={() => router.push(`/categories/${encodeURIComponent(interest)}`)}
                  accessibilityRole="button"
                  accessibilityLabel={`Browse ${interest}`}
                >
                  <Text style={[styles.interestText, { color: colors.accent }]}>{interest}</Text>
                </AnimatedPressable>
              ))}
            </View>
          </SectionCard>
        )}

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
          accessibilityLabel="Close menu"
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
                color={isUserBlocked ? colors.accent : '#EF4444'}
              />
              <Text style={[styles.menuItemText, { color: isUserBlocked ? colors.text : '#EF4444' }]}>
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
    </SafeAreaView>
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
  floatingBack: {
    position: 'absolute',
    top: 16,
    left: 16,
    padding: 8,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  backRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    padding: 4,
  },
  backText: {
    fontSize: 16,
    fontWeight: '500',
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
    borderRadius: 10,
    marginBottom: 12,
  },
  blockedBannerText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#EF4444',
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16,
  },
  errorSubtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
  },
  retryBtn: {
    marginTop: 24,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
  retryBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },

  // Profile card
  profileCard: {
    borderRadius: 20,
    borderWidth: 1,
    paddingTop: 60,
    paddingHorizontal: 24,
    paddingBottom: 24,
    alignItems: 'center',
    overflow: 'hidden',
  },
  profileBanner: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 80,
  },
  avatarRing: {
    padding: 4,
    borderRadius: 50,
    borderWidth: 3,
    marginTop: -20,
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
    fontWeight: '700',
    color: '#fff',
  },
  profileInfo: {
    alignItems: 'center',
    marginTop: 16,
  },
  displayName: {
    fontSize: 22,
    fontWeight: '700',
  },
  handle: {
    fontSize: 15,
    marginTop: 4,
  },
  quickStatsRow: {
    flexDirection: 'row',
    marginTop: 20,
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderRadius: 16,
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
    fontSize: 18,
    fontWeight: '700',
  },
  quickStatLabel: {
    fontSize: 12,
    marginTop: 2,
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
    borderRadius: 12,
    gap: 8,
  },
  ctaBtnPrimary: {},
  ctaBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
  ctaBtnTextLight: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },

  // Section card
  sectionCard: {
    borderRadius: 16,
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
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },

  // Bio
  bioText: {
    fontSize: 14,
    lineHeight: 20,
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
    fontSize: 10,
    fontWeight: '600',
    textAlign: 'center',
  },

  // Interests
  interestsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  interestPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  interestText: {
    fontSize: 13,
    fontWeight: '500',
  },

  // Menu modal
  menuOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  menuSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
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
    fontSize: 16,
    fontWeight: '500',
  },
  menuDivider: {
    height: 1,
    marginHorizontal: 16,
  },
});
