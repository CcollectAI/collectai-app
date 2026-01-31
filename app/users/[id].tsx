/**
 * User Profile Screen — Pro-grade collector profile with opt-in sections.
 * Route: /users/[id]
 * Uses DataProvider for profile data; hides sections when data unavailable.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

// UUID v4 regex for validation (prevents invalid uuid errors in Supabase)
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// ─────────────────────────────────────────────────────────────────────────────
// Avatar Component
// ─────────────────────────────────────────────────────────────────────────────
const AvatarCircle: React.FC<{ name: string; size?: number; accentColor: string }> = ({
  name,
  size = 64,
  accentColor,
}) => {
  const initials =
    name
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
          backgroundColor: accentColor,
        },
      ]}
    >
      <Text style={[styles.avatarText, { fontSize: size * 0.35 }]}>{initials}</Text>
    </View>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Section Card Component (square corners)
// ─────────────────────────────────────────────────────────────────────────────
const SectionCard: React.FC<{
  title: string;
  children: React.ReactNode;
  colors: any;
}> = ({ title, children, colors }) => (
  <View style={[styles.sectionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
    <Text style={[styles.sectionTitle, { color: colors.muted }]}>{title}</Text>
    {children}
  </View>
);

// ─────────────────────────────────────────────────────────────────────────────
// Stat Box Component (square corners)
// ─────────────────────────────────────────────────────────────────────────────
const StatBox: React.FC<{ label: string; value: string | number; colors: any }> = ({
  label,
  value,
  colors,
}) => (
  <View style={[styles.statBox, { backgroundColor: colors.background, borderColor: colors.border }]}>
    <Text style={[styles.statValue, { color: colors.text }]}>{value}</Text>
    <Text style={[styles.statLabel, { color: colors.muted }]}>{label}</Text>
  </View>
);

// ─────────────────────────────────────────────────────────────────────────────
// Main Screen
// ─────────────────────────────────────────────────────────────────────────────
export default function UserProfileScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();

  const [profile, setProfile] = useState<PublicUserProfile | null>(null);
  const [watchlistCount, setWatchlistCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    if (!id) {
      setError('No user ID provided');
      setLoading(false);
      return;
    }

    // Guard: If id is not a valid UUID, don't call Supabase (prevents "invalid uuid" errors)
    if (!UUID_REGEX.test(id)) {
      console.warn('[UserProfile] Invalid UUID format:', id);
      setError('Collector not found');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const profileData = await dataProvider.getPublicUserProfile(id);
      setProfile(profileData);

      // Try to load watchlist count (best-effort)
      try {
        const watchlist = await dataProvider.listWatchlist(id);
        setWatchlistCount(watchlist.length);
      } catch {
        setWatchlistCount(null);
      }
    } catch (err: any) {
      console.warn('[UserProfile] loadProfile error:', err);
      setError(err?.message || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  // Error / Not found state
  if (error || !profile) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <View style={styles.centerContainer}>
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
          >
            <Text style={[styles.retryBtnText, { color: colors.text }]}>Go back</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  // Format collection value
  const formattedValue = profile.collectionValueEur
    ? `€${profile.collectionValueEur.toLocaleString()}`
    : null;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* ═══════════════════════════════════════════════════════════════════
            A) Profile Header Card
        ═══════════════════════════════════════════════════════════════════ */}
        <View style={[styles.profileCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <AvatarCircle name={profile.displayName} size={72} accentColor={colors.accent} />

          <View style={styles.profileInfo}>
            <Text style={[styles.displayName, { color: colors.text }]}>
              {profile.displayName}
            </Text>
            {profile.handle && (
              <Text style={[styles.handle, { color: colors.muted }]}>
                @{profile.handle}
              </Text>
            )}
          </View>

          {/* CTA Row */}
          <View style={styles.ctaRow}>
            <AnimatedPressable
              style={[styles.ctaBtn, styles.ctaBtnPrimary, { backgroundColor: colors.accent }]}
              onPress={() => {
                dataProvider
                  .requestDm(id!, '')
                  .then((result) => {
                    const threadId = typeof result === 'string' ? result : (result as any)?.thread_id;
                    if (threadId) {
                      router.push(`/chat/${threadId}`);
                    }
                  })
                  .catch(() => {
                    // DM not available
                  });
              }}
            >
              <Ionicons name="chatbubble-outline" size={16} color="#fff" />
              <Text style={styles.ctaBtnTextLight}>Message</Text>
            </AnimatedPressable>

            <AnimatedPressable
              style={[
                styles.ctaBtn,
                { backgroundColor: colors.background, borderColor: colors.border, borderWidth: 1 },
              ]}
              disabled
            >
              <Ionicons name="person-add-outline" size={16} color={colors.muted} />
              <Text style={[styles.ctaBtnText, { color: colors.muted }]}>Follow</Text>
            </AnimatedPressable>
          </View>
        </View>

        {/* ═══════════════════════════════════════════════════════════════════
            B) Stats Card (conditional - show if any stats available)
        ═══════════════════════════════════════════════════════════════════ */}
        {(profile.collectionCount !== null || watchlistCount !== null || formattedValue) && (
          <SectionCard title="Collector Stats" colors={colors}>
            <View style={styles.statsGrid}>
              {profile.collectionCount !== null && (
                <StatBox label="Items" value={profile.collectionCount} colors={colors} />
              )}
              {watchlistCount !== null && (
                <StatBox label="Watchlist" value={watchlistCount} colors={colors} />
              )}
              {formattedValue && (
                <StatBox label="Value" value={formattedValue} colors={colors} />
              )}
            </View>
          </SectionCard>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            C) Bio Card (conditional - show if bio exists)
        ═══════════════════════════════════════════════════════════════════ */}
        {profile.bio && (
          <SectionCard title="About" colors={colors}>
            <Text style={[styles.bioText, { color: colors.text }]}>{profile.bio}</Text>
          </SectionCard>
        )}

        {/* ═══════════════════════════════════════════════════════════════════
            D) Interests Card (conditional - show if interests exist)
        ═══════════════════════════════════════════════════════════════════ */}
        {profile.interests && profile.interests.length > 0 && (
          <SectionCard title="Interests" colors={colors}>
            <View style={styles.interestsRow}>
              {profile.interests.map((interest, idx) => (
                <View
                  key={idx}
                  style={[styles.interestPill, { backgroundColor: colors.background, borderColor: colors.border }]}
                >
                  <Text style={[styles.interestText, { color: colors.text }]}>{interest}</Text>
                </View>
              ))}
            </View>
          </SectionCard>
        )}

        {/* Bottom spacing */}
        <View style={{ height: 32 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles (square cards, consistent 16px padding)
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
    borderRadius: 0,
    borderWidth: 1,
  },
  retryBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },

  // Profile card (square)
  profileCard: {
    borderRadius: 0,
    borderWidth: 1,
    padding: 20,
    alignItems: 'center',
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
    marginTop: 12,
  },
  displayName: {
    fontSize: 20,
    fontWeight: '700',
  },
  handle: {
    fontSize: 14,
    marginTop: 2,
  },
  ctaRow: {
    flexDirection: 'row',
    marginTop: 16,
    gap: 12,
  },
  ctaBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 0,
    gap: 6,
  },
  ctaBtnPrimary: {},
  ctaBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },
  ctaBtnTextLight: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },

  // Section card (square)
  sectionCard: {
    borderRadius: 0,
    borderWidth: 1,
    padding: 16,
    marginTop: 16,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },

  // Stats (square)
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  statBox: {
    flex: 1,
    minWidth: 80,
    padding: 12,
    borderRadius: 0,
    borderWidth: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 11,
    marginTop: 2,
  },

  // Bio
  bioText: {
    fontSize: 14,
    lineHeight: 20,
  },

  // Interests (square pills)
  interestsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  interestPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 0,
    borderWidth: 1,
  },
  interestText: {
    fontSize: 13,
    fontWeight: '500',
  },
});
