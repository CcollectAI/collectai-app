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

import React, { useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Linking,
  Alert,
  RefreshControl,
} from 'react-native';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import type { CollectorsEvent } from '@/data/events';
import { getCategoryById } from '@/data/categories';
import { getUserById } from '@/data/users'; // demo-data-ok: attendee list only, and attendeeIds is hardcoded [] by eventsProvider, so it never renders (see EventAttendeesSection); the host card reads the real profile
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
import { safeGoBack } from '@/lib/goBack';
import { isEventPast } from '@/lib/calendar';
import { userErrorMessage } from '@/lib/userErrorMessage';

function EventDetailScreen() {
  const { t } = useTranslation();
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { user } = useAuthContext();
  const currentUserId = user?.id ?? null;

  const [event, setEvent] = useState<CollectorsEvent | null>(null);
  const [loading, setLoading] = useState(true);
  // The event read FAILED — distinct from not found. Without it a timeout
  // rendered "Event not found / This event doesn't exist yet".
  const [loadFailed, setLoadFailed] = useState(false);
  const [hostProfile, setHostProfile] = useState<PublicUserProfile | null>(null);
  const [hostProfileLoading, setHostProfileLoading] = useState(false);
  const [alertsOn, setAlertsOn] = useState(false);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [followingStream, setFollowingStream] = useState(false);
  const [rsvpStatus, setRsvpStatus] = useState<string | undefined>(undefined);
  // One tap, one RSVP write (2026-09-17, class sweep I). All three RSVP
  // handlers share this: they write to the same row, and Going on a PAID event
  // opens a Stripe checkout, so a second tap could start a second checkout for
  // the same ticket. A ref, not state — the guard must be set before the first
  // await, and re-rendering for it would fight the optimistic count updates.
  const rsvpWritingRef = useRef(false);
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
      setLoadFailed(false);
    } catch (err) {
      // A failed REFRESH keeps the event already on screen (setEvent is not
      // called); with nothing shown, the failed state below renders.
      logger.error('[EventDetail] loadEvent error:', err);
      setLoadFailed(true);
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
    if (!event?.hostUserId) return;
    let cancelled = false;
    setHostProfileLoading(true);
    dataProvider.getPublicUserProfile(event.hostUserId)
      .then((p) => { if (!cancelled) setHostProfile(p); })
      .catch((err) => {
        logger.error('[EventDetail] host profile load failed:', err);
        // empty-ok: EventHostSection renders NOTHING for a null profile (EventHostSection.tsx `!profile && !loading`) — no false claim, the card is just absent.
        if (!cancelled) setHostProfile(null);
      })
      .finally(() => { if (!cancelled) setHostProfileLoading(false); });
    return () => { cancelled = true; };
  }, [event?.hostUserId]);

  // Update RSVP status when event loads
  useEffect(() => {
    if (event) {
      setRsvpStatus(event.myRsvpStatus);
    }
  }, [event?.myRsvpStatus]);

  // Announcements only make sense for events created inside the app by a user
  // or organizer. Scraped/external events (concerts, brand drops — source
  // 'scraper'/'rss'/'ticketmaster'/'newsletter' etc.) have no one in our
  // network to post updates, so the announcements card is hidden for them.
  const isCommunityEvent = !!event && (event.source === 'user' || event.source === 'admin');

  // Load drop alert status for this event
  useEffect(() => {
    if (!eventId || !currentUserId) return;
    let cancelled = false;
    collectorsApi.listMyDropAlerts()
      .then((alerts) => {
        if (cancelled) return;
        const hasAlert = Array.isArray(alerts) && alerts.some((a) => a.event_id === eventId);
        setAlertsOn(hasAlert);
      })
      .catch(() => { if (!cancelled) setAlertsOn(false); });
    return () => { cancelled = true; };
  }, [eventId, currentUserId]);

  // Load announcement unread count — only for community (app-created) events;
  // scraped events never have announcements so we skip the call entirely.
  useEffect(() => {
    if (!eventId || !isCommunityEvent) return;
    let cancelled = false;
    dataProvider.listEventAnnouncements(eventId)
      .then((announcements) => {
        if (cancelled) return;
        const unread = announcements.filter((a) => !a.isRead).length;
        setUnreadAnnouncementCount(unread);
      })
      .catch((err) => {
        logger.error('[EventDetail] announcement count load failed:', err);
        // empty-ok: 0 only hides the unread badge; the announcements screen itself shows its own failed state.
        if (!cancelled) setUnreadAnnouncementCount(0);
      });
    return () => { cancelled = true; };
  }, [eventId, isCommunityEvent]);

  /* ---- derived values ---- */
  const isCreator = !!(
    currentUserId &&
    event &&
    (event.createdBy === currentUserId || event.hostUserId === currentUserId)
  );

  const isPastEvent = useMemo(() => {
    if (!event) return false;
    try {
      // `isEventPast`, not `new Date(event.date)`: a bare YYYY-MM-DD parses as
      // UTC MIDNIGHT, so every event happening TODAY read as past and this
      // screen rendered its past branch — Share only, no Going, no Interested —
      // while the list still had it under "Upcoming". Found on Android
      // 2026-09-12 on an event starting at 20:00 that same evening.
      return isEventPast(event.date, event.time, event.endDate);
    } catch (e) {
      logger.error('[silent-catch] [eventId].tsx:167:', e);
      return false;
    }
  }, [event?.date, event?.time, event?.endDate]);

  /* ---- RSVP handlers ---- */
  const handleRsvpGoing = useCallback(async () => {
    if (!event || !eventId) return;
    if (rsvpWritingRef.current) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });

    // Paid event — redirect to ticket checkout
    if (event.ticketPriceCents && event.ticketPriceCents > 0 && rsvpStatus !== 'going') {
      rsvpWritingRef.current = true;
      try {
        const { url } = await dataProvider.createTicketCheckout(eventId as string);
        if (url) {
          Linking.openURL(url);
        }
      } catch (err) {
        logger.error('[EventDetail] ticket checkout error:', err);
        showToast({ message: userErrorMessage(err, 'Failed to start ticket checkout.'), type: 'error' });
      } finally {
        rsvpWritingRef.current = false;
      }
      return;
    }

    rsvpWritingRef.current = true;
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
      logger.error('[EventDetail] rsvp going error:', err);
      loadEvent(); // rollback
    } finally {
      rsvpWritingRef.current = false;
    }
  }, [event, eventId, rsvpStatus, settings.hapticsEnabled, showToast, loadEvent]);

  const handleRsvpInterested = useCallback(async () => {
    if (!event || !eventId) return;
    if (rsvpWritingRef.current) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    rsvpWritingRef.current = true;
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
      logger.error('[EventDetail] rsvp interested error:', err);
      loadEvent(); // rollback
    } finally {
      rsvpWritingRef.current = false;
    }
  }, [event, eventId, rsvpStatus, settings.hapticsEnabled, loadEvent]);

  // Join the waitlist for a full event.
  //
  // This used to POST status:'waitlist'. RsvpRequest only permits
  // going|interested|not_going (events_helpers.py:96), so every tap was a hard
  // 422 that this catch swallowed into a log line — the button changed colour,
  // said "On Waitlist", and nothing was ever written. There is no 'waitlist'
  // row type anywhere: the server implements the waitlist by ACCEPTING 'going'
  // on a full event, storing 'interested', and returning waitlisted:true
  // (events_rsvp.py:65-89). So we send 'going' and take the server's answer.
  // Introducing a real 4th status would mean a DDL change plus re-auditing
  // every consumer of event_attendees.status (v_events_with_attendees_v1's
  // going/interested counters filter on it), for no behavioural gain.
  const handleJoinWaitlist = useCallback(async () => {
    if (!event || !eventId) return;
    if (rsvpWritingRef.current) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    const prevStatus = rsvpStatus;
    rsvpWritingRef.current = true;
    try {
      const res = await dataProvider.rsvpEvent(eventId, 'going');
      setRsvpStatus(res.status);
      setEvent((prev) => (prev ? { ...prev, myRsvpStatus: res.status } : prev));
      showToast({
        message: res.waitlisted
          ? "Event is full — you're on the waitlist"
          : "You're going",
        type: 'success',
      });
      track({ name: 'event_rsvp', properties: { event_id: eventId as string, status: res.status } });
    } catch (err) {
      logger.error('[EventDetail] waitlist error:', err);
      setRsvpStatus(prevStatus);
      showToast({
        message: userErrorMessage(err, 'Could not join the waitlist. Please try again.'),
        type: 'error',
      });
      loadEvent();
    } finally {
      rsvpWritingRef.current = false;
    }
  }, [event, eventId, rsvpStatus, settings.hapticsEnabled, showToast, loadEvent]);

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
      logger.error('[EventDetail] toggle drop alert error:', err);
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
      logger.error('[EventDetail] duplicate error:', err);
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
              safeGoBack(router);
            } catch (err) {
              logger.error('[EventDetail] cancel error:', err);
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
    router.push(path as Href);
  }, [router]);

  const handleUserPress = useCallback((userId: string) => {
    router.push(`/users/${encodeURIComponent(userId)}` as Href);
  }, [router]);

  const handleAskToConnect = useCallback((userId: string) => {
    router.push({
      pathname: '/chat/new',
      params: {
        toUserId: userId,
        contextEventId: event?.id,
      },
    } as Href);
  }, [router, event?.id]);

  // Loading state
  if (loading) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <SkeletonEventCard />
        </View>
        <QuickNavBar />
      </View>
    );
  }

  if (!event && loadFailed) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.emptyContainer}>
          <Ionicons name="cloud-offline-outline" size={48} color={colors.muted} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>
            {t('event_detail.load_failed', { defaultValue: "Couldn't load this event" })}
          </Text>
          <AnimatedPressable
            onPress={loadEvent}
            style={[styles.emptyBtn, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel={t('common.try_again', { defaultValue: 'Try again' })}
          >
            <Text style={[styles.emptyBtnText, { color: colors.text }]}>{t('common.try_again', { defaultValue: 'Try again' })}</Text>
          </AnimatedPressable>
        </View>
        <QuickNavBar />
      </View>
    );
  }

  // Not found state
  if (!event) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <View style={styles.emptyContainer}>
          <Ionicons name="calendar-outline" size={48} color={colors.muted} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>{t('event_detail.not_found')}</Text>
          <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
            This event doesn&apos;t exist yet. Try opening it from the Events tab again.
          </Text>
          <AnimatedPressable
            onPress={() => safeGoBack(router)}
            style={[styles.emptyBtn, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel={t('common.go_back_a11y')}
          >
            <Text style={[styles.emptyBtnText, { color: colors.text }]}>{t('common.go_back')}</Text>
          </AnimatedPressable>
        </View>
        <QuickNavBar />
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
              accessibilityLabel={t('common.more_options_a11y')}
            >
              <Ionicons name="ellipsis-horizontal" size={22} color={colors.text} />
            </AnimatedPressable>
          </View>
        )}

        <EventHeroSection event={event} />

        {/* Promote CTA for creators of non-sponsored events */}
        {isCreator && !event.isSponsored && (
          <AnimatedPressable
            onPress={() => router.push('/sponsor/dashboard' as Href)}
            style={[styles.promoteCta, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '40' }]}
            accessibilityRole="button"
            accessibilityLabel={t('event_detail.promote_a11y')}
          >
            <Ionicons name="megaphone-outline" size={18} color={colors.accent} />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={[styles.promoteTitle, { color: colors.text }]}>{t('event_detail.promote_title')}</Text>
              <Text style={[styles.promoteSubtitle, { color: colors.muted }]}>{t('event_detail.promote_subtitle')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.accent} />
          </AnimatedPressable>
        )}

        {/* Share/Open link render INSIDE the RSVP row (2026-08-17). They used
            to be a row of their own directly above Going / Interested, so the
            screen showed two stacked rows of pills. */}
        <EventRsvpSection
          leadingActions={
            <EventActionBar event={event} hapticsEnabled={settings.hapticsEnabled} />
          }
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

        {isCommunityEvent && (
          <EventAnnouncementsCard
            eventId={event.id}
            unreadCount={unreadAnnouncementCount}
            isCreator={isCreator}
            onNavigate={handleNavigate}
          />
        )}

        {/* Related category */}
        {relatedCategory && (
          <EventRelatedCategory
            category={relatedCategory}
            onPress={() => router.push(`/categories/${encodeURIComponent(relatedCategory.id)}` as Href)}
          />
        )}

        {/* Host collector */}
        <EventHostSection
          profile={hostProfile}
          loading={hostProfileLoading}
          onPress={hostProfile ? () => router.push(`/users/${encodeURIComponent(hostProfile.id)}` as Href) : undefined}
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
  promoteCta: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginHorizontal: 16,
    marginBottom: 12,
  },
  promoteTitle: {
    fontSize: 14,
    fontWeight: '700',
  },
  promoteSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
});
