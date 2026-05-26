/**
 * Events Tab — Collection drops, meetups, and Twitch streams.
 * Follows the same styling pattern as other tab pages.
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  ScrollView,
  SectionList,
  StyleSheet,
  Animated,
  ActivityIndicator,
  RefreshControl,
  TextInput,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { dataProvider } from '@/data';
import type { CollectorsEvent } from '@/data/events';
import { useOptimisticRsvpList } from '@/hooks/useOptimisticRsvp';
import { usePaginatedList } from '@/hooks/usePaginatedList';
import { useFollowedCategories } from '@/hooks/useFollowedCategories';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
import { CountdownBadge } from '@/components/EventCountdown';
import { KIND_ICON, KIND_LABEL } from '@/constants/eventConstants';
import calendar, { parseEventDate, getCountdown } from '@/lib/calendar';
import { CalendarGrid } from '@/components/CalendarGrid';
import { WeekViewCalendar } from '@/components/events/WeekViewCalendar';
import { useToast } from '@/components/Toast';
import { SkeletonList } from '@/components/Skeleton';
import { collectorsApi } from '@/api/collectorsApi';
import * as Location from 'expo-location';
import logger from '@/utils/logger';
import { radius, spacing, text, fontWeight, gap, shadow } from '@/theme/tokens';
import { BETA_MODE } from '@/config/featureFlags';

const VIEW_MODE_TABS = [
  { key: 'list' as const, icon: 'list-outline' as const, label: 'List' },
  { key: 'week' as const, icon: 'grid-outline' as const, label: 'Week' },
  { key: 'calendar' as const, icon: 'calendar-outline' as const, label: 'Month' },
  { key: 'nearby' as const, icon: 'location-outline' as const, label: 'Nearby' },
] as const;

function EventsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'calendar' | 'week' | 'nearby'>('list');
  const [selectedCalendarDate, setSelectedCalendarDate] = useState<string | null>(null);
  const [nearbyEvents, setNearbyEvents] = useState<{ id: string; title: string; date: string; location?: string; distance_km?: number }[]>([]);
  const [nearbyLoading, setNearbyLoading] = useState(false);
  const [nearbyError, setNearbyError] = useState(false);
  const [kindFilter, setKindFilter] = useState<string | null>(null);
  // Default-on filter to the user's onboarded categories — falls back to "show
  // all" automatically when the user follows zero categories so the events
  // tab is never blank just because of the filter.
  const [myCategoriesOnly, setMyCategoriesOnly] = useState<boolean>(true);
  const { followed: followedCategoryIds } = useFollowedCategories();
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


  const [now, setNow] = useState(() => new Date());

  useFocusEffect(
    useCallback(() => {
      setNow(new Date());
    }, []),
  );

  // Strict filter: when "My Categories" is on, only events whose categoryId
  // is in the user's followed set are shown. If the user follows zero
  // categories the result is intentionally empty — the empty-state CTA
  // below tells them to pick favourites in onboarding/profile.
  const followedFilterActive = myCategoriesOnly;
  const noFollowedCategories = myCategoriesOnly && followedCategoryIds.size === 0;

  // Search + kind + followed-category filter
  const searchFiltered = useMemo(
    () => events.filter((e) => {
      if (searchQuery && !e.title.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      if (kindFilter && e.kind !== kindFilter) return false;
      if (followedFilterActive && (!e.categoryId || !followedCategoryIds.has(e.categoryId))) return false;
      return true;
    }),
    [events, searchQuery, kindFilter, followedFilterActive, followedCategoryIds],
  );

  // Unique event kinds for filter chips
  const availableKinds = useMemo(
    () => Array.from(new Set(events.map((e) => e.kind))).filter(Boolean),
    [events],
  );

  const filteredUpcoming = useMemo(
    () => searchFiltered.filter((e) => parseEventDate(e.date, e.time) >= now),
    [searchFiltered, now],
  );
  const filteredPast = useMemo(
    () => searchFiltered.filter((e) => parseEventDate(e.date, e.time) < now),
    [searchFiltered, now],
  );

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await paginatedRefresh();
    setRefreshing(false);
  }, [paginatedRefresh]);

  const loadNearbyEvents = useCallback(async () => {
    setNearbyLoading(true);
    setNearbyError(false);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        showToast({ message: 'Location permission needed for nearby events', type: 'info' });
        setViewMode('list');
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      const data = await collectorsApi.getNearbyEvents(loc.coords.latitude, loc.coords.longitude, 50);
      const nearbyData = data as { events?: typeof nearbyEvents } | undefined;
      if (Array.isArray(nearbyData?.events)) {
        // Sort by distance (closest first)
        const sorted = [...nearbyData.events].sort(
          (a, b) => (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity),
        );
        setNearbyEvents(sorted);
      }
    } catch (err) {
      logger.warn('[Events] nearby events failed:', err);
      setNearbyError(true);
      showToast({ message: 'Could not load nearby events', type: 'error' });
    } finally {
      setNearbyLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    let cancelled = false;
    if (viewMode === 'nearby') {
      loadNearbyEvents().finally(() => {
        if (cancelled) return; // prevent setState after unmount
      });
    }
    return () => { cancelled = true; };
  }, [viewMode, loadNearbyEvents]);

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

  // All filtered events combined (for calendar grid prop and calendar filtering)
  const allFilteredEvents = useMemo(
    () => [...filteredUpcoming, ...filteredPast],
    [filteredUpcoming, filteredPast],
  );

  // Events filtered by selected calendar date (for calendar mode)
  const calendarFilteredEvents = useMemo(() => {
    if (!selectedCalendarDate) return allFilteredEvents;
    return allFilteredEvents.filter((e) => e.date.slice(0, 10) === selectedCalendarDate);
  }, [allFilteredEvents, selectedCalendarDate]);

  // Optimistic RSVP: toggles attendance state immediately, reverts on error
  const optimisticRsvp = useOptimisticRsvpList(setEvents, paginatedRefresh);

  const handleAttend = async (event: CollectorsEvent) => {
    // Optimistic update: toggle attendance state immediately
    try {
      await optimisticRsvp.mutate({
        eventId: event.id,
        currentlyAttending: !!event.isAttending,
      });

      // If RSVP succeeded and user is now attending, silently add to calendar
      if (!event.isAttending) {
        try {
          const eventDate = parseEventDate(event.date, event.time);
          await calendar.addToCalendar({
            eventId: event.id,
            title: event.title,
            startDate: eventDate,
            location: event.location,
            notes: `Sparrow Collect Event: ${KIND_LABEL[event.kind]}`,
          });
        } catch (calErr) {
          // Calendar add is non-critical; don't fail the RSVP for this
          logger.warn('[EventsScreen] calendar add error:', calErr);
        }
      }
    } catch (err: unknown) {
      logger.warn('[EventsScreen] RSVP error:', err);
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

  // Navigation handlers (useCallback to avoid re-creating closures in render)
  const handleEventPress = useCallback((eventId: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(`/events/${encodeURIComponent(eventId)}`);
  }, [router, settings.hapticsEnabled]);

  const handleCreateEvent = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/create-event');
  }, [router, settings.hapticsEnabled]);

  const handleViewModeChange = useCallback((key: 'list' | 'calendar' | 'week' | 'nearby') => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setViewMode(key);
    if (key !== 'calendar') setSelectedCalendarDate(null);
  }, [settings.hapticsEnabled]);

  const handleKindFilterAll = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setKindFilter(null);
  }, [settings.hapticsEnabled]);

  const handleKindFilterToggle = useCallback((kind: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setKindFilter((prev) => prev === kind ? null : kind);
  }, [settings.hapticsEnabled]);

  const handleRetryNearby = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    loadNearbyEvents();
  }, [settings.hapticsEnabled, loadNearbyEvents]);

  const handleNearbyEventPress = useCallback((eventId: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(`/events/${eventId}`);
  }, [router, settings.hapticsEnabled]);

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
        onPress={() => handleEventPress(event.id)}
        style={[
          styles.eventCard,
          {
            backgroundColor: colors.card,
            borderColor: isSponsored
              ? colors.accent
              : isPast ? colors.border : colors.accent + '40',
            opacity: isPast ? 0.6 : 1,
          },
        ]}
        accessibilityRole="button"
        accessibilityLabel={`${isSponsored ? 'Sponsored: ' : ''}${event.title}, ${KIND_LABEL[event.kind]}, ${event.date}${isPast ? ', past event' : ''}`}
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
              cachePolicy="memory-disk"
              transition={150}
            />
          ) : (
            <View
              style={[
                styles.eventIcon,
                { backgroundColor: isPast ? colors.muted + '80' : colors.accent },
              ]}
            >
              <Ionicons name={KIND_ICON[event.kind]} size={20} color={colors.accentText} />
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
              accessibilityLabel={t('events.reminder_a11y')}
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
          <InboxHeaderButton color={colors.text} size={22} />
          <ThemeToggleButton size={22} />
        </View>
      </View>

      {/* Action Row: Create + Sponsor */}
      <View style={styles.actionRow}>
        <AnimatedPressable
          onPress={handleCreateEvent}
          style={[styles.createEventPill, { backgroundColor: colors.accent }]}
          accessibilityRole="button"
          accessibilityLabel={t('events.create_event_a11y')}
        >
          <Ionicons name="add" size={16} color={colors.accentText} />
          <Text style={[styles.createEventPillText, { color: colors.accentText }]}>{t('events.create_event')}</Text>
        </AnimatedPressable>

        {/* Sponsor + Twitch chips removed 2026-04-19 — the events tab is
            consumer-facing; sponsor onboarding lives at /sponsor/register
            and /sponsor/dashboard (reached via direct navigation, not via
            the user-facing events tab). Twitch page is still a stub. */}
      </View>

      {/* Search Bar */}
      <View style={[styles.searchRow, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Ionicons name="search-outline" size={16} color={colors.muted} style={{ marginRight: 8 }} />
        <TextInput
          value={searchQuery}
          onChangeText={setSearchQuery}
          placeholder={t('events.search_placeholder')}
          placeholderTextColor={colors.muted}
          style={[styles.searchInput, { color: colors.text }]}
          accessibilityLabel={t('events.search_a11y')}
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
        {searchQuery.length > 0 && (
          <AnimatedPressable
            onPress={() => setSearchQuery('')}
            accessibilityRole="button"
            accessibilityLabel={t('common.clear_search')}
          >
            <Ionicons name="close-circle" size={18} color={colors.muted} />
          </AnimatedPressable>
        )}
      </View>

      {/* Kind filter chips */}
      {(availableKinds.length > 1 || followedCategoryIds.size > 0) && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.kindFilterRow}
          contentContainerStyle={styles.kindFilterContent}
        >
          {followedCategoryIds.size > 0 && (
            <AnimatedPressable
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                setMyCategoriesOnly((v) => !v);
              }}
              style={[
                styles.kindChip,
                {
                  backgroundColor: myCategoriesOnly ? colors.accent : colors.card,
                  borderColor: myCategoriesOnly ? colors.accent : colors.border,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Filter to your followed categories"
              accessibilityState={{ selected: myCategoriesOnly }}
            >
              <Ionicons
                name="heart"
                size={13}
                color={myCategoriesOnly ? colors.accentText : colors.muted}
              />
              <Text style={[styles.kindChipText, { color: myCategoriesOnly ? colors.accentText : colors.text }]}>
                My Categories
              </Text>
            </AnimatedPressable>
          )}
          <AnimatedPressable
            onPress={handleKindFilterAll}
            style={[
              styles.kindChip,
              {
                backgroundColor: !kindFilter ? colors.accent : colors.card,
                borderColor: !kindFilter ? colors.accent : colors.border,
              },
            ]}
            accessibilityRole="button"
            accessibilityLabel={t('events.show_all_a11y')}
            accessibilityState={{ selected: !kindFilter }}
          >
            <Text style={[styles.kindChipText, { color: !kindFilter ? colors.accentText : colors.text }]}>All</Text>
          </AnimatedPressable>
          {availableKinds.map((kind) => {
            const active = kindFilter === kind;
            return (
              <AnimatedPressable
                key={kind}
                onPress={() => handleKindFilterToggle(kind)}
                style={[
                  styles.kindChip,
                  {
                    backgroundColor: active ? colors.accent : colors.card,
                    borderColor: active ? colors.accent : colors.border,
                  },
                ]}
                accessibilityRole="button"
                accessibilityLabel={`Filter by ${KIND_LABEL[kind] || kind}`}
                accessibilityState={{ selected: active }}
              >
                <Ionicons
                  name={KIND_ICON[kind]}
                  size={13}
                  color={active ? colors.accentText : colors.muted}
                />
                <Text style={[styles.kindChipText, { color: active ? colors.accentText : colors.text }]}>
                  {KIND_LABEL[kind] || kind}
                </Text>
              </AnimatedPressable>
            );
          })}
        </ScrollView>
      )}

      {/* View Mode Tabs — below search */}
      <View style={[styles.viewModeTabs, { backgroundColor: colors.border + '40' }]}>
        {VIEW_MODE_TABS.map((tab) => {
          const isActive = viewMode === tab.key;
          return (
            <AnimatedPressable
              key={tab.key}
              onPress={() => handleViewModeChange(tab.key)}
              style={[
                styles.viewModeTab,
                isActive && {
                  backgroundColor: colors.card,
                  shadowColor: colors.text,
                  shadowOpacity: 0.08,
                  shadowRadius: 4,
                  shadowOffset: { width: 0, height: 1 },
                  elevation: 2,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel={`${tab.label} view`}
              accessibilityState={{ selected: isActive }}
            >
              <Ionicons
                name={isActive ? (tab.icon.replace('-outline', '') as keyof typeof Ionicons.glyphMap) : tab.icon}
                size={15}
                color={isActive ? colors.accent : colors.muted}
              />
              <Text style={[
                styles.viewModeTabText,
                { color: isActive ? colors.text : colors.muted },
                isActive && { fontWeight: fontWeight.bold },
              ]}>
                {tab.label}
              </Text>
            </AnimatedPressable>
          );
        })}
      </View>
    </Animated.View>
  );

  const emptyComponent = loading ? (
    <SkeletonList count={4} type="event" />
  ) : error ? (
    <View style={styles.emptyContainer}>
      <Ionicons name="cloud-offline-outline" size={48} color={colors.muted} />
      <Text style={[styles.emptyTitle, { color: colors.text }]}>
        Failed to load events
      </Text>
      <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
        Pull down to retry.
      </Text>
    </View>
  ) : !loading && noFollowedCategories ? (
    <View style={styles.emptyContainer}>
      <Ionicons name="heart-outline" size={48} color={colors.muted} />
      <Text style={[styles.emptyTitle, { color: colors.text }]}>
        Pick your favourite categories
      </Text>
      <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
        Follow the categories you collect to see relevant events here.
      </Text>
      <AnimatedPressable
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          router.push('/categories');
        }}
        style={{
          marginTop: 16,
          paddingHorizontal: 20,
          paddingVertical: 10,
          borderRadius: radius.md,
          backgroundColor: colors.accent,
        }}
        accessibilityRole="button"
        accessibilityLabel="Follow categories"
      >
        <Text style={{ color: colors.accentText, fontWeight: fontWeight.bold }}>
          Follow categories
        </Text>
      </AnimatedPressable>
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
        events={allFilteredEvents}
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
      {viewMode === 'nearby' ? (
        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          refreshControl={refreshControlElement}
        >
          {headerElement}
          <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 4, marginBottom: 12 }]}>
            Nearby Events
          </Text>
          {nearbyLoading ? (
            <SkeletonList count={3} type="event" />
          ) : nearbyError ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="cloud-offline-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text, marginTop: 12 }]}>{t('events.load_error_title')}</Text>
              <Text style={[styles.emptySubtitle, { color: colors.muted }]}>{t('events.load_error_body')}</Text>
              <AnimatedPressable
                onPress={handleRetryNearby}
                style={[styles.retryBtn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel={t('events.retry_a11y')}
              >
                <Ionicons name="refresh-outline" size={16} color={colors.accentText} />
                <Text style={[styles.retryBtnText, { color: colors.accentText }]}>{t('common.retry_action')}</Text>
              </AnimatedPressable>
            </View>
          ) : nearbyEvents.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="location-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text, marginTop: 12 }]}>{t('events.empty_title')}</Text>
              <Text style={[styles.emptySubtitle, { color: colors.muted }]}>{t('events.empty_body')}</Text>
            </View>
          ) : (
            nearbyEvents.map((ev) => (
              <AnimatedPressable
                key={ev.id}
                style={[styles.eventCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                onPress={() => handleNearbyEventPress(ev.id)}
                accessibilityRole="button"
                accessibilityLabel={`${ev.title}, ${ev.date}${ev.distance_km != null ? `, ${ev.distance_km.toFixed(1)} km away` : ''}`}
              >
                <View style={styles.eventHeader}>
                  <View style={[styles.eventIcon, { backgroundColor: colors.accent }]}>
                    <Ionicons name="location" size={20} color={colors.accentText} />
                  </View>
                  <View style={styles.eventInfo}>
                    <Text style={[styles.eventTitle, { color: colors.text }]} numberOfLines={2}>{ev.title}</Text>
                    <Text style={[styles.eventMeta, { color: colors.muted }]}>{ev.date}</Text>
                    {ev.location && <Text style={[styles.eventLocation, { color: colors.muted }]}>{ev.location}</Text>}
                  </View>
                  {ev.distance_km != null && (
                    <View style={[styles.distanceBadge, { backgroundColor: colors.accent + '15' }]}>
                      <Ionicons name="navigate-outline" size={12} color={colors.accent} />
                      <Text style={[styles.distanceText, { color: colors.accent }]}>{ev.distance_km.toFixed(1)} km</Text>
                    </View>
                  )}
                </View>
              </AnimatedPressable>
            ))
          )}
        </ScrollView>
      ) : viewMode === 'week' ? (
        <View style={styles.scrollView}>
          <View style={styles.scrollContent}>
            {headerElement}
          </View>
          <WeekViewCalendar
            events={events}
            onEventPress={(evt) => router.push(`/events/${evt.id}`)}
          />
        </View>
      ) : viewMode === 'calendar' ? (
        <FlashList
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
          initialNumToRender={10}
          maxToRenderPerBatch={10}
          windowSize={3}
          removeClippedSubviews={true}
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
    fontSize: text['2xl'],
    fontWeight: fontWeight.bold,
  },
  headerSubtitle: {
    fontSize: text.sm,
    marginTop: 4,
  },
  headerIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  viewModeTabs: {
    flexDirection: 'row',
    width: '100%',
    borderRadius: radius.lg,
    padding: 4,
    marginBottom: 14,
    gap: 4,
  },
  viewModeTab: {
    flex: 1,
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: radius.sm,
  },
  viewModeTabText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    letterSpacing: 0.1,
    textAlign: 'center',
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
    marginBottom: 10,
  },
  eventCard: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 12,
    marginBottom: 10,
    ...shadow.card,
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
    borderRadius: radius.xs,
  },
  sponsoredBadgeText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  sponsorNameText: {
    fontSize: text.sm,
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
    borderRadius: radius.sm,
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
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    flex: 1,
  },
  eventMeta: {
    marginTop: 2,
    fontSize: text.sm,
  },
  eventLocation: {
    marginTop: 2,
    fontSize: text.sm,
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
    borderRadius: radius.xs,
    borderWidth: 1,
    gap: 6,
  },
  actionBtnText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
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
    borderRadius: radius.lg,
  },
  createEventPillText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  sponsorPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.lg,
    borderWidth: 1,
  },
  sponsorPillText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: radius.md,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 12,
  },
  searchInput: {
    flex: 1,
    fontSize: text.md,
    paddingVertical: 0,
  },
  filterChipText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  attendeeCountText: {
    fontSize: text.sm,
    marginTop: 2,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.semibold,
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: text.md,
    marginTop: 4,
  },
  loadingMoreContainer: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  distanceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radius.xs,
    marginLeft: 8,
  },
  distanceText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  kindFilterRow: {
    marginBottom: 10,
  },
  kindFilterContent: {
    gap: 8,
  },
  kindChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  kindChipText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: radius.sm,
    marginTop: 16,
  },
  retryBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
});

export default function EventsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Events">
      <EventsScreen />
    </ScreenErrorBoundary>
  );
}
