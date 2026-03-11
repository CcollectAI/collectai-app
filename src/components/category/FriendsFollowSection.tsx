import React from 'react';
import { View, Text, Image, ScrollView, StyleSheet } from 'react-native';
import { AnimatedPressable } from '@/motion';
import type { MiniUserProfile } from '@/data';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  friends: MiniUserProfile[];
  onFriendPress: (userId: string) => void;
  colors: AppTheme['colors'];
};

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
    <AnimatedPressable style={styles.friendCard} onPress={onPress} accessibilityRole="button" accessibilityLabel={`View ${profile.displayName}'s profile`}>
      {profile.avatarUrl ? (
        <Image source={{ uri: profile.avatarUrl }} style={styles.friendAvatar} accessibilityLabel={`${profile.displayName} avatar`} />
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

const FriendsFollowSection: React.FC<Props> = ({ friends, onFriendPress, colors }) => (
  <View style={styles.section}>
    <Text style={[styles.sectionTitle, { color: colors.text }]}>Friends Who Follow</Text>
    {friends.length === 0 ? (
      <Text style={[styles.emptyText, { color: colors.muted }]}>
        None of your friends follow this category yet.
      </Text>
    ) : (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.friendsRow}
      >
        {friends.map((friend) => (
          <FriendAvatar
            key={friend.id}
            profile={friend}
            onPress={() => onFriendPress(friend.id)}
            accentColor={colors.accent}
            textColor={colors.text}
          />
        ))}
      </ScrollView>
    )}
  </View>
);

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
    gap: 12,
  },
  friendCard: {
    alignItems: 'center',
    width: 64,
  },
  friendAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
  },
  friendAvatarPlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  friendInitials: {
    fontSize: 14,
    fontWeight: '700',
    color: '#fff',
  },
  friendName: {
    marginTop: 4,
    fontSize: 11,
    textAlign: 'center',
  },
});
