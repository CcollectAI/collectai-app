/**
 * Event Detail Screen -- View event details, host, attendees, announcements.
 * Route: /events/[eventId]
 *
 * Features:
 *  - 3-dot menu for event creator (Edit, Duplicate, Cancel)
 *  - Announcements card with unread badge
 *  - Dual RSVP buttons: Going / Interested
 *  - Waitlist support when event is full
 *  - Past event "Attended" badge
 */

import React, { useMemo, useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Linking,
  Alert,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import type { CollectorsEvent } from '@/data/events';
import { getCategoryById } from '@/data/categories';
import { getUserById } from '@/data/users';
// PublicUserProfileCard moved to EventHostSection
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useAuthContext } from '@/providers/useAuthContext';
import logger from '@/utils/logger';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useToast } from '@/components/Toast';
import { SkeletonEventCard } from '@/components/Skeleton';
import { QuickNavBar } from '@/components/QuickNavBar';
import { collectorsApi } from '@/api/collectorsApi';
import { track } from '@/analytics/track';

import {
  EventHeroSection,
  EventActionBar,
  EventRsvpSection,
  EventAnnouncementsCard,
  EventAttendeesSection,
  EventCreatorMenu,
  EventRelatedCategory,
  EventHostSection,
} from '@/components/events';

