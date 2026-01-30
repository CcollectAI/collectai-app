/**
 * PublicUserProfileCard — displays public user profile from user_public_profile_v1.
 * Styled consistently with Event cards (same padding, radius, typography).
 * Privacy-safe: only shows fields from the public view.
 */
import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Image,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { PublicUserProfile } from '@/data';

// Event card colors (matching app/events/[eventId].tsx)
const CARD = '#020617';
const BORDER = '#1f2933';
const TEXT = '#e5e7eb';
const MUTED = '#9ca3af';
const PRIMARY = '#0ea5e9';

type Props = {
  profile: PublicUserProfile | null;
  loading?: boolean;
  onPress?: () => void;
};

const Avatar: React.FC<{ name: string; avatarUrl?: string | null }> = ({
  name,
  avatarUrl,
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
        style={styles.avatar}
        resizeMode="cover"
      />
    );
  }

  return (
    <View style={[styles.avatar, styles.avatarPlaceholder]}>
      <Text style={styles.avatarInitials}>{initials}</Text>
    </View>
  );
};

export const PublicUserProfileCard: React.FC<Props> = ({
  profile,
  loading,
  onPress,
}) => {
  if (loading) {
    return (
      <View style={styles.card}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={PRIMARY} />
          <Text style={styles.loadingText}>Loading profile...</Text>
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

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={onPress ? 0.7 : 1}
    >
      {/* Header: Avatar + Name */}
      <View style={styles.header}>
        <Avatar name={profile.displayName} avatarUrl={profile.avatarUrl} />
        <View style={styles.headerText}>
          <Text style={styles.displayName} numberOfLines={1}>
            {profile.displayName}
          </Text>
          {profile.handle && (
            <Text style={styles.handle} numberOfLines={1}>
              @{profile.handle}
            </Text>
          )}
        </View>
        {onPress && (
          <Ionicons name="chevron-forward" size={18} color={MUTED} />
        )}
      </View>

      {/* Bio */}
      {profile.bio && (
        <Text style={styles.bio} numberOfLines={3}>
          {profile.bio}
        </Text>
      )}

      {/* Interests as pills */}
      {profile.interests && profile.interests.length > 0 && (
        <View style={styles.interestsRow}>
          {profile.interests.slice(0, 4).map((interest, idx) => (
            <View key={idx} style={styles.interestPill}>
              <Text style={styles.interestText}>{interest}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Collection summary */}
      {(profile.collectionCount != null || profile.collectionValueEur != null) && (
        <View style={styles.statsRow}>
          {profile.collectionCount != null && (
            <View style={styles.statItem}>
              <Ionicons name="grid-outline" size={14} color={MUTED} />
              <Text style={styles.statText}>
                {profile.collectionCount} items
              </Text>
            </View>
          )}
          {profile.collectionValueEur != null && (
            <View style={styles.statItem}>
              <Ionicons name="trending-up-outline" size={14} color={MUTED} />
              <Text style={styles.statText}>
                {formatValue(profile.collectionValueEur)}
              </Text>
            </View>
          )}
        </View>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: BORDER,
    backgroundColor: CARD,
    padding: 12,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    gap: 8,
  },
  loadingText: {
    fontSize: 13,
    color: MUTED,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    marginRight: 10,
  },
  avatarPlaceholder: {
    backgroundColor: PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitials: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
  headerText: {
    flex: 1,
  },
  displayName: {
    fontSize: 14,
    fontWeight: '600',
    color: TEXT,
  },
  handle: {
    fontSize: 12,
    color: MUTED,
    marginTop: 1,
  },
  bio: {
    marginTop: 10,
    fontSize: 13,
    color: TEXT,
    lineHeight: 18,
  },
  interestsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 10,
    gap: 6,
  },
  interestPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: BORDER,
    backgroundColor: 'rgba(14, 165, 233, 0.1)',
  },
  interestText: {
    fontSize: 11,
    color: PRIMARY,
    fontWeight: '500',
  },
  statsRow: {
    flexDirection: 'row',
    marginTop: 10,
    gap: 16,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 12,
    color: MUTED,
  },
});

export default PublicUserProfileCard;
