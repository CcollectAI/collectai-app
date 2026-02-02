/**
 * PublicUserProfileCard — displays public user profile from user_public_profile_v1.
 * Styled consistently with the app theme using useAppTheme.
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
import { useAppTheme } from '@/hooks/useAppTheme';

type Props = {
  profile: PublicUserProfile | null;
  loading?: boolean;
  onPress?: () => void;
};

const Avatar: React.FC<{ name: string; avatarUrl?: string | null; accentColor: string }> = ({
  name,
  avatarUrl,
  accentColor,
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
    <View style={[styles.avatar, styles.avatarPlaceholder, { backgroundColor: accentColor }]}>
      <Text style={styles.avatarInitials}>{initials}</Text>
    </View>
  );
};

export const PublicUserProfileCard: React.FC<Props> = ({
  profile,
  loading,
  onPress,
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

  return (
    <TouchableOpacity
      style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={onPress ? 0.7 : 1}
    >
      {/* Header: Avatar + Name */}
      <View style={styles.header}>
        <Avatar name={profile.displayName} avatarUrl={profile.avatarUrl} accentColor={colors.accent} />
        <View style={styles.headerText}>
          <Text style={[styles.displayName, { color: colors.text }]} numberOfLines={1}>
            {profile.displayName}
          </Text>
          {profile.handle && (
            <Text style={[styles.handle, { color: colors.muted }]} numberOfLines={1}>
              @{profile.handle}
            </Text>
          )}
        </View>
        {onPress && (
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        )}
      </View>

      {/* Bio */}
      {profile.bio && (
        <Text style={[styles.bio, { color: colors.text }]} numberOfLines={3}>
          {profile.bio}
        </Text>
      )}

      {/* Interests as pills */}
      {profile.interests && profile.interests.length > 0 && (
        <View style={styles.interestsRow}>
          {profile.interests.slice(0, 4).map((interest, idx) => (
            <View key={idx} style={[styles.interestPill, { borderColor: colors.border, backgroundColor: `${colors.accent}15` }]}>
              <Text style={[styles.interestText, { color: colors.accent }]}>{interest}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Collection summary */}
      {(profile.collectionCount != null || profile.collectionValueEur != null) && (
        <View style={styles.statsRow}>
          {profile.collectionCount != null && (
            <View style={styles.statItem}>
              <Ionicons name="grid-outline" size={14} color={colors.muted} />
              <Text style={[styles.statText, { color: colors.muted }]}>
                {profile.collectionCount} items
              </Text>
            </View>
          )}
          {profile.collectionValueEur != null && (
            <View style={styles.statItem}>
              <Ionicons name="trending-up-outline" size={14} color={colors.muted} />
              <Text style={[styles.statText, { color: colors.muted }]}>
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
  },
  handle: {
    fontSize: 12,
    marginTop: 1,
  },
  bio: {
    marginTop: 10,
    fontSize: 13,
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
  },
  interestText: {
    fontSize: 11,
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
  },
});

export default PublicUserProfileCard;
