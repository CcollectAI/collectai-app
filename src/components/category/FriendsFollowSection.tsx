/**
 * FriendsFollowSection — auto-rotating carousel of friends who follow this
 * category. Groups 4 avatars per slide so each slide shows a row.
 */

import React, { useCallback } from 'react';
import { View, Text, Image, StyleSheet, Share } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { inviteMessage } from '@/constants/storeLinks';
import { AnimatedPressable } from '@/motion';
import { AutoRotatingCarousel } from '@/components/AutoRotatingCarousel';
import type { MiniUserProfile } from '@/data';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  friends: MiniUserProfile[];
  onFriendPress: (userId: string) => void;
  colors: AppTheme['colors'];
};

// Invite (external share) + Find friends (in-app search) CTAs. Shown in both
// the empty and populated states so there's always a path to grow your circle.
const FriendsCtaRow: React.FC<{ colors: AppTheme['colors'] }> = ({ colors }) => {
  const router = useRouter();
  const onInvite = useCallback(() => {
    Share.share({ message: inviteMessage() }).catch(() => {});
  }, []);
  const onFind = useCallback(() => {
    // /search, NOT the marketplace tab. That tab renders <MemberMarketplace
    // asTab /> — a LISTINGS feed with no way to search for a person — so this
    // button could not do what it says. app/search.tsx is the unified search
    // over items, catalogue, COLLECTORS, events and categories.
    //
    // This is the 2026-08-10 bug in a second place: a search affordance that
    // opened the marketplace. The tab was fixed on 08-11 and these two CTAs
    // were missed, because the sweep looked at the tab, not at who pushed to
    // it. Push `/search`, never `/(tabs)/search`: check:params resolves a
    // target to its route FILE, and the tab wrapper has no
    // useLocalSearchParams, so pushing there makes the contract uncheckable.
    router.push('/search');
  }, [router]);
  return (
    <View style={styles.ctaRow}>
      <AnimatedPressable
        style={[styles.ctaBtn, { backgroundColor: colors.accent }]}
        onPress={onInvite} accessibilityRole="button" accessibilityLabel="Invite your friends"
      >
        <Ionicons name="share-outline" size={16} color="#fff" />
        <Text style={styles.ctaBtnText}>Invite friends</Text>
      </AnimatedPressable>
      <AnimatedPressable
        style={[styles.ctaBtnOutline, { borderColor: colors.accent }]}
        onPress={onFind} accessibilityRole="button" accessibilityLabel="Find friends to follow"
      >
        <Ionicons name="search" size={16} color={colors.accent} />
        <Text style={[styles.ctaBtnTextOutline, { color: colors.accent }]}>Find friends</Text>
      </AnimatedPressable>
    </View>
  );
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
}> = React.memo(function FriendAvatar({ profile, onPress, accentColor, textColor }) {
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
        <FriendsCtaRow colors={colors} />
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
      <FriendsCtaRow colors={colors} />
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
  ctaRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  ctaBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    height: 40,
    borderRadius: 10,
  },
  ctaBtnText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  ctaBtnOutline: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    height: 40,
    borderRadius: 10,
    borderWidth: 1,
  },
  ctaBtnTextOutline: { fontSize: 14, fontWeight: '600' },
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