function EventDetailScreen() {
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { user } = useAuthContext();
  const currentUserId = user?.id ?? null;

  const [event, setEvent] = useState<CollectorsEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [hostProfile, setHostProfile] = useState<PublicUserProfile | null>(null);
  const [hostProfileLoading, setHostProfileLoading] = useState(false);
  const [alertsOn, setAlertsOn] = useState(false);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [followingStream, setFollowingStream] = useState(false);
  const [rsvpStatus, setRsvpStatus] = useState<string | undefined>(undefined);
  const [showMenu, setShowMenu] = useState(false);
  const [unreadAnnouncementCount, setUnreadAnnouncementCount] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  // Load event data
  const loadEvent = useCallback(async () => {
    if (!eventId) return;
    setLoading(true);
    try {
      const eventData = await dataProvider.getEventById(eventId);
      setEvent(eventData);
    } catch (err) {
      logger.warn('[EventDetail] loadEvent error:', err);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    loadEvent();
  }, [loadEvent]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadEvent();
    setRefreshing(false);
  }, [loadEvent]);

  // Load host profile when event loads
  useEffect(() => {
    if (event?.hostUserId) {
      setHostProfileLoading(true);
      dataProvider.getPublicUserProfile(event.hostUserId)
        .then(setHostProfile)
        .catch(() => setHostProfile(null))
        .finally(() => setHostProfileLoading(false));
    }
  }, [event?.hostUserId]);

  // Update RSVP status when event loads
  useEffect(() => {
    if (event) {
      setRsvpStatus(event.myRsvpStatus);
    }
  }, [event?.myRsvpStatus]);

  // Load drop alert status for this event
  useEffect(() => {
    if (!eventId || !currentUserId) return;
    collectorsApi.listMyDropAlerts()
      .then((alerts) => {
        const hasAlert = Array.isArray(alerts) && alerts.some((a) => a.event_id === eventId);
        setAlertsOn(hasAlert);
      })
      .catch(() => setAlertsOn(false));
  }, [eventId, currentUserId]);

  // Load announcement unread count
  useEffect(() => {
    if (!eventId) return;
    dataProvider.listEventAnnouncements(eventId)
      .then((announcements) => {
        const unread = announcements.filter((a) => !a.isRead).length;
        setUnreadAnnouncementCount(unread);
      })
      .catch(() => setUnreadAnnouncementCount(0));
  }, [eventId]);

  /* ---- derived values ---- */
  const isCreator = !!(
    currentUserId &&
    event &&
    (event.createdBy === currentUserId || event.hostUserId === currentUserId)
  );

  const isPastEvent = useMemo(() => {
    if (!event) return false;
    try {
      const eventDate = new Date(event.endDate || event.date);
      return eventDate < new Date();
    } catch {
      return false;
    }
  }, [event?.date, event?.endDate]);

  /* ---- RSVP handlers ---- */
  const handleRsvpGoing = useCallback(async () => {
    if (!event || !eventId) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    // Paid event — redirect to ticket checkout
    if (event.ticketPriceCents && event.ticketPriceCents > 0 && rsvpStatus !== 'going') {
      try {
        const { url } = await dataProvider.createTicketCheckout(eventId as string);
        if (url) {
          Linking.openURL(url);
        }
      } catch (err) {
        logger.warn('[EventDetail] ticket checkout error:', err);
        showToast({ message: (err as Error)?.message || 'Failed to start ticket checkout.', type: 'error' });
      }
      return;
    }

    try {
      if (rsvpStatus === 'going') {
        setRsvpStatus(undefined);
        setEvent((prev) => prev ? {
          ...prev,
          myRsvpStatus: undefined,
          goingCount: Math.max(0, (prev.goingCount ?? 0) - 1),
          attendeeCount: Math.max(0, (prev.attendeeCount ?? 0) - 1),
        } : prev);
        await dataProvider.unrsvpEvent(eventId);
      } else {
        const prevStatus = rsvpStatus;
        setRsvpStatus('going');
        setEvent((prev) => prev ? {
          ...prev,
          myRsvpStatus: 'going',
          goingCount: (prev.goingCount ?? 0) + 1,
          interestedCount: prevStatus === 'interested'
            ? Math.max(0, (prev.interestedCount ?? 0) - 1)
            : (prev.interestedCount ?? 0),
          attendeeCount: prevStatus
            ? (prev.attendeeCount ?? 0)
            : (prev.attendeeCount ?? 0) + 1,
        } : prev);
        await dataProvider.rsvpEvent(eventId, 'going');
        track({ name: 'event_rsvp', properties: { event_id: eventId as string, status: 'going' } });
      }
    } catch (err) {
      logger.warn('[EventDetail] rsvp going error:', err);
      loadEvent(); // rollback
    }
  }, [event, eventId, rsvpStatus, settings.hapticsEnabled, showToast, loadEvent]);

  const handleRsvpInterested = useCallback(async () => {
    if (!event || !eventId) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      if (rsvpStatus === 'interested') {
        setRsvpStatus(undefined);
        setEvent((prev) => prev ? {
          ...prev,
          myRsvpStatus: undefined,
          interestedCount: Math.max(0, (prev.interestedCount ?? 0) - 1),
          attendeeCount: Math.max(0, (prev.attendeeCount ?? 0) - 1),
        } : prev);
        await dataProvider.unrsvpEvent(eventId);
      } else {
        const prevStatus = rsvpStatus;
        setRsvpStatus('interested');
        setEvent((prev) => prev ? {
          ...prev,
          myRsvpStatus: 'interested',
          interestedCount: (prev.interestedCount ?? 0) + 1,
          goingCount: prevStatus === 'going'
            ? Math.max(0, (prev.goingCount ?? 0) - 1)
            : (prev.goingCount ?? 0),
          attendeeCount: prevStatus
            ? (prev.attendeeCount ?? 0)
            : (prev.attendeeCount ?? 0) + 1,
        } : prev);
        await dataProvider.rsvpEvent(eventId, 'interested');
        track({ name: 'event_rsvp', properties: { event_id: eventId as string, status: 'interested' } });
      }
    } catch (err) {
      logger.warn('[EventDetail] rsvp interested error:', err);
      loadEvent(); // rollback
    }
  }, [event, eventId, rsvpStatus, settings.hapticsEnabled, loadEvent]);

  const handleJoinWaitlist = useCallback(async () => {
    if (!event || !eventId) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    try {
      setRsvpStatus('waitlist');
      await dataProvider.rsvpEvent(eventId, 'waitlist');
    } catch (err) {
      logger.warn('[EventDetail] waitlist error:', err);
      loadEvent();
    }
  }, [event, eventId, settings.hapticsEnabled, loadEvent]);

  const handleToggleDropAlert = useCallback(async () => {
    if (!eventId || alertsLoading) return;
    setAlertsLoading(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      if (alertsOn) {
        await collectorsApi.unsubscribeDropAlert(eventId);
        setAlertsOn(false);
        showToast({ message: 'Drop alert removed', type: 'info' });
      } else {
        await collectorsApi.subscribeDropAlert(eventId, 24);
        setAlertsOn(true);
        showToast({ message: "Alert set \u2014 we'll notify you before this drop", type: 'success' });
      }
    } catch (err) {
      logger.warn('[EventDetail] toggle drop alert error:', err);
      showToast({ message: 'Failed to update drop alert', type: 'error' });
    } finally {
      setAlertsLoading(false);
    }
  }, [eventId, alertsLoading, alertsOn, settings.hapticsEnabled, showToast]);

  const handleToggleStreamFollow = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setFollowingStream(!followingStream);
    logger.info('[EventDetail] toggle stream follow', event?.id, !followingStream);
  }, [followingStream, settings.hapticsEnabled, event?.id]);

  /* ---- 3-dot menu handlers ---- */
  const handleEditEvent = () => {
    setShowMenu(false);
    if (!eventId) return;
    router.push({ pathname: '/edit-event', params: { eventId } });
  };

  const handleDuplicateEvent = async () => {
    setShowMenu(false);
    if (!eventId) return;
    try {
      const duplicated = await dataProvider.duplicateEvent(eventId);
      router.push({ pathname: '/edit-event', params: { eventId: duplicated.id } });
    } catch (err) {
      logger.warn('[EventDetail] duplicate error:', err);
      showToast({ message: 'Failed to duplicate event.', type: 'error' });
    }
  };

  const handleCancelEvent = () => {
    setShowMenu(false);
    if (!eventId) return;
    Alert.alert(
      'Cancel Event',
      'Are you sure you want to cancel this event? This action cannot be undone and all attendees will be notified.',
      [
        { text: 'Keep Event', style: 'cancel' },
        {
          text: 'Cancel Event',
          style: 'destructive',
          onPress: async () => {
            try {
              await dataProvider.cancelEvent(eventId);
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.back();
            } catch (err) {
              logger.warn('[EventDetail] cancel error:', err);
              showToast({ message: 'Failed to cancel event.', type: 'error' });
            }
          },
        },
      ],
    );
  };

  const relatedCategory = useMemo(
    () => (event?.categoryId ? getCategoryById(event.categoryId) : undefined),
    [event?.categoryId]
  );

  const attendeeUsers = useMemo(
    () =>
      event?.attendeeIds
        .map((id) => getUserById(id))
        .filter((u): u is NonNullable<ReturnType<typeof getUserById>> => Boolean(u)) ?? [],
    [event?.attendeeIds]
  );

  const handleNavigate = useCallback((path: string) => {
    router.push(path as never);
  }, [router]);

  const handleUserPress = useCallback((userId: string) => {
    router.push(`/users/${encodeURIComponent(userId)}` as never);
  }, [router]);

  const handleAskToConnect = useCallback((userId: string) => {
    router.push({
      pathname: '/chat/new',
      params: {
        toUserId: userId,
        contextEventId: event?.id,
      },
    } as never);
  }, [router, event?.id]);

  // Loading state
  if (loading) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <SkeletonEventCard />
        </View>
      </View>
    );
  }

  // Not found state
  if (!event) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.emptyContainer}>
          <Ionicons name="calendar-outline" size={48} color={colors.muted} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>Event not found</Text>
          <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
            This event doesn't exist yet. Try opening it from the Events tab again.
          </Text>
          <AnimatedPressable
            onPress={() => router.back()}
            style={[styles.emptyBtn, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel="Go back"
          >
            <Text style={[styles.emptyBtnText, { color: colors.text }]}>Go back</Text>
          </AnimatedPressable>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        {/* Creator menu (3-dot) */}
        {isCreator && (
          <View style={styles.topRow}>
            <View style={{ flex: 1 }} />
            <AnimatedPressable
              onPress={() => setShowMenu(true)}
              style={styles.menuBtn}
              accessibilityRole="button"
              accessibilityLabel="More options"
            >
              <Ionicons name="ellipsis-horizontal" size={22} color={colors.text} />
            </AnimatedPressable>
          </View>
        )}

        <EventHeroSection event={event} />

        <EventActionBar event={event} hapticsEnabled={settings.hapticsEnabled} />

        <EventRsvpSection
          event={event}
          rsvpStatus={rsvpStatus}
          isPastEvent={isPastEvent}
          alertsOn={alertsOn}
          alertsLoading={alertsLoading}
          followingStream={followingStream}
          onRsvpGoing={handleRsvpGoing}
          onRsvpInterested={handleRsvpInterested}
          onJoinWaitlist={handleJoinWaitlist}
          onToggleDropAlert={handleToggleDropAlert}
          onToggleStreamFollow={handleToggleStreamFollow}
        />

        <EventAnnouncementsCard
          eventId={event.id}
          unreadCount={unreadAnnouncementCount}
          isCreator={isCreator}
          onNavigate={handleNavigate}
        />

        {/* Related category */}
        {relatedCategory && (
          <EventRelatedCategory
            category={relatedCategory}
            onPress={() => router.push(`/categories/${encodeURIComponent(relatedCategory.id)}` as never)}
          />
        )}

        {/* Host collector */}
        <EventHostSection
          profile={hostProfile}
          loading={hostProfileLoading}
          onPress={hostProfile ? () => router.push(`/users/${encodeURIComponent(hostProfile.id)}` as never) : undefined}
        />

        <EventAttendeesSection
          attendees={attendeeUsers}
          onUserPress={handleUserPress}
          onConnectPress={handleAskToConnect}
        />

        {/* Bottom spacing */}
        <View style={{ height: 24 }} />
      </ScrollView>

      {/* 3-dot Menu Modal */}
      <EventCreatorMenu
        visible={showMenu}
        onClose={() => setShowMenu(false)}
        onEdit={handleEditEvent}
        onDuplicate={handleDuplicateEvent}
        onCancel={handleCancelEvent}
      />
      <QuickNavBar />
    </View>
  );
}

export default function EventDetailScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Event Detail">
      <EventDetailScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 20,
  },
  emptyBtn: {
    marginTop: 20,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  emptyBtnText: {
    fontSize: 14,
    fontWeight: '500',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  menuBtn: {
    padding: 8,
  },
  // section, sectionTitle moved to EventRelatedCategory + EventHostSection
  // categoryCard, categoryName, categoryTagline moved to EventRelatedCategory
  // menuOverlay, menuSheet, menuItem, menuItemText, menuDivider moved to EventCreatorMenu
});
