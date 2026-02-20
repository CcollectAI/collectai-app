/**
 * Category Store — Amazon Brand Store style layout for a category.
 * Shows: header, spotlight carousel, items, events, friends, sponsored slot.
 */
import React, { useEffect, useState, useRef } from 'react';
import {
  Alert,
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
  FlatList,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type CategoryStoreData, type Item, type MiniUserProfile, type CategoryMissingItem } from '@/data';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import logger from '@/utils/logger';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const kindIcon: Record<string, keyof typeof Ionicons.glyphMap> = {
  collection_drop: 'cube-outline',
  meetup: 'people-outline',
  stream: 'logo-twitch',
};

const kindLabel: Record<string, string> = {
  collection_drop: 'Drop',
  meetup: 'Meetup',
  stream: 'Stream',
};

// Avatar component for friends
const FriendAvatar: React.FC<{ profile: MiniUserProfile; onPress: () => void; accentColor: string; textColor: string }> = ({
  profile,
  onPress,
  accentColor,
  textColor,
}) => {
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
};

export default function CategoryStoreScreen() {
  const { categoryId } = useLocalSearchParams<{ categoryId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const [data, setData] = useState<CategoryStoreData | null>(null);
  const [missingItems, setMissingItems] = useState<CategoryMissingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [following, setFollowing] = useState(false);
  const [spotlightIndex, setSpotlightIndex] = useState(0);
  const [markingOwned, setMarkingOwned] = useState<string | null>(null);
  const [recentlyOwned, setRecentlyOwned] = useState<Set<string>>(new Set());

  const spotlightRef = useRef<FlatList>(null);

  useEffect(() => {
    if (!categoryId) return;

    setLoading(true);
    setError(null);

    // Load both category store data and missing items
    Promise.all([
      dataProvider.getCategoryStore(categoryId),
      dataProvider.listCategoryMissing(categoryId).catch(() => []), // Graceful fallback
    ])
      .then(([storeResult, missingResult]) => {
        if (storeResult) {
          setData(storeResult);
          setMissingItems(missingResult);
        } else {
          setError('Category not found');
        }
      })
      .catch((err) => {
        logger.warn('[CategoryStore] error:', err);
        setError(err?.message || 'Failed to load category');
      })
      .finally(() => setLoading(false));
  }, [categoryId]);

  // Load follow state
  useEffect(() => {
    if (!categoryId) return;
    dataProvider.isFollowingCategory(categoryId)
      .then(setFollowing)
      .catch(() => {}); // Non-critical
  }, [categoryId]);

  // Auto-rotate spotlight carousel
  useEffect(() => {
    if (!data || data.spotlightSlides.length <= 1) return;

    const interval = setInterval(() => {
      setSpotlightIndex((prev) => {
        const next = (prev + 1) % data.spotlightSlides.length;
        spotlightRef.current?.scrollToIndex({ index: next, animated: true });
        return next;
      });
    }, 4000);

    return () => clearInterval(interval);
  }, [data]);

  const handleItemPress = (item: Item) => {
    router.push({
      pathname: '/item/[id]',
      params: {
        id: item.id,
        name: item.name,
        category: item.category,
        value: String(item.price),
        imageUri: item.imageUrl || '',
      },
    });
  };

  const handleEventPress = (eventId: string) => {
    router.push(`/events/${encodeURIComponent(eventId)}`);
  };

  const handleFriendPress = (userId: string) => {
    router.push(`/users/${encodeURIComponent(userId)}`);
  };

  const handleToggleFollow = async () => {
    const newFollowing = !following;
    setFollowing(newFollowing);

    try {
      if (newFollowing) {
        await dataProvider.followCategory(categoryId!);
      } else {
        await dataProvider.unfollowCategory(categoryId!);
      }
    } catch (err) {
      // Revert on error
      setFollowing(!newFollowing);
      logger.warn('[Category] Follow toggle failed', err);
      Alert.alert('Error', 'Could not update follow status. Please try again.');
    }
  };

  const handleMarkOwned = async (itemId: string) => {
    setMarkingOwned(itemId);
    try {
      await dataProvider.markCategoryItemOwned(itemId);

      // Fire success haptic
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

      // Mark as recently owned for visual feedback
      setRecentlyOwned((prev) => new Set(prev).add(itemId));

      // Remove from missing items list after brief delay for animation
      setTimeout(() => {
        setMissingItems((prev) => prev.filter((item) => item.id !== itemId));
        setRecentlyOwned((prev) => {
          const next = new Set(prev);
          next.delete(itemId);
          return next;
        });
      }, 600);
    } catch (err: unknown) {
      logger.warn('[CategoryStore] markOwned error:', err);
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
    } finally {
      setMarkingOwned(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={[styles.headerRow, { backgroundColor: colors.background }]}>
          <AnimatedPressable onPress={() => router.back()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
        </View>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading category...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error / not found state
  if (error || !data) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={[styles.headerRow, { backgroundColor: colors.background }]}>
          <AnimatedPressable onPress={() => router.back()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </AnimatedPressable>
        </View>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.muted} />
          <Text style={[styles.errorTitle, { color: colors.text }]}>Category not found</Text>
          <Text style={[styles.errorSubtitle, { color: colors.muted }]}>
            This category doesn't exist or couldn't be loaded.
          </Text>
          <AnimatedPressable style={[styles.backButton, { borderColor: colors.border }]} onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Go back">
            <Text style={[styles.backButtonText, { color: colors.text }]}>Go back</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      {/* Header row with back button */}
      <View style={[styles.headerRow, { backgroundColor: colors.background }]}>
        <AnimatedPressable onPress={() => router.back()} style={styles.backBtn} accessibilityRole="button" accessibilityLabel="Go back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </AnimatedPressable>
      </View>

      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.contentContainer}
      >
        {/* 1. Category Header Card */}
        <View style={[styles.headerCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={styles.headerContent}>
            <Text style={[styles.categoryName, { color: colors.text }]}>{data.categoryName}</Text>
            <Text style={[styles.categoryTagline, { color: colors.muted }]} numberOfLines={3}>
              {data.categoryTagline}
            </Text>
          </View>
          <AnimatedPressable
            style={[
              styles.followButton,
              { borderColor: colors.accent },
              following && { backgroundColor: colors.accent },
            ]}
            onPress={handleToggleFollow}
            accessibilityRole="button"
            accessibilityLabel={following ? `Unfollow ${data.categoryName}` : `Follow ${data.categoryName}`}
          >
            <Ionicons
              name={following ? 'checkmark' : 'add'}
              size={16}
              color={following ? '#fff' : colors.accent}
            />
            <Text
              style={[
                styles.followButtonText,
                { color: colors.accent },
                following && { color: '#fff' },
              ]}
            >
              {following ? 'Following' : 'Follow'}
            </Text>
          </AnimatedPressable>
        </View>

      {/* 2. Spotlight Carousel */}
      {data.spotlightSlides.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Spotlight</Text>
          <FlatList
            ref={spotlightRef}
            data={data.spotlightSlides}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            keyExtractor={(slide) => slide.id}
            onMomentumScrollEnd={(e) => {
              const index = Math.round(e.nativeEvent.contentOffset.x / (SCREEN_WIDTH - 32));
              setSpotlightIndex(index);
            }}
            renderItem={({ item: slide }) => (
              <View style={[styles.spotlightSlide, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {slide.imageUrl ? (
                  <View style={styles.spotlightImageWrap}>
                    <Image source={{ uri: slide.imageUrl }} style={styles.spotlightImage} />
                    <View style={styles.spotlightImageOverlay} />
                  </View>
                ) : (
                  <View style={[styles.spotlightImagePlaceholder, { backgroundColor: colors.background }]}>
                    <Ionicons name="sparkles" size={32} color={colors.accent} />
                  </View>
                )}
                <Text style={[styles.spotlightTitle, { color: colors.text }]}>{slide.title}</Text>
                {slide.subtitle && (
                  <Text style={[styles.spotlightSubtitle, { color: colors.muted }]}>{slide.subtitle}</Text>
                )}
              </View>
            )}
          />
          {/* Dots indicator */}
          {data.spotlightSlides.length > 1 && (
            <View style={styles.dotsRow}>
              {data.spotlightSlides.map((_, idx) => (
                <View
                  key={idx}
                  style={[
                    styles.dot,
                    { backgroundColor: colors.border },
                    idx === spotlightIndex && { backgroundColor: colors.accent },
                  ]}
                />
              ))}
            </View>
          )}
        </View>
      )}

      {/* 3. Items in this Category */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Items in {data.categoryName}</Text>
        {data.items.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>No items yet in this category.</Text>
        ) : (
          data.items.slice(0, 6).map((item) => (
            <AnimatedPressable
              key={item.id}
              style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => handleItemPress(item)}
              accessibilityRole="button"
              accessibilityLabel={`${item.name}, ${formatPrice(item.price)}`}
            >
              <View style={styles.itemInfo}>
                <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={[styles.itemCategory, { color: colors.muted }]}>{item.category}</Text>
              </View>
              <Text style={[styles.itemPrice, { color: colors.text }]}>{formatPrice(item.price)}</Text>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </AnimatedPressable>
          ))
        )}
        {data.items.length > 6 && (
          <AnimatedPressable
            style={styles.seeAllButton}
            onPress={() =>
              router.push({
                pathname: '/(tabs)/items',
                params: { category: data.categoryName },
              })
            }
            accessibilityRole="link"
            accessibilityLabel={`See all ${data.items.length} items`}
          >
            <Text style={[styles.seeAllText, { color: colors.accent }]}>
              See all {data.items.length} items
            </Text>
            <Ionicons name="arrow-forward" size={14} color={colors.accent} />
          </AnimatedPressable>
        )}
      </View>

      {/* 4. Upcoming Events / Drops */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Upcoming Events & Drops</Text>
        {data.upcomingEvents.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>No upcoming events for this category.</Text>
        ) : (
          data.upcomingEvents.map((event) => (
            <AnimatedPressable
              key={event.id}
              style={[styles.eventCard, { backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={() => handleEventPress(event.id)}
              accessibilityRole="button"
              accessibilityLabel={`${event.title}, ${kindLabel[event.kind] || event.kind}, ${event.date}`}
            >
              <View
                style={[
                  styles.eventIconBubble,
                  { backgroundColor: colors.accent },
                ]}
              >
                <Ionicons
                  name={kindIcon[event.kind] || 'calendar-outline'}
                  size={18}
                  color="#fff"
                />
              </View>
              <View style={styles.eventInfo}>
                <Text style={[styles.eventTitle, { color: colors.text }]} numberOfLines={1}>
                  {event.title}
                </Text>
                <Text style={[styles.eventMeta, { color: colors.muted }]}>
                  {kindLabel[event.kind] || event.kind} · {event.date}
                  {event.time ? ` · ${event.time}` : ''}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </AnimatedPressable>
          ))
        )}
      </View>

      {/* 4.5. Missing Items Checklist - above Friends */}
      {missingItems.length > 0 && (
        <View style={[styles.missingCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={styles.missingCardHeader}>
            <Text style={[styles.missingCardTitle, { color: colors.text }]}>
              Complete Your Collection
            </Text>
            <Text style={[styles.missingCardCount, { color: colors.muted }]}>
              {missingItems.length} left
            </Text>
          </View>
          {missingItems.slice(0, 3).map((item) => {
            const isOwned = recentlyOwned.has(item.id);
            const isMarking = markingOwned === item.id;

            return (
              <View
                key={item.id}
                style={[
                  styles.missingChecklistRow,
                  { borderBottomColor: colors.border },
                ]}
              >
                <View
                  style={[
                    styles.missingCheckbox,
                    { borderColor: isOwned ? colors.accent : colors.border },
                    isOwned && { backgroundColor: colors.accent },
                  ]}
                >
                  {isOwned && <Ionicons name="checkmark" size={12} color="#fff" />}
                </View>
                <View style={styles.missingInfo}>
                  <Text
                    style={[
                      styles.missingTitle,
                      { color: isOwned ? colors.muted : colors.text },
                      isOwned && styles.missingTitleOwned,
                    ]}
                    numberOfLines={1}
                  >
                    {item.title}
                  </Text>
                  {item.brand && (
                    <Text style={[styles.missingBrand, { color: colors.muted }]} numberOfLines={1}>
                      {item.brand}
                    </Text>
                  )}
                </View>
                <AnimatedPressable
                  style={[
                    styles.missingAddBtn,
                    {
                      backgroundColor: isOwned ? 'transparent' : colors.accent,
                    },
                  ]}
                  disabled={isMarking || isOwned}
                  onPress={() => handleMarkOwned(item.id)}
                  accessibilityRole="button"
                  accessibilityLabel={isOwned ? `${item.title} marked as owned` : `Add ${item.title}`}
                >
                  {isMarking ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : isOwned ? (
                    <Text style={[styles.missingAddBtnText, { color: colors.accent }]}>Added</Text>
                  ) : (
                    <Text style={styles.missingAddBtnText}>Add</Text>
                  )}
                </AnimatedPressable>
              </View>
            );
          })}
          {missingItems.length > 3 && (
            <AnimatedPressable style={styles.missingFooter}>
              <Text style={[styles.seeMore, { color: colors.accent }]}>
                +{missingItems.length - 3} more to collect
              </Text>
            </AnimatedPressable>
          )}
        </View>
      )}

      {/* 5. Friends Who Follow */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Friends Who Follow</Text>
        {data.friendsWhoFollow.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            None of your friends follow this category yet.
          </Text>
        ) : (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.friendsRow}
          >
            {data.friendsWhoFollow.map((friend) => (
              <FriendAvatar
                key={friend.id}
                profile={friend}
                onPress={() => handleFriendPress(friend.id)}
                accentColor={colors.accent}
                textColor={colors.text}
              />
            ))}
          </ScrollView>
        )}
      </View>

      {/* Bottom spacing */}
      <View style={{ height: 32 }} />
    </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  container: {
    flex: 1,
  },
  contentContainer: {
    paddingHorizontal: 16,
    paddingTop: 0,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 4,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  errorTitle: {
    marginTop: 12,
    fontSize: 16,
    fontWeight: '600',
  },
  errorSubtitle: {
    marginTop: 4,
    fontSize: 13,
    textAlign: 'center',
  },
  backButton: {
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
  },
  backButtonText: {
    fontSize: 13,
    fontWeight: '500',
  },

  // Header card
  headerCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  headerContent: {
    marginBottom: 12,
  },
  categoryName: {
    fontSize: 20,
    fontWeight: '700',
  },
  categoryTagline: {
    marginTop: 4,
    fontSize: 13,
    lineHeight: 18,
  },
  followButton: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
  },
  followButtonText: {
    marginLeft: 4,
    fontSize: 13,
    fontWeight: '600',
  },

  // Sections
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  sectionCount: {
    fontSize: 13,
    fontWeight: '500',
  },
  emptyText: {
    fontSize: 13,
  },

  // Missing items checklist card
  missingCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 20,
  },
  missingCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  missingCardTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  missingCardCount: {
    fontSize: 13,
    fontWeight: '500',
  },
  missingChecklistRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  missingCheckbox: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  missingInfo: {
    flex: 1,
  },
  missingTitle: {
    fontSize: 14,
    fontWeight: '500',
  },
  missingTitleOwned: {
    textDecorationLine: 'line-through',
  },
  missingBrand: {
    fontSize: 12,
    marginTop: 2,
  },
  missingAddBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
    marginLeft: 8,
  },
  missingAddBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  missingFooter: {
    paddingTop: 10,
  },
  seeMore: {
    fontSize: 13,
    fontWeight: '500',
    textAlign: 'center',
  },

  // Spotlight carousel
  spotlightSlide: {
    width: SCREEN_WIDTH - 32,
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    alignItems: 'center',
  },
  spotlightImageWrap: {
    width: '100%',
    height: 100,
    borderRadius: 12,
    overflow: 'hidden',
    marginBottom: 12,
  },
  spotlightImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  spotlightImageOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.15)',
  },
  spotlightImagePlaceholder: {
    width: '100%',
    height: 100,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  spotlightTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  spotlightSubtitle: {
    marginTop: 2,
    fontSize: 12,
    textAlign: 'center',
  },
  dotsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 10,
    gap: 6,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },

  // Items
  itemCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    marginBottom: 8,
  },
  itemInfo: {
    flex: 1,
    marginRight: 8,
  },
  itemName: {
    fontSize: 14,
    fontWeight: '600',
  },
  itemCategory: {
    fontSize: 12,
    marginTop: 2,
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '700',
    marginRight: 8,
  },
  seeAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    gap: 4,
  },
  seeAllText: {
    fontSize: 13,
    fontWeight: '600',
  },

  // Events
  eventCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    marginBottom: 8,
  },
  eventIconBubble: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  eventInfo: {
    flex: 1,
    marginRight: 8,
  },
  eventTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  eventMeta: {
    fontSize: 11,
    marginTop: 2,
  },

  // Friends
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

  // Sponsored
  sponsoredCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  sponsoredLabel: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  sponsoredPlaceholder: {
    height: 60,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  sponsoredText: {
    fontSize: 12,
  },
});
