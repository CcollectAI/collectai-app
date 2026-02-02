/**
 * User Profile Screen — Pro-grade collector profile.
 * Route: /users/[id]
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

// UUID v4 regex for validation
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

// Format currency
const formatValue = (value: number) =>
  new Intl.NumberFormat('en-EU', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

export default function UserProfileScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();

  const [profile, setProfile] = useState<PublicUserProfile | null>(null);
  const [dmStatus, setDmStatus] = useState<string>('none');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestingDm, setRequestingDm] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!id) {
      setError('No user ID provided');
      setLoading(false);
      return;
    }

    // Skip UUID validation for mock IDs (collector-xxx format)
    const isMockId = id.startsWith('collector-');
    if (!isMockId && !UUID_REGEX.test(id)) {
      setError('Collector not found');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const profileData = await dataProvider.getPublicUserProfile(id);
      if (!profileData) {
        setError('Collector not found');
        return;
      }
      setProfile(profileData);

      // Check DM status
      try {
        const status = await dataProvider.getDmStatus(id);
        setDmStatus(status);
      } catch {
        setDmStatus('none');
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleMessage = async () => {
    if (!id || requestingDm) return;

    // If already connected, go to existing thread
    if (dmStatus === 'accepted') {
      // Find existing thread
      try {
        const threads = await dataProvider.listInboxThreads();
        const existing = threads.find((t) => t.otherUserId === id);
        if (existing) {
          router.push(`/chat/${existing.id}`);
          return;
        }
      } catch {}
    }

    // Request new DM
    setRequestingDm(true);
    try {
      const threadId = await dataProvider.requestDm(id, '');
      if (threadId) {
        router.push(`/chat/${threadId}`);
      }
    } catch (err) {
      console.warn('[UserProfile] requestDm error:', err);
    } finally {
      setRequestingDm(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <Header colors={colors} router={router} />
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (error || !profile) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
        <Header colors={colors} router={router} />
        <View style={styles.centerContainer}>
          <View style={[styles.errorIcon, { backgroundColor: colors.card }]}>
            <Ionicons name="person-outline" size={32} color={colors.muted} />
          </View>
          <Text style={[styles.errorTitle, { color: colors.text }]}>
            {error || 'Collector not found'}
          </Text>
          <Text style={[styles.errorSubtitle, { color: colors.muted }]}>
            This profile doesn't exist or is private.
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  const messageLabel =
    dmStatus === 'accepted' ? 'Message' :
    dmStatus === 'pending_outgoing' ? 'Pending' :
    dmStatus === 'pending_incoming' ? 'Respond' : 'Message';

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      <Header colors={colors} router={router} title={profile.displayName} />

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Card */}
        <View style={[styles.profileCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {/* Avatar + Name */}
          <View style={styles.avatarSection}>
            <Avatar
              name={profile.displayName}
              avatarUrl={profile.avatarUrl}
              size={88}
              accentColor={colors.accent}
            />
            <View style={styles.nameContainer}>
              <Text style={[styles.displayName, { color: colors.text }]}>
                {profile.displayName}
              </Text>
              {profile.handle && (
                <Text style={[styles.handle, { color: colors.muted }]}>
                  @{profile.handle}
                </Text>
              )}
            </View>
          </View>

          {/* Bio inline */}
          {profile.bio && (
            <Text style={[styles.bioText, { color: colors.text }]}>{profile.bio}</Text>
          )}

          {/* Stats Row */}
          <View style={[styles.statsRow, { borderColor: colors.border }]}>
            <StatItem
              value={profile.collectionCount ?? 0}
              label="Items"
              colors={colors}
            />
            <StatItem
              value={profile.collectionValueEur ? formatValue(profile.collectionValueEur) : '—'}
              label="Value"
              colors={colors}
            />
            <StatItem
              value={profile.interests?.length ?? 0}
              label="Categories"
              colors={colors}
            />
          </View>

          {/* Action Buttons */}
          <View style={styles.actionRow}>
            <AnimatedPressable
              style={[styles.actionBtn, styles.actionBtnPrimary, { backgroundColor: colors.accent }]}
              onPress={handleMessage}
              disabled={requestingDm || dmStatus === 'pending_outgoing'}
            >
              {requestingDm ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <>
                  <Ionicons name="chatbubble" size={16} color="#fff" />
                  <Text style={styles.actionBtnTextLight}>{messageLabel}</Text>
                </>
              )}
            </AnimatedPressable>

            <AnimatedPressable
              style={[styles.actionBtn, styles.actionBtnSecondary, { borderColor: colors.border }]}
              disabled
            >
              <Ionicons name="person-add-outline" size={16} color={colors.text} />
              <Text style={[styles.actionBtnText, { color: colors.text }]}>Follow</Text>
            </AnimatedPressable>
          </View>
        </View>

        {/* Interests Section */}
        {profile.interests && profile.interests.length > 0 && (
          <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.sectionTitle, { color: colors.muted }]}>Collects</Text>
            <View style={styles.interestsGrid}>
              {profile.interests.map((interest, idx) => (
                <View
                  key={idx}
                  style={[styles.interestChip, { backgroundColor: colors.background }]}
                >
                  <Ionicons name="pricetag" size={12} color={colors.accent} style={{ marginRight: 6 }} />
                  <Text style={[styles.interestText, { color: colors.text }]}>{interest}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Header Component
// ─────────────────────────────────────────────────────────────────────────────
function Header({ colors, router, title }: { colors: any; router: any; title?: string }) {
  return (
    <View style={[styles.header, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
      <AnimatedPressable onPress={() => router.back()} style={styles.backBtn}>
        <Ionicons name="chevron-back" size={24} color={colors.text} />
      </AnimatedPressable>
      <Text style={[styles.headerTitle, { color: colors.text }]} numberOfLines={1}>
        {title || 'Profile'}
      </Text>
      <View style={{ width: 32 }} />
    </View>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Avatar Component
// ─────────────────────────────────────────────────────────────────────────────
function Avatar({
  name,
  avatarUrl,
  size,
  accentColor,
}: {
  name: string;
  avatarUrl?: string | null;
  size: number;
  accentColor: string;
}) {
  const initials = name
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || '?';

  if (avatarUrl) {
    return (
      <View style={[styles.avatarRing, { borderColor: accentColor }]}>
        <Image
          source={{ uri: avatarUrl }}
          style={{ width: size, height: size, borderRadius: size / 2 }}
        />
      </View>
    );
  }

  return (
    <View style={[styles.avatarRing, { borderColor: accentColor }]}>
      <View
        style={[
          styles.avatarCircle,
          { width: size, height: size, borderRadius: size / 2, backgroundColor: accentColor },
        ]}
      >
        <Text style={[styles.avatarInitials, { fontSize: size * 0.36 }]}>{initials}</Text>
      </View>
    </View>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Stat Item Component
// ─────────────────────────────────────────────────────────────────────────────
function StatItem({
  value,
  label,
  colors,
}: {
  value: string | number;
  label: string;
  colors: any;
}) {
  return (
    <View style={styles.statItem}>
      <Text style={[styles.statValue, { color: colors.text }]}>{value}</Text>
      <Text style={[styles.statLabel, { color: colors.muted }]}>{label}</Text>
    </View>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  backBtn: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
    marginHorizontal: 8,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 24,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  errorIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  errorSubtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 6,
  },

  // Profile Card
  profileCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 20,
    marginBottom: 16,
  },

  // Avatar Section
  avatarSection: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  avatarRing: {
    borderWidth: 3,
    borderRadius: 48,
    padding: 2,
  },
  avatarCircle: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitials: {
    fontWeight: '700',
    color: '#fff',
  },
  nameContainer: {
    flex: 1,
    marginLeft: 16,
  },
  displayName: {
    fontSize: 22,
    fontWeight: '700',
  },
  handle: {
    fontSize: 14,
    marginTop: 2,
  },

  // Bio
  bioText: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },

  // Stats Row
  statsRow: {
    flexDirection: 'row',
    borderTopWidth: 1,
    paddingTop: 16,
    marginBottom: 16,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 11,
    marginTop: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },

  // Action Buttons - pill shape
  actionRow: {
    flexDirection: 'row',
    gap: 10,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 24,
    gap: 8,
  },
  actionBtnPrimary: {
    // backgroundColor set inline
  },
  actionBtnSecondary: {
    borderWidth: 1.5,
  },
  actionBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
  actionBtnTextLight: {
    fontSize: 15,
    fontWeight: '600',
    color: '#fff',
  },

  // Sections
  section: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
    marginBottom: 12,
  },

  // Interests
  interestsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  interestChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
  },
  interestText: {
    fontSize: 13,
    fontWeight: '500',
  },
});
