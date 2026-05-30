/**
 * FriendsFollowSection — auto-rotating carousel of friends who follow this
 * category. Groups 4 avatars per slide so each slide shows a row.
 */

import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { AnimatedPressable } from '@/motion';
import { AutoRotatingCarousel } from '@/components/AutoRotatingCarousel';
import type { MiniUserProfile } from '@/data';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  friends: MiniUserProfile[];
  onFriendPress: (userId: string) => void;
  colors: AppTheme['colors'];
};

const PER_SLIDE = 4;

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

const FriendAvatar: React.FC<{
  profile: MiniUserProfile;
  onPress: () => void;
  accentColor: string;
  textColor: string;
}> = React.memo(({ profile, onPress, accentColor, textColor }) => {
  const initials = profile.displayName
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <AnimatedPressable
      style={styles.friendCard}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`View ${profile.displayName}'s profile`}
    >
      {profile.avatarUrl ? (
        <Image
          source={{ uri: profile.avatarUrl }}
          style={styles.friendAvatar}
          accessibilityLabel={`${profile.displayName} avatar`}
        />
      ) : (
        <View
          style={[
            styles.friendAvatar,
            styles.friendAvatarPlaceholder,
            { backgroundColor: profile.avatarColor || accentColor },
          ]}
        >
          <Text style={styles.friendInitials}>{initials}</Text>
        </View>
      )}
      <Text style={[styles.friendName, { color: textColor }]} numberOfLines={1}>
        {profile.displayName}
      </Text>
    </AnimatedPressable>
  );
});

const FriendsFollowSection: React.FC<Props> = ({ friends, onFriendPress, colors }) => {
  if (friends.length === 0) {
    return (
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Friends Who Follow</Text>
        <Text style={[styles.emptyText, { color: colors.muted }]}>
          None of your friends follow this category yet.
        </Text>
      </View>
    );
  }

  const slides = chunk(friends, PER_SLIDE);

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>Friends Who Follow</Text>
      <AutoRotatingCarousel intervalMs={6000} horizontalInset={16}>
        {slides.map((group, gi) => (
          <View key={`group-${gi}`} style={styles.friendsRow}>
            {group.map((friend) => (
              <FriendAvatar
                key={friend.id}
                profile={friend}
                onPress={() => onFriendPress(friend.id)}
                accentColor={colors.accent}
                textColor={colors.text}
              />
            ))}
          </View>
        ))}
      </AutoRotatingCarousel>
    </View>
  );
};

export default React.memo(FriendsFollowSection);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 13,
  },
  friendsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'flex-start',
    paddingHorizontal: 8,
  },
  friendCard: {
    alignItems: 'center',
    width: 72,
  },
  friendAvatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
  },
  friendAvatarPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  friendInitials: {
    fontSize: 16,
    fontWeight: '700',
    color: '#fff',
  },
  friendName: {
    marginTop: 6,
    fontSize: 11,
    textAlign: 'center',
  },
});
