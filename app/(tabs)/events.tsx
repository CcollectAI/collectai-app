/**
 * Events Tab — Collection drops, meetups, and Twitch streams.
 * Follows the same styling pattern as other tab pages.
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Animated,
  Alert,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider } from '@/data';
import type { CollectorsEvent } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
import { CountdownBadge } from '@/components/EventCountdown';
import { CATEGORIES as ALL_CATS } from '@/constants/categories';
import calendar, { parseEventDate, getCountdown } from '@/lib/calendar';

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

export default function EventsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const [refreshing, setRefreshing] = useState(false);
  const [events, setEvents] = useState<CollectorsEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [followedCategories, setFollowedCategories] = useState<string[]>([]);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const loadEvents = useCallback(async () => {
    try {
      const eventsList = await dataProvider.listEvents();
      setEvents(eventsList);
    } catch (err) {
      console.warn('[EventsScreen] loadEvents error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    dataProvider.listFollowedCategories().then(setFollowedCategories).catch(() => {});
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
    await loadEvents();
    setRefreshing(false);
  }, [loadEvents]);

  const handleAttend = async (event: CollectorsEvent) => {
    try {
      if (event.isAttending) {
        await dataProvider.unrsvpEvent(event.id);
      } else {
        await dataProvider.rsvpEvent(event.id);
        // Silently add to calendar after RSVP
        const eventDate = parseEventDate(event.date, event.time);
        await calendar.addToCalendar({
          eventId: event.id,
          title: event.title,
          startDate: eventDate,
          location: event.location,
          notes: `CollectAI Event: ${kindLabel[event.kind]}`,
        });
      }
      await loadEvents();
    } catch (err) {
      console.warn('[EventsScreen] handleAttend error:', err);
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

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['top', 'left', 'right']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
      >
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
                  >
                    <Text style={[styles.filterChipText, { color: isActive ? colors.accent : colors.muted }]}>
                      {cat?.name || catId}
                    </Text>
                  </AnimatedPressable>
                );
              })}
            </ScrollView>
          )}

          {/* Upcoming Events */}
          {filteredUpcoming.length > 0 && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Upcoming ({filteredUpcoming.length})
              </Text>
              {filteredUpcoming.map((event) => renderEventCard(event, true))}
            </View>
          )}

          {/* Past Events */}
          {filteredPast.length > 0 && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.muted }]}>
                Past Events ({filteredPast.length})
              </Text>
              {filteredPast.map((event) => renderEventCard(event, false))}
            </View>
          )}

          {/* Empty state */}
          {events.length === 0 && !loading && (
            <View style={styles.emptyContainer}>
              <Ionicons name="calendar-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>
                No events yet
              </Text>
              <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
                Check back later for drops, meetups, and streams.
              </Text>
            </View>
          )}

          {/* Bottom spacing */}
          <View style={{ height: 24 }} />
        </Animated.View>
      </ScrollView>

      {/* Create Event FAB */}
      <AnimatedPressable
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          router.push('/create-event');
        }}
        style={[styles.fab, { backgroundColor: colors.accent }]}
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
});
