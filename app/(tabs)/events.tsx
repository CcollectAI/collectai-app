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
  FlatList,
  StyleSheet,
  Animated,
  ActivityIndicator,
  RefreshControl,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
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
import { KIND_ICON, KIND_LABEL } from '@/constants/eventConstants';
import calendar, { parseEventDate, getCountdown } from '@/lib/calendar';
import { CalendarGrid } from '@/components/CalendarGrid';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';

function EventsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const [followedCategories, setFollowedCategories] = useState<string[]>([]);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const [selectedCalendarDate, setSelectedCalendarDate] = useState<string | null>(null);

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

  // Search filter: match title case-insensitively
  const searchFiltered = events.filter(
    (e) => !searchQuery || e.title.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const upcomingEvents = searchFiltered.filter((e) => {
    const eventDate = parseEventDate(e.date, e.time);
    return eventDate >= now;
  });
  const pastEvents = searchFiltered.filter((e) => {
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

  // Events filtered by selected calendar date (for calendar mode)
  const calendarFilteredEvents = useMemo(() => {
    const allFiltered = [...filteredUpcoming, ...filteredPast];
    if (!selectedCalendarDate) return allFiltered;
    return allFiltered.filter((e) => e.date.slice(0, 10) === selectedCalendarDate);
  }, [filteredUpcoming, filteredPast, selectedCalendarDate]);

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
          notes: `CollectAI Event: ${KIND_LABEL[event.kind]}`,
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
      showToast({ message: 'This event has already passed.', type: 'info' });
      return;
    }

    const reminderDate = new Date(eventDate.getTime() - 60 * 60 * 1000);
    if (reminderDate < new Date()) {
      reminderDate.setTime(Date.now() + 60 * 1000);
    }

    const result = await calendar.scheduleReminder({
      eventId: event.id,
      title: `Upcoming: ${event.title}`,
      body: `${KIND_LABEL[event.kind]} starts in 1 hour!`,
      triggerDate: reminderDate,
    });

    if (result.success) {
      showToast({ message: `Reminder set for "${event.title}".`, type: 'success' });
    } else if (result.error !== 'Permission denied') {
      showToast({ message: result.error || 'Could not set reminder.', type: 'error' });
    }
  };

  const renderEventCard = (event: CollectorsEvent, showActions = true) => {
    const metaLine = [
      KIND_LABEL[event.kind],
      event.date + (event.time ? ` — ${event.time}` : ''),
    ]
      .filter(Boolean)
      .join(' • ');

    const eventDate = parseEventDate(event.date, event.time);
    const isPast = eventDate < now;
    const isSponsored = !!event.isSponsored;

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
            borderColor: isSponsored
              ? colors.accent
              : isPast ? colors.border : colors.accent + '40',
          },
        ]}
        accessibilityRole="button"
        accessibilityLabel={`${isSponsored ? 'Sponsored: ' : ''}${event.title}, ${KIND_LABEL[event.kind]}, ${event.date}`}
      >
        {/* Sponsored badge */}
        {isSponsored && (
          <View style={[styles.sponsoredBadgeRow]}>
            <View style={[styles.sponsoredBadge, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="megaphone-outline" size={12} color={colors.accent} />
              <Text style={[styles.sponsoredBadgeText, { color: colors.accent }]}>Sponsored</Text>
            </View>
            {event.sponsorName && (
              <Text style={[styles.sponsorNameText, { color: colors.muted }]} numberOfLines={1}>
                by {event.sponsorName}
              </Text>
            )}
          </View>
        )}

        <View style={styles.eventHeader}>
          {event.imageUrl ? (
            <Image
              source={{ uri: event.imageUrl }}
              style={styles.eventThumbnail}
              contentFit="cover"
            />
          ) : (
            <View
              style={[
                styles.eventIcon,
                { backgroundColor: isPast ? colors.muted + '80' : colors.accent },
              ]}
            >
              <Ionicons name={KIND_ICON[event.kind]} size={20} color="#ffffff" />
            </View>
          )}

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
              accessibilityHint={event.isAttending ? 'Removes your RSVP from this event' : 'RSVPs you to this event and adds it to your calendar'}
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
              accessibilityHint="Schedules a notification one hour before the event"
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
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              setViewMode((m) => (m === 'list' ? 'calendar' : 'list'));
              if (viewMode === 'calendar') setSelectedCalendarDate(null);
            }}
            accessibilityRole="button"
            accessibilityLabel={viewMode === 'list' ? 'Switch to calendar view' : 'Switch to list view'}
            style={styles.viewToggleBtn}
          >
            <Ionicons
              name={viewMode === 'list' ? 'calendar-outline' : 'list-outline'}
              size={22}
              color={viewMode === 'calendar' ? colors.accent : colors.text}
            />
          </AnimatedPressable>
          <InboxHeaderButton color={colors.text} size={22} />
          <ThemeToggleButton size={22} />
        </View>
      </View>

      {/* Action Row: Create + Sponsor */}
      <View style={styles.actionRow}>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push('/create-event');
          }}
          style={[styles.createEventPill, { backgroundColor: colors.accent }]}
          accessibilityRole="button"
          accessibilityLabel="Create new event"
        >
          <Ionicons name="add" size={16} color="#fff" />
          <Text style={styles.createEventPillText}>Create Event</Text>
        </AnimatedPressable>

        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push('/sponsor/dashboard');
          }}
          style={[styles.sponsorPill, { borderColor: colors.accent, backgroundColor: colors.accent + '10' }]}
          accessibilityRole="button"
          accessibilityLabel="Sponsor events"
        >
          <Ionicons name="megaphone-outline" size={14} color={colors.accent} />
          <Text style={[styles.sponsorPillText, { color: colors.accent }]}>Sponsor</Text>
        </AnimatedPressable>
      </View>

      {/* Search Bar */}
      <View style={[styles.searchRow, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Ionicons name="search-outline" size={16} color={colors.muted} style={{ marginRight: 8 }} />
        <TextInput
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder="Search events..."
          placeholderTextColor={colors.muted}
          style={[styles.searchInput, { color: colors.text }]}
          accessibilityLabel="Search events"
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
        {searchQuery.length > 0 && (
          <AnimatedPressable
            onPress={() => setSearchQuery('')}
            accessibilityRole="button"
            accessibilityLabel="Clear search"
          >
            <Ionicons name="close-circle" size={18} color={colors.muted} />
          </AnimatedPressable>
        )}
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
            accessibilityState={{ selected: !activeFilter }}
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
                accessibilityState={{ selected: isActive }}
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

  const emptyComponent = error ? (
    <View style={styles.emptyContainer}>
      <Ionicons name="cloud-offline-outline" size={48} color={colors.muted} />
      <Text style={[styles.emptyTitle, { color: colors.text }]}>
        Failed to load events
      </Text>
      <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
        Pull down to retry.
      </Text>
    </View>
  ) : !loading ? (
    <View style={styles.emptyContainer}>
      <Ionicons name="calendar-outline" size={48} color={colors.muted} />
      <Text style={[styles.emptyTitle, { color: colors.text }]}>
        {selectedCalendarDate ? 'No events on this day' : 'No events yet'}
      </Text>
      <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
        {selectedCalendarDate
          ? 'Tap the date again to deselect, or try another day.'
          : 'Check back later for drops, meetups, and streams.'}
      </Text>
    </View>
  ) : null;

  const footerComponent = (
    <>
      {isLoadingMore && (
        <View style={styles.loadingMoreContainer}>
          <ActivityIndicator size="small" color={colors.accent} />
        </View>
      )}
      <View style={{ height: 24 }} />
    </>
  );

  const refreshControlElement = (
    <RefreshControl
      refreshing={refreshing}
      onRefresh={handleRefresh}
      tintColor={colors.accent}
      colors={[colors.accent]}
    />
  );

  // Calendar mode header: shared header + CalendarGrid + section label
  const calendarHeaderElement = (
    <>
      {headerElement}
      <CalendarGrid
        events={[...filteredUpcoming, ...filteredPast]}
        selectedDate={selectedCalendarDate}
        onSelectDate={setSelectedCalendarDate}
      />
      {calendarFilteredEvents.length > 0 && (
        <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 4 }]}>
          {selectedCalendarDate
            ? `Events on ${selectedCalendarDate}`
            : `All Events (${calendarFilteredEvents.length})`}
        </Text>
      )}
    </>
  );

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      {viewMode === 'calendar' ? (
        <FlatList
          data={calendarFilteredEvents}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => {
            const eventDate = parseEventDate(item.date, item.time);
            const isPast = eventDate < now;
            return renderEventCard(item, !isPast);
          }}
          ListHeaderComponent={calendarHeaderElement}
          ListEmptyComponent={emptyComponent}
          ListFooterComponent={footerComponent}
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          refreshControl={refreshControlElement}
        />
      ) : (
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
          ListEmptyComponent={emptyComponent}
          ListFooterComponent={footerComponent}
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          stickySectionHeadersEnabled={false}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          refreshControl={refreshControlElement}
        />
      )}
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
  viewToggleBtn: {
    padding: 4,
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
  sponsoredBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  sponsoredBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  sponsoredBadgeText: {
    fontSize: 11,
    fontWeight: '600',
  },
  sponsorNameText: {
    fontSize: 11,
    flex: 1,
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
  eventThumbnail: {
    width: 48,
    height: 48,
    borderRadius: 10,
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
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 14,
  },
  createEventPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
  },
  createEventPillText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  sponsorPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  sponsorPillText: {
    fontSize: 13,
    fontWeight: '600',
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 12,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
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
