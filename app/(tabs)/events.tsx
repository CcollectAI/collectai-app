/**
 * Events Tab — Collection drops, meetups, and Twitch streams.
 * Follows the same styling pattern as other tab pages.
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  ScrollView,
  SectionList,
  StyleSheet,
  Animated,
  Alert,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import type { CollectorsEvent } from '@/data/events';
import { useOptimisticRsvpList } from '@/hooks/useOptimisticRsvp';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
import { CountdownBadge } from '@/components/EventCountdown';
import { CATEGORIES as ALL_CATS } from '@/constants/categories';
import calendar, { parseEventDate, getCountdown } from '@/lib/calendar';
import logger from '@/utils/logger';

const kindLabel: Record<CollectorsEvent['kind'], string> = {
  collection_drop: 'Collection drop',
  meetup: 'Meetup',
  stream: 'Twitch stream',
  convention: 'Convention',
  release: 'New release',
};

const kindIcon: Record<CollectorsEvent['kind'], keyof typeof Ionicons.glyphMap> = {
  collection_drop: 'cube-outline',
  meetup: 'people-outline',
  stream: 'logo-twitch',
  convention: 'map-outline',
  release: 'rocket-outline',
};

function EventsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const [refreshing, setRefreshing] = useState(false);
  const [followedCategories, setFollowedCategories] = useState<string[]>([]);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  // Paginated data fetching
  const eventFetcher = useCallback(
    async (limit: number, offset: number): Promise<CollectorsEvent[]> => {
      return dataProvider.listEvents({ limit, offset });
    },
    [],
  );

  const {
    items: events,
    isLoading: loading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    refresh: paginatedRefresh,
    setItems: setEvents,
  } = usePaginatedList<CollectorsEvent>(eventFetcher, { pageSize: 20 });

  useEffect(() => {
    dataProvider.listFollowedCategories().then(setFollowedCategories).catch((err) => { logger.warn('[Events] Failed to load followed categories', err); });
  }, []);

  const now = new Date();
  const upcomingEvents = events.filter((e) => {
    const eventDate = parseEventDate(e.date, e.time);
    return eventDate >= now;
  });
  const pastEvents = events.filter((e) => {
    const eventDate = parseEventDate(e.date, e.time);
    return eventDate < now;
  });

  const filteredUpcoming = activeFilter
    ? upcomingEvents.filter((e) => e.categoryId === activeFilter)
    : upcomingEvents;
  const filteredPast = activeFilter
    ? pastEvents.filter((e) => e.categoryId === activeFilter)
    : pastEvents;

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await paginatedRefresh();
    setRefreshing(false);
  }, [paginatedRefresh]);

  // SectionList sections for upcoming + past events
  const sections = useMemo(() => {
    const result: { title: string; isPast: boolean; data: CollectorsEvent[] }[] = [];
    if (filteredUpcoming.length > 0) {
      result.push({ title: `Upcoming (${filteredUpcoming.length})`, isPast: false, data: filteredUpcoming });
    }
    if (filteredPast.length > 0) {
      result.push({ title: `Past Events (${filteredPast.length})`, isPast: true, data: filteredPast });
    }
    return result;
  }, [filteredUpcoming, filteredPast]);

  // Optimistic RSVP: toggles attendance state immediately, reverts on error
  const optimisticRsvp = useOptimisticRsvpList(setEvents, paginatedRefresh);

  const handleAttend = async (event: CollectorsEvent) => {
    // Optimistic update: toggle attendance state immediately
    await optimisticRsvp.mutate({
      eventId: event.id,
      currentlyAttending: !!event.isAttending,
    });

    // If RSVP succeeded and user is now attending, silently add to calendar
    if (!event.isAttending && !optimisticRsvp.error) {
      try {
        const eventDate = parseEventDate(event.date, event.time);
        await calendar.addToCalendar({
          eventId: event.id,
          title: event.title,
          startDate: eventDate,
          location: event.location,
          notes: `CollectAI Event: ${kindLabel[event.kind]}`,
        });
      } catch (calErr) {
        // Calendar add is non-critical; don't fail the RSVP for this
        logger.warn('[EventsScreen] calendar add error:', calErr);
      }
    }
  };

  const handleSetReminder = async (event: CollectorsEvent) => {
    const eventDate = parseEventDate(event.date, event.time);
    const countdown = getCountdown(eventDate);

    if (countdown.isPast) {
      Alert.alert('Event Ended', 'This event has already passed.');
      return;
    }

    const reminderDate = new Date(eventDate.getTime() - 60 * 60 * 1000);
    if (reminderDate < new Date()) {
      reminderDate.setTime(Date.now() + 60 * 1000);
    }

    const result = await calendar.scheduleReminder({
      eventId: event.id,
      title: `Upcoming: ${event.title}`,
      body: `${kindLabel[event.kind]} starts in 1 hour!`,
      triggerDate: reminderDate,
    });

    if (result.success) {
      Alert.alert('Reminder Set', `You'll be notified before "${event.title}".`);
    } else if (result.error !== 'Permission denied') {
      Alert.alert('Error', result.error || 'Could not set reminder.');
    }
  };

  const renderEventCard = (event: CollectorsEvent, showActions = true) => {
    const metaLine = [
      kindLabel[event.kind],
      event.date + (event.time ? ` — ${event.time}` : ''),
    ]
      .filter(Boolean)
      .join(' • ');

    const eventDate = parseEventDate(event.date, event.time);
    const isPast = eventDate < now;

    return (
      <AnimatedPressable
        key={event.id}
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          router.push(`/events/${encodeURIComponent(event.id)}`);
        }}
        style={[
          styles.eventCard,
          {
            backgroundColor: colors.card,
            borderColor: isPast ? colors.border : colors.accent + '40',
          },
        ]}
        accessibilityRole="button"
        accessibilityLabel={`${event.title}, ${kindLabel[event.kind]}, ${event.date}`}
      >
        <View style={styles.eventHeader}>
          <View
            style={[
              styles.eventIcon,
              { backgroundColor: isPast ? colors.muted + '80' : colors.accent },
            ]}
          >
            <Ionicons name={kindIcon[event.kind]} size={20} color="#ffffff" />
          </View>

          <View style={styles.eventInfo}>
            <View style={styles.eventTitleRow}>
              <Text
                style={[styles.eventTitle, { color: isPast ? colors.muted : colors.text }]}
                numberOfLines={1}
              >
                {event.title}
              </Text>
              <CountdownBadge
                date={event.date}
                time={event.time}
                colors={{ text: colors.text, muted: colors.muted, accent: colors.accent }}
              />
            </View>
            <Text
              style={[styles.eventMeta, { color: colors.muted }]}
              numberOfLines={1}
            >
              {metaLine}
            </Text>
            {event.attendeeCount != null && event.attendeeCount > 0 && (
              <Text style={[styles.attendeeCountText, { color: colors.muted }]}>
                {event.attendeeCount} attending
              </Text>
            )}
            {event.location && (
              <Text
                style={[styles.eventLocation, { color: colors.muted }]}
                numberOfLines={1}
              >
                {event.location}
              </Text>
            )}
          </View>

          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </View>

        {showActions && !isPast && (
          <View style={[styles.eventActions, { borderTopColor: colors.border }]}>
            <AnimatedPressable
              style={[styles.actionBtn, { borderColor: event.isAttending ? colors.accent : colors.border }]}
              onPress={(e) => {
                e.stopPropagation();
                fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
                handleAttend(event);
              }}
              accessibilityRole="button"
              accessibilityLabel={event.isAttending ? 'Cancel attendance' : 'Attend event'}
            >
              <Ionicons
                name={event.isAttending ? 'checkmark-circle' : 'person-add-outline'}
                size={16}
                color={event.isAttending ? colors.accent : colors.text}
              />
              <Text style={[styles.actionBtnText, { color: event.isAttending ? colors.accent : colors.text }]}>
                {event.isAttending ? 'Going' : 'Attend'}
              </Text>
            </AnimatedPressable>

            <AnimatedPressable
              style={[styles.actionBtn, { borderColor: colors.border }]}
              onPress={(e) => {
                e.stopPropagation();
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                handleSetReminder(event);
              }}
              accessibilityRole="button"
              accessibilityLabel="Set reminder for event"
            >
              <Ionicons name="notifications-outline" size={16} color={colors.accent} />
              <Text style={[styles.actionBtnText, { color: colors.text }]}>
                Set Reminder
              </Text>
            </AnimatedPressable>
          </View>
        )}
      </AnimatedPressable>
    );
  };

  const headerElement = (
    <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
      {/* Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Text style={[styles.headerTitle, { color: colors.text }]}>
            Events
          </Text>
          <Text style={[styles.headerSubtitle, { color: colors.muted }]}>
            Collection drops, meetups, and streams.
          </Text>
        </View>
        <View style={styles.headerIcons}>
          <InboxHeaderButton color={colors.text} size={22} />
          <ThemeToggleButton size={22} />
        </View>
      </View>

      {/* Category Filter Chips */}
      {followedCategories.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow}>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              setActiveFilter(null);
            }}
            style={[
              styles.filterChip,
              { borderColor: !activeFilter ? colors.accent : colors.border },
              !activeFilter && { backgroundColor: colors.accent + '15' },
            ]}
            accessibilityRole="button"
            accessibilityLabel="Show all categories"
          >
            <Text style={[styles.filterChipText, { color: !activeFilter ? colors.accent : colors.muted }]}>
              All
            </Text>
          </AnimatedPressable>
          {followedCategories.map((catId) => {
            const cat = ALL_CATS.find((c) => c.slug === catId);
            const isActive = activeFilter === catId;
            return (
              <AnimatedPressable
                key={catId}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  setActiveFilter(isActive ? null : catId);
                }}
                style={[
                  styles.filterChip,
                  { borderColor: isActive ? colors.accent : colors.border },
                  isActive && { backgroundColor: colors.accent + '15' },
                ]}
                accessibilityRole="button"
                accessibilityLabel={`Filter by ${cat?.name || catId}`}
              >
                <Text style={[styles.filterChipText, { color: isActive ? colors.accent : colors.muted }]}>
                  {cat?.name || catId}
                </Text>
              </AnimatedPressable>
            );
          })}
        </ScrollView>
      )}
    </Animated.View>
  );

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      <SectionList
        sections={sections}
        keyExtractor={(item) => item.id}
        renderSectionHeader={({ section }) => (
          <Text style={[styles.sectionTitle, { color: section.isPast ? colors.muted : colors.text, marginTop: 16 }]}>
            {section.title}
          </Text>
        )}
        renderItem={({ item, section }) => renderEventCard(item, !section.isPast)}
        ListHeaderComponent={headerElement}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="calendar-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>
                No events yet
              </Text>
              <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
                Check back later for drops, meetups, and streams.
              </Text>
            </View>
          ) : null
        }
        ListFooterComponent={
          <>
            {isLoadingMore && (
              <View style={styles.loadingMoreContainer}>
                <ActivityIndicator size="small" color={colors.accent} />
              </View>
            )}
            <View style={{ height: 24 }} />
          </>
        }
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        stickySectionHeadersEnabled={false}
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
      />

      {/* Create Event FAB */}
      <AnimatedPressable
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          router.push('/create-event');
        }}
        style={[styles.fab, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel="Create new event"
      >
        <Ionicons name="add" size={28} color="#ffffff" />
      </AnimatedPressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 24,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 4,
  },
  headerIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 10,
  },
  eventCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 12,
    marginBottom: 10,
  },
  eventHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  eventIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  eventInfo: {
    flex: 1,
    paddingRight: 8,
  },
  eventTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  eventTitle: {
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  eventMeta: {
    marginTop: 2,
    fontSize: 11,
  },
  eventLocation: {
    marginTop: 2,
    fontSize: 11,
  },
  eventActions: {
    flexDirection: 'row',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    gap: 8,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    gap: 6,
  },
  actionBtnText: {
    fontSize: 12,
    fontWeight: '600',
  },
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  filterRow: {
    marginBottom: 12,
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    marginRight: 8,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: '600',
  },
  attendeeCountText: {
    fontSize: 11,
    marginTop: 2,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 13,
    marginTop: 4,
  },
  loadingMoreContainer: {
    paddingVertical: 16,
    alignItems: 'center',
  },
});

export default function EventsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Events">
      <EventsScreen />
    </ScreenErrorBoundary>
  );
}
