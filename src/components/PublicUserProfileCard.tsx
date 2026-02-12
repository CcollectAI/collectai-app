/**
 * PublicUserProfileCard — displays public user profile from user_public_profile_v1.
 * Styled consistently with the app theme using useAppTheme.
 * Privacy-safe: only shows fields from the public view.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { Image } from 'expo-image';
import { Ionicons } from '@expo/vector-icons';
import type { PublicUserProfile } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

type Props = {
  profile: PublicUserProfile | null;
  loading?: boolean;
  onPress?: () => void;
  onConnect?: () => void;
};

const Avatar: React.FC<{ name: string; avatarUrl?: string | null; accentColor: string; size?: number }> = ({
  name,
  avatarUrl,
  accentColor,
  size = 56,
}) => {
  const initials = name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || '?';

  if (avatarUrl) {
    return (
      <Image
        source={{ uri: avatarUrl }}
        style={[styles.avatar, { width: size, height: size, borderRadius: size / 2 }]}
        contentFit="cover"
        cachePolicy="disk"
        transition={150}
      />
    );
  }

  return (
    <View style={[styles.avatar, styles.avatarPlaceholder, { backgroundColor: accentColor, width: size, height: size, borderRadius: size / 2 }]}>
      <Text style={[styles.avatarInitials, { fontSize: size * 0.35 }]}>{initials}</Text>
    </View>
  );
};

export const PublicUserProfileCard: React.FC<Props> = ({
  profile,
  loading,
  onPress,
  onConnect,
}) => {
  const { colors } = useAppTheme();

  if (loading) {
    return (
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading profile...</Text>
        </View>
      </View>
    );
  }

  if (!profile) {
    return null;
  }

  const formatValue = (value: number) => {
    if (value >= 1000) {
      return `€${(value / 1000).toFixed(1)}k`;
    }
    return `€${value}`;
  };

  const CardWrapper = onPress ? AnimatedPressable : View;
  const cardProps = onPress ? { onPress } : {};

  return (
    <CardWrapper
      {...cardProps}
      style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
    >
      {/* Top section: Avatar + Info + Actions */}
      <View style={styles.topSection}>
        <Avatar name={profile.displayName} avatarUrl={profile.avatarUrl} accentColor={colors.accent} size={56} />

        <View style={styles.infoSection}>
          <View style={styles.nameRow}>
            <Text style={[styles.displayName, { color: colors.text }]} numberOfLines={1}>
              {profile.displayName}
            </Text>
            {onPress && (
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            )}
          </View>

          {profile.handle && (
            <Text style={[styles.handle, { color: colors.muted }]} numberOfLines={1}>
              @{profile.handle}
            </Text>
          )}

          {/* Stats inline */}
          <View style={styles.statsInline}>
            {profile.collectionCount != null && (
              <View style={styles.statItem}>
                <Ionicons name="grid-outline" size={12} color={colors.accent} />
                <Text style={[styles.statText, { color: colors.text }]}>
                  {profile.collectionCount}
                </Text>
              </View>
            )}
            {profile.collectionValueEur != null && (
              <View style={styles.statItem}>
                <Ionicons name="trending-up-outline" size={12} color={colors.accent} />
                <Text style={[styles.statText, { color: colors.text }]}>
                  {formatValue(profile.collectionValueEur)}
                </Text>
              </View>
            )}
          </View>
        </View>
      </View>

      {/* Bio */}
      {profile.bio && (
        <Text style={[styles.bio, { color: colors.text }]} numberOfLines={2}>
          {profile.bio}
        </Text>
      )}

      {/* Interests as pills */}
      {profile.interests && profile.interests.length > 0 && (
        <View style={styles.interestsRow}>
          {profile.interests.slice(0, 4).map((interest, idx) => (
            <View key={idx} style={[styles.interestPill, { backgroundColor: `${colors.accent}15`, borderColor: `${colors.accent}30` }]}>
              <Text style={[styles.interestText, { color: colors.accent }]}>{interest}</Text>
            </View>
          ))}
          {profile.interests.length > 4 && (
            <View style={[styles.interestPill, { backgroundColor: colors.background, borderColor: colors.border }]}>
              <Text style={[styles.interestText, { color: colors.muted }]}>+{profile.interests.length - 4}</Text>
            </View>
          )}
        </View>
      )}

      {/* Connect button (optional) */}
      {onConnect && (
        <AnimatedPressable
          onPress={onConnect}
          accessibilityRole="button"
          accessibilityLabel={`Connect with ${profile.displayName}`}
          style={[styles.connectBtn, { backgroundColor: colors.accent }]}
        >
          <Ionicons name="chatbubble-ellipses-outline" size={16} color="#ffffff" />
          <Text style={styles.connectBtnText}>Connect</Text>
        </AnimatedPressable>
      )}
    </CardWrapper>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    gap: 10,
  },
  loadingText: {
    fontSize: 14,
  },
  topSection: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  avatar: {
    marginRight: 14,
  },
  avatarPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitials: {
    fontWeight: '700',
    color: '#ffffff',
  },
  infoSection: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  displayName: {
    fontSize: 16,
    fontWeight: '700',
    flex: 1,
  },
  handle: {
    fontSize: 13,
    marginTop: 2,
  },
  statsInline: {
    flexDirection: 'row',
    marginTop: 8,
    gap: 16,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 13,
    fontWeight: '600',
  },
  bio: {
    marginTop: 12,
    fontSize: 14,
    lineHeight: 20,
  },
  interestsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 12,
    gap: 6,
  },
  interestPill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 12,
    borderWidth: 1,
  },
  interestText: {
    fontSize: 12,
    fontWeight: '500',
  },
  connectBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    marginTop: 14,
    gap: 6,
  },
  connectBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
  },
});

export default PublicUserProfileCard;
