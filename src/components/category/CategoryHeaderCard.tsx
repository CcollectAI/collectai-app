/**
 * CategoryHeaderCard — tiffany gradient banner per the redesign mockup
 * (web/category-redesign-preview.html `.cathead`), tuned to the app's brand
 * ramp (tokens.brand.base → darker — the mockup's #2C7873 endpoint read
 * off-palette next to the rest of the app). White text; Follow pill inverts
 * on the gradient: outline-white when idle, solid-white when following.
 *
 * Also hosts the Invite/Find friends CTAs (moved up from the old
 * FriendsFollowSection, which is gone): one banner owns all "grow your
 * circle around this category" actions.
 */
import React, { useCallback, useState } from 'react';
import { View, Text, StyleSheet, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';
import { inviteMessage } from '@/constants/storeLinks';
import { AnimatedPressable } from '@/motion';
import { colors as tokens } from '@/theme/tokens';
import { COMMUNITY_GATED, CATEGORY_FOLLOW_ENABLED } from '@/config/featureFlags';
import type { AppTheme } from '@/hooks/useAppTheme';
import CategoryCollectorSearch from './CategoryCollectorSearch';

type Props = {
  /** Slug. Needed for the per-category leaderboard route, not just display. */
  categoryId: string;
  categoryName: string;
  categoryTagline: string;
  following: boolean;
  onToggleFollow: () => void;
  colors: AppTheme['colors'];
};

const CategoryHeaderCard: React.FC<Props> = ({
  categoryId,
  categoryName,
  categoryTagline,
  following,
  onToggleFollow,
  colors,
}) => {
  const [searchOpen, setSearchOpen] = useState(false);
  const router = useRouter();

  const onInvite = useCallback(() => {
    Share.share({ message: inviteMessage() }).catch(() => {});
  }, []);

  // Inline collector search drops down in place instead of leaving for the
  // marketplace tab. Whole surface is gated by COMMUNITY_GATED below.
  const onFindFriends = useCallback(() => {
    setSearchOpen((v) => !v);
  }, []);
  const closeSearch = useCallback(() => setSearchOpen(false), []);

  return (
    <LinearGradient
      colors={[tokens.brand.base, tokens.brand.darker]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.headerCard}
    >
      <View style={styles.headerContent}>
        <Text style={styles.categoryName}>{categoryName}</Text>
        <Text style={styles.categoryTagline} numberOfLines={3}>
          {categoryTagline}
        </Text>
      </View>
      <View style={styles.actionsRow}>
        {CATEGORY_FOLLOW_ENABLED && (
          <AnimatedPressable
            style={[styles.pill, following && styles.pillActive]}
            onPress={onToggleFollow}
            accessibilityRole="button"
            accessibilityLabel={following ? `Unfollow ${categoryName}` : `Follow ${categoryName}`}
          >
            <Ionicons
              name={following ? 'checkmark' : 'add'}
              size={16}
              color={following ? tokens.brand.darker : '#fff'}
            />
            <Text style={[styles.pillText, following && styles.pillTextActive]}>
              {following ? 'Following' : 'Follow'}
            </Text>
          </AnimatedPressable>
        )}
        <AnimatedPressable
          style={styles.pill}
          onPress={onInvite}
          accessibilityRole="button"
          accessibilityLabel="Invite your friends"
        >
          <Ionicons name="share-outline" size={15} color="#fff" />
          <Text style={styles.pillText}>Invite friends</Text>
        </AnimatedPressable>
        {/* Per-category leaderboard. Ranks the collectors of THIS category by
            items owned or value held — not the XP board, which has no category
            dimension and is gated off. Sits beside Invite friends because both
            are "who else is here" actions. */}
        <AnimatedPressable
          style={styles.pill}
          onPress={() => router.push(`/leaderboard?categoryId=${encodeURIComponent(categoryId)}`)}
          accessibilityRole="button"
          accessibilityLabel={`See the ${categoryName} leaderboard`}
        >
          <Ionicons name="trophy-outline" size={15} color="#fff" />
          <Text style={styles.pillText}>Leaderboard</Text>
        </AnimatedPressable>
        {!COMMUNITY_GATED && (
          <AnimatedPressable
            style={[styles.pill, searchOpen && styles.pillActive]}
            onPress={onFindFriends}
            accessibilityRole="button"
            accessibilityState={{ expanded: searchOpen }}
            accessibilityLabel="Find friends to follow"
          >
            <Ionicons
              name="search"
              size={15}
              color={searchOpen ? tokens.brand.darker : '#fff'}
            />
            <Text style={[styles.pillText, searchOpen && styles.pillTextActive]}>
              Find friends
            </Text>
          </AnimatedPressable>
        )}
      </View>
      {!COMMUNITY_GATED && searchOpen && (
        <CategoryCollectorSearch colors={colors} onClose={closeSearch} />
      )}
    </LinearGradient>
  );
};

export default React.memo(CategoryHeaderCard);

const styles = StyleSheet.create({
  headerCard: {
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  headerContent: {
    marginBottom: 12,
  },
  categoryName: {
    fontSize: 20,
    fontWeight: '900',
    color: '#fff',
  },
  categoryTagline: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 18,
    color: '#fff',
    opacity: 0.9,
  },
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#fff',
  },
  pillActive: {
    backgroundColor: '#fff',
    borderColor: '#fff',
  },
  pillText: {
    marginLeft: 4,
    fontSize: 13,
    fontWeight: '600',
    color: '#fff',
  },
  pillTextActive: {
    color: tokens.brand.darker,
  },
});
