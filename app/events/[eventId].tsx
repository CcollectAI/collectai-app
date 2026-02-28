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
  Modal,
  RefreshControl,
  Share,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import type { CollectorsEvent } from '@/data/events';
import { getCategoryById } from '@/data/categories';
import { getUserById } from '@/data/users';
import { PublicUserProfileCard } from '@/components/PublicUserProfileCard';
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
import { KIND_ICON, KIND_LABEL } from '@/constants/eventConstants';
import { Image } from 'expo-image';
import { parseEventDate, getCountdown } from '@/lib/calendar';

const EVENT_SOURCE_LABELS: Record<string, string> = {
  admin: 'Official',
  newsletter: 'Newsletter',
  community: 'Community',
  scraped: 'Scraped',
  user: 'Community',
};

const AvatarSmall: React.FC<{ name: string; color: string; textColor: string }> = ({ name, color, textColor }) => {
  const initials =
    name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?';
  return (
    <View
      style={[styles.avatarSmall, { backgroundColor: color }]}
    >
      <Text style={[styles.avatarSmallText, { color: textColor }]}>
        {initials}
      </Text>
    </View>
  );
};

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

  // 3-dot menu state
  const [showMenu, setShowMenu] = useState(false);

  // Announcement unread count
  const [unreadAnnouncementCount, setUnreadAnnouncementCount] = useState(0);

  // Pull-to-refresh
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

  const goingCount = event?.goingCount ?? 0;
  const interestedCount = event?.interestedCount ?? 0;

  const isStream = event?.kind === 'stream';
  const isDrop = event?.kind === 'collection_drop';

  /* ---- RSVP handlers ---- */
  const handleRsvpGoing = async () => {
    if (!event || !eventId) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    try {
      if (rsvpStatus === 'going') {
        // Un-RSVP
        setRsvpStatus(undefined);
        setEvent((prev) => prev ? {
          ...prev,
          myRsvpStatus: undefined,
          goingCount: Math.max(0, (prev.goingCount ?? 0) - 1),
          attendeeCount: Math.max(0, (prev.attendeeCount ?? 0) - 1),
        } : prev);
        await dataProvider.unrsvpEvent(eventId);
      } else {
        // RSVP as going
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
      }
    } catch (err) {
      logger.warn('[EventDetail] rsvp going error:', err);
      loadEvent(); // rollback
    }
  };

  const handleRsvpInterested = async () => {
    if (!event || !eventId) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      if (rsvpStatus === 'interested') {
        // Un-RSVP
        setRsvpStatus(undefined);
        setEvent((prev) => prev ? {
          ...prev,
          myRsvpStatus: undefined,
          interestedCount: Math.max(0, (prev.interestedCount ?? 0) - 1),
          attendeeCount: Math.max(0, (prev.attendeeCount ?? 0) - 1),
        } : prev);
        await dataProvider.unrsvpEvent(eventId);
      } else {
        // RSVP as interested
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
      }
    } catch (err) {
      logger.warn('[EventDetail] rsvp interested error:', err);
      loadEvent(); // rollback
    }
  };

  const handleJoinWaitlist = async () => {
    if (!event || !eventId) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    try {
      setRsvpStatus('waitlist');
      await dataProvider.rsvpEvent(eventId, 'waitlist');
    } catch (err) {
      logger.warn('[EventDetail] waitlist error:', err);
      loadEvent();
    }
  };

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

  const openExternal = () => {
    if (!event?.onlineUrl) return;
    Linking.openURL(event.onlineUrl).catch((err) =>
      logger.info('[EventDetail] failed to open url', err),
    );
  };

  const handleAskToConnect = (userId: string) => {
    router.push({
      pathname: '/chat/new',
      params: {
        toUserId: userId,
        contextEventId: event?.id,
      },
    });
  };

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
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#81D8D0" />}
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

        {/* Hero image */}
        {event.imageUrl && (
          <Image
            source={{ uri: event.imageUrl }}
            style={styles.heroImage}
            contentFit="cover"
          />
        )}

        {/* Cancelled banner */}
        {event.status === 'cancelled' && (
          <View style={[styles.cancelledBanner, { backgroundColor: '#EF444415' }]}>
            <Ionicons name="close-circle-outline" size={16} color="#EF4444" />
            <Text style={styles.cancelledBannerText}>This event has been cancelled</Text>
          </View>
        )}

        {/* Event Kind Badge */}
        <View style={[styles.kindBadge, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}>
          <Ionicons
            name={KIND_ICON[event.kind]}
            size={14}
            color={colors.accent}
            style={{ marginRight: 6 }}
          />
          <Text style={[styles.kindText, { color: colors.accent }]}>
            {KIND_LABEL[event.kind]}
          </Text>
        </View>

        {/* Source badge for scraped events */}
        {event.source && event.source !== 'user' && (
          <View style={[styles.sourceBadge, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="globe-outline" size={12} color={colors.muted} style={{ marginRight: 4 }} />
            <Text style={[styles.sourceText, { color: colors.muted }]}>
              {EVENT_SOURCE_LABELS[event.source] || event.source}
            </Text>
          </View>
        )}

        {/* Title & Date/Time */}
        <Text style={[styles.eventTitle, { color: colors.text }]}>
          {event.title}
        </Text>

        <View style={styles.metaRow}>
          <Ionicons name="calendar-outline" size={16} color={colors.muted} style={{ marginRight: 6 }} />
          <Text style={[styles.metaText, { color: colors.muted }]}>
            {event.date}
            {event.time ? ` \u2022 ${event.time}` : ''}
          </Text>
        </View>

        {event.date && (() => {
          const eventDate = parseEventDate(event.date, event.time);
          const countdown = getCountdown(eventDate);
          const isUpcoming = !countdown.isPast;
          return (
            <View style={[styles.countdownBadge, { backgroundColor: isUpcoming ? colors.accent + '15' : colors.border + '40' }]}>
              <Ionicons name={isUpcoming ? 'time-outline' : 'checkmark-circle-outline'} size={14} color={isUpcoming ? colors.accent : colors.muted} />
              <Text style={[styles.countdownText, { color: isUpcoming ? colors.accent : colors.muted }]}>{countdown.formatted}</Text>
            </View>
          );
        })()}

        {event.location && (
          <View style={styles.metaRow}>
            <Ionicons name="location-outline" size={16} color={colors.muted} style={{ marginRight: 6 }} />
            <Text style={[styles.metaText, { color: colors.muted }]}>
              {event.location}
            </Text>
          </View>
        )}

        {/* Description */}
        <View style={[styles.descriptionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={[styles.descriptionText, { color: colors.text }]}>
            {event.description}
          </Text>
        </View>

        {/* Primary external action */}
        {event.onlineUrl && (
          <AnimatedPressable
            onPress={openExternal}
            style={[styles.primaryBtn, { backgroundColor: colors.accent }]}
            accessibilityRole="link"
            accessibilityLabel={isStream ? 'Open stream' : isDrop ? 'Open drop page' : 'Open link'}
          >
            <Ionicons
              name={isStream ? 'logo-twitch' : 'open-outline'}
              size={16}
              color="#ffffff"
              style={{ marginRight: 6 }}
            />
            <Text style={[styles.primaryBtnText, { color: colors.card }]}>
              {isStream
                ? 'Open stream'
                : isDrop
                ? 'Open drop page'
                : 'Open link'}
            </Text>
          </AnimatedPressable>
        )}

        {/* ============================================================== */}
        {/*  RSVP Section                                                   */}
        {/* ============================================================== */}
        {isPastEvent ? (
          /* Past event: show "Attended" badge if the user went */
          rsvpStatus === 'going' ? (
            <View style={[styles.attendedBadge, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}>
              <Ionicons name="checkmark-circle" size={16} color={colors.accent} style={{ marginRight: 6 }} />
              <Text style={[styles.attendedBadgeText, { color: colors.accent }]}>Attended</Text>
            </View>
          ) : rsvpStatus === 'interested' ? (
            <View style={[styles.attendedBadge, { backgroundColor: colors.border + '40', borderColor: colors.border }]}>
              <Ionicons name="star" size={16} color={colors.muted} style={{ marginRight: 6 }} />
              <Text style={[styles.attendedBadgeText, { color: colors.muted }]}>Was interested</Text>
            </View>
          ) : null
        ) : (
          /* Active event: show RSVP buttons */
          <View style={styles.actionsRow}>
            {isDrop && (
              <AnimatedPressable
                onPress={async () => {
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
                }}
                disabled={alertsLoading}
                style={[
                  styles.actionBtn,
                  {
                    backgroundColor: alertsOn ? `${colors.accent}15` : colors.card,
                    borderColor: alertsOn ? colors.accent : colors.border,
                    opacity: alertsLoading ? 0.6 : 1,
                  },
                ]}
                accessibilityRole="button"
                accessibilityLabel={alertsOn ? 'Turn off drop alerts' : 'Alert me about this drop'}
              >
                <Ionicons
                  name={alertsOn ? 'notifications' : 'notifications-outline'}
                  size={16}
                  color={alertsOn ? colors.accent : colors.muted}
                  style={{ marginRight: 6 }}
                />
                <Text style={[styles.actionBtnText, { color: alertsOn ? colors.accent : colors.muted }]}>
                  {alertsOn ? 'Alerts on' : 'Alert me'}
                </Text>
              </AnimatedPressable>
            )}

            {isStream && (
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  setFollowingStream(!followingStream);
                  logger.info('[EventDetail] toggle stream follow', event.id, !followingStream);
                }}
                style={[
                  styles.actionBtn,
                  {
                    backgroundColor: followingStream ? `${colors.accent}15` : colors.card,
                    borderColor: followingStream ? colors.accent : colors.border,
                  },
                ]}
                accessibilityRole="button"
                accessibilityLabel={followingStream ? 'Unfollow stream' : 'Follow stream'}
              >
                <Ionicons
                  name={followingStream ? 'checkmark-circle' : 'add-circle-outline'}
                  size={16}
                  color={followingStream ? colors.accent : colors.muted}
                  style={{ marginRight: 6 }}
                />
                <Text style={[styles.actionBtnText, { color: followingStream ? colors.accent : colors.muted }]}>
                  {followingStream ? 'Following' : 'Follow stream'}
                </Text>
              </AnimatedPressable>
            )}

            {/* Going / Join Waitlist button */}
            {event.isFull && rsvpStatus !== 'going' ? (
              <AnimatedPressable
                onPress={handleJoinWaitlist}
                style={[
                  styles.actionBtn,
                  {
                    backgroundColor: rsvpStatus === 'waitlist' ? `${colors.accent}15` : colors.card,
                    borderColor: rsvpStatus === 'waitlist' ? colors.accent : colors.border,
                  },
                ]}
                accessibilityRole="button"
                accessibilityLabel={rsvpStatus === 'waitlist' ? 'On waitlist' : 'Join waitlist'}
              >
                <Ionicons
                  name={rsvpStatus === 'waitlist' ? 'time' : 'hourglass-outline'}
                  size={16}
                  color={rsvpStatus === 'waitlist' ? colors.accent : colors.muted}
                  style={{ marginRight: 6 }}
                />
                <Text style={[styles.actionBtnText, { color: rsvpStatus === 'waitlist' ? colors.accent : colors.muted }]}>
                  {rsvpStatus === 'waitlist' ? 'On Waitlist' : 'Join Waitlist'}
                </Text>
              </AnimatedPressable>
            ) : (
              <AnimatedPressable
                onPress={handleRsvpGoing}
                style={[
                  styles.actionBtn,
                  {
                    backgroundColor: rsvpStatus === 'going' ? `${colors.accent}15` : colors.card,
                    borderColor: rsvpStatus === 'going' ? colors.accent : colors.border,
                  },
                ]}
                accessibilityRole="button"
                accessibilityLabel={rsvpStatus === 'going' ? 'Cancel going' : 'Mark as going'}
                accessibilityHint={rsvpStatus === 'going' ? 'Removes your RSVP from this event' : 'RSVPs you as going to this event'}
              >
                <Ionicons
                  name={rsvpStatus === 'going' ? 'checkmark-circle' : 'person-add-outline'}
                  size={16}
                  color={rsvpStatus === 'going' ? colors.accent : colors.muted}
                  style={{ marginRight: 6 }}
                />
                <Text style={[styles.actionBtnText, { color: rsvpStatus === 'going' ? colors.accent : colors.muted }]}>
                  Going
                </Text>
              </AnimatedPressable>
            )}

            {/* Interested button */}
            <AnimatedPressable
              onPress={handleRsvpInterested}
              style={[
                styles.actionBtn,
                {
                  backgroundColor: rsvpStatus === 'interested' ? `${colors.accent}15` : colors.card,
                  borderColor: rsvpStatus === 'interested' ? colors.accent : colors.border,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel={rsvpStatus === 'interested' ? 'Remove interest' : 'Mark as interested'}
              accessibilityHint={rsvpStatus === 'interested' ? 'Removes your interest from this event' : 'Marks you as interested in this event'}
            >
              <Ionicons
                name={rsvpStatus === 'interested' ? 'star' : 'star-outline'}
                size={16}
                color={rsvpStatus === 'interested' ? colors.accent : colors.muted}
                style={{ marginRight: 6 }}
              />
              <Text style={[styles.actionBtnText, { color: rsvpStatus === 'interested' ? colors.accent : colors.muted }]}>
                Interested
              </Text>
            </AnimatedPressable>
          </View>
        )}

        {/* RSVP counts */}
        {(goingCount > 0 || interestedCount > 0) && (
          <Text style={[styles.rsvpCountText, { color: colors.muted }]}>
            {goingCount} going{interestedCount > 0 ? ` \u00B7 ${interestedCount} interested` : ''}
          </Text>
        )}

        {/* Fallback: old attendeeCount display when goingCount/interestedCount are not set */}
        {goingCount === 0 && interestedCount === 0 && event.attendeeCount != null && event.attendeeCount > 0 && (
          <Text style={[styles.rsvpCountText, { color: colors.muted }]}>
            {event.attendeeCount} {event.attendeeCount === 1 ? 'collector' : 'collectors'} attending
          </Text>
        )}

        {/* Capacity progress bar */}
        {event.maxAttendees != null && event.maxAttendees > 0 && (
          <View style={styles.capacityBar}>
            <View style={[styles.capacityTrack, { backgroundColor: colors.border }]}>
              <View
                style={[
                  styles.capacityFill,
                  {
                    width: `${Math.min(100, (goingCount / event.maxAttendees) * 100)}%`,
                    backgroundColor: goingCount >= event.maxAttendees ? '#EF4444' : colors.accent,
                  },
                ]}
              />
            </View>
            <Text style={[styles.capacityText, { color: colors.muted }]}>
              {goingCount}/{event.maxAttendees} spots filled
            </Text>
          </View>
        )}

        {/* Share Event */}
        <AnimatedPressable
          onPress={async () => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            try {
              await Share.share({
                message: `${event.title}\n${event.date}${event.time ? ` at ${event.time}` : ''}${event.location ? `\n${event.location}` : ''}\n\nCheck it out on CollectAI!`,
                title: event.title,
              });
            } catch {
              showToast({ message: 'Failed to share event', type: 'error' });
            }
          }}
          style={[styles.shareBtn, { backgroundColor: colors.card, borderColor: colors.border }]}
          accessibilityRole="button"
          accessibilityLabel="Share this event"
        >
          <Ionicons name="share-outline" size={16} color={colors.accent} style={{ marginRight: 6 }} />
          <Text style={[styles.shareBtnText, { color: colors.accent }]}>Share Event</Text>
        </AnimatedPressable>

        {/* ============================================================== */}
        {/*  Announcements Card                                             */}
        {/* ============================================================== */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            Announcements
          </Text>

          <AnimatedPressable
            onPress={() => router.push(`/events/${encodeURIComponent(event.id)}/announcements`)}
            style={[styles.announcementsCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel={`View announcements${unreadAnnouncementCount > 0 ? `, ${unreadAnnouncementCount} unread` : ''}`}
          >
            <View style={styles.announcementsLeft}>
              <Ionicons name="megaphone-outline" size={20} color={colors.accent} />
              <View style={styles.announcementsInfo}>
                <Text style={[styles.announcementsTitle, { color: colors.text }]}>
                  Event Announcements
                </Text>
                <Text style={[styles.announcementsSubtitle, { color: colors.muted }]}>
                  Updates from the host
                </Text>
              </View>
            </View>

            <View style={styles.announcementsRight}>
              {unreadAnnouncementCount > 0 && (
                <View style={[styles.unreadBadge, { backgroundColor: colors.accent }]}>
                  <Text style={styles.unreadBadgeText}>
                    {unreadAnnouncementCount > 99 ? '99+' : unreadAnnouncementCount}
                  </Text>
                </View>
              )}
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </View>
          </AnimatedPressable>

          {/* Post Announcement button for host/sponsor */}
          {isCreator && (
            <AnimatedPressable
              onPress={() => router.push(`/events/${encodeURIComponent(event.id)}/announcements`)}
              style={[styles.postAnnouncementBtn, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}
              accessibilityRole="button"
              accessibilityLabel="Post announcement"
            >
              <Ionicons name="add-circle-outline" size={16} color={colors.accent} style={{ marginRight: 6 }} />
              <Text style={[styles.postAnnouncementText, { color: colors.accent }]}>Post Announcement</Text>
            </AnimatedPressable>
          )}
        </View>

        {/* Related category */}
        {relatedCategory && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>
              Related category
            </Text>

            <AnimatedPressable
              onPress={() =>
                router.push(`/categories/${encodeURIComponent(relatedCategory.id)}`)
              }
              style={[styles.categoryCard, { backgroundColor: colors.card, borderColor: colors.border }]}
              accessibilityRole="link"
              accessibilityLabel={`View ${relatedCategory.name} category`}
            >
              <Text style={[styles.categoryName, { color: colors.text }]}>
                {relatedCategory.name}
              </Text>
              <Text style={[styles.categoryTagline, { color: colors.muted }]} numberOfLines={2}>
                {relatedCategory.tagline}
              </Text>
            </AnimatedPressable>
          </View>
        )}

        {/* Host collector */}
        {(hostProfile || hostProfileLoading) && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>
              Host collector
            </Text>
            <PublicUserProfileCard
              profile={hostProfile}
              loading={hostProfileLoading}
              onPress={hostProfile ? () => router.push(`/users/${encodeURIComponent(hostProfile.id)}`) : undefined}
            />
          </View>
        )}

        {/* Collectors attending */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            Collectors attending / following
          </Text>
          {attendeeUsers.length === 0 ? (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No collectors are marked as attending yet. You can be the first.
            </Text>
          ) : (
            <View style={[styles.attendeesCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {attendeeUsers.map((u) => (
                <View key={u.id} style={styles.attendeeRow}>
                  <AnimatedPressable
                    onPress={() => router.push(`/users/${encodeURIComponent(u.id)}`)}
                    style={styles.attendeeLeft}
                    accessibilityRole="button"
                    accessibilityLabel={`View ${u.displayName}'s profile`}
                  >
                    <AvatarSmall
                      name={u.displayName}
                      color={u.avatarColor}
                      textColor="#ffffff"
                    />
                    <View style={styles.attendeeInfo}>
                      <Text style={[styles.attendeeName, { color: colors.text }]} numberOfLines={1}>
                        {u.displayName}
                      </Text>
                      <Text style={[styles.attendeeHandle, { color: colors.muted }]} numberOfLines={1}>
                        @{u.handle}
                      </Text>
                    </View>
                  </AnimatedPressable>

                  <AnimatedPressable
                    onPress={() => handleAskToConnect(u.id)}
                    style={[styles.connectBtn, { borderColor: colors.border }]}
                    accessibilityRole="button"
                    accessibilityLabel={`Connect with ${u.displayName}`}
                  >
                    <Ionicons
                      name="chatbubble-ellipses-outline"
                      size={14}
                      color={colors.accent}
                      style={{ marginRight: 4 }}
                    />
                    <Text style={[styles.connectBtnText, { color: colors.accent }]}>
                      Connect
                    </Text>
                  </AnimatedPressable>
                </View>
              ))}

              <Text style={[styles.attendeeCount, { color: colors.muted }]}>
                {attendeeUsers.length === 1
                  ? '1 collector is attending/following this event.'
                  : `${attendeeUsers.length} collectors are attending/following this event.`}
              </Text>
            </View>
          )}
        </View>

        {/* Bottom spacing */}
        <View style={{ height: 24 }} />
      </ScrollView>

      {/* ================================================================ */}
      {/*  3-dot Menu Modal                                                 */}
      {/* ================================================================ */}
      <Modal
        visible={showMenu}
        transparent
        animationType="fade"
        onRequestClose={() => setShowMenu(false)}
      >
        <AnimatedPressable
          style={styles.menuOverlay}
          onPress={() => setShowMenu(false)}
          accessibilityRole="button"
          accessibilityLabel="Close menu"
        >
          <View style={[styles.menuSheet, { backgroundColor: colors.card, borderColor: colors.border }]}>
            {/* Edit Event */}
            <AnimatedPressable
              style={styles.menuItem}
              onPress={handleEditEvent}
              accessibilityRole="button"
              accessibilityLabel="Edit event"
            >
              <Ionicons name="create-outline" size={20} color={colors.accent} />
              <Text style={[styles.menuItemText, { color: colors.text }]}>Edit Event</Text>
            </AnimatedPressable>

            <View style={[styles.menuDivider, { backgroundColor: colors.border }]} />

            {/* Duplicate Event */}
            <AnimatedPressable
              style={styles.menuItem}
              onPress={handleDuplicateEvent}
              accessibilityRole="button"
              accessibilityLabel="Duplicate event"
            >
              <Ionicons name="copy-outline" size={20} color={colors.accent} />
              <Text style={[styles.menuItemText, { color: colors.text }]}>Duplicate Event</Text>
            </AnimatedPressable>

            <View style={[styles.menuDivider, { backgroundColor: colors.border }]} />

            {/* Cancel Event */}
            <AnimatedPressable
              style={styles.menuItem}
              onPress={handleCancelEvent}
              accessibilityRole="button"
              accessibilityLabel="Cancel event"
            >
              <Ionicons name="close-circle-outline" size={20} color="#EF4444" />
              <Text style={[styles.menuItemText, { color: '#EF4444' }]}>Cancel Event</Text>
            </AnimatedPressable>

            <View style={[styles.menuDivider, { backgroundColor: colors.border }]} />

            {/* Dismiss */}
            <AnimatedPressable
              style={styles.menuItem}
              onPress={() => setShowMenu(false)}
              accessibilityRole="button"
              accessibilityLabel="Cancel"
            >
              <Text style={[styles.menuItemText, { color: colors.muted }]}>Cancel</Text>
            </AnimatedPressable>
          </View>
        </AnimatedPressable>
      </Modal>
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

  /* Top row: back + menu */
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
  },
  backBtnText: {
    fontSize: 15,
    fontWeight: '500',
    marginLeft: 2,
  },
  menuBtn: {
    padding: 8,
  },

  /* Hero image */
  heroImage: {
    width: '100%',
    height: 200,
    borderRadius: 12,
    marginBottom: 16,
  },

  /* Cancelled banner */
  cancelledBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    marginBottom: 12,
  },
  cancelledBannerText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#EF4444',
  },

  kindBadge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    marginBottom: 8,
  },
  kindText: {
    fontSize: 12,
    fontWeight: '500',
  },
  eventTitle: {
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 6,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 2,
  },
  metaText: {
    fontSize: 14,
  },
  countdownBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  countdownText: {
    fontSize: 13,
    fontWeight: '600',
  },
  descriptionCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginTop: 12,
    marginBottom: 12,
  },
  descriptionText: {
    fontSize: 14,
    lineHeight: 20,
  },
  primaryBtn: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 24,
    marginBottom: 12,
  },
  primaryBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 8,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  actionBtnText: {
    fontSize: 13,
    fontWeight: '500',
  },

  /* Attended badge (past events) */
  attendedBadge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    marginBottom: 8,
  },
  attendedBadgeText: {
    fontSize: 13,
    fontWeight: '600',
  },

  /* Share button */
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 16,
  },
  shareBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },

  /* RSVP count text */
  rsvpCountText: {
    fontSize: 12,
    marginTop: 4,
    marginBottom: 12,
  },

  /* Capacity progress bar */
  capacityBar: {
    marginBottom: 16,
  },
  capacityTrack: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  capacityFill: {
    height: '100%',
    borderRadius: 3,
  },
  capacityText: {
    fontSize: 12,
    marginTop: 6,
  },

  /* Announcements card */
  announcementsCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  announcementsLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 12,
  },
  announcementsInfo: {
    flex: 1,
  },
  announcementsTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  announcementsSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  announcementsRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  unreadBadge: {
    minWidth: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  unreadBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  postAnnouncementBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 8,
  },
  postAnnouncementText: {
    fontSize: 13,
    fontWeight: '600',
  },

  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 8,
  },
  categoryCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  categoryName: {
    fontSize: 15,
    fontWeight: '600',
  },
  categoryTagline: {
    fontSize: 13,
    marginTop: 4,
  },
  emptyText: {
    fontSize: 13,
  },
  attendeesCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  attendeeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  attendeeLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  avatarSmall: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  avatarSmallText: {
    fontSize: 12,
    fontWeight: '700',
  },
  attendeeInfo: {
    flex: 1,
  },
  attendeeName: {
    fontSize: 14,
    fontWeight: '600',
  },
  attendeeHandle: {
    fontSize: 12,
    marginTop: 1,
  },
  connectBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 16,
    borderWidth: 1,
  },
  connectBtnText: {
    fontSize: 12,
    fontWeight: '500',
  },
  attendeeCount: {
    fontSize: 12,
    marginTop: 4,
  },
  sourceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 8,
  },
  sourceText: {
    fontSize: 11,
  },

  /* 3-dot menu modal */
  menuOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  menuSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    borderBottomWidth: 0,
    paddingVertical: 8,
    paddingBottom: 32,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
  },
  menuItemText: {
    fontSize: 16,
    fontWeight: '500',
  },
  menuDivider: {
    height: 1,
    marginHorizontal: 16,
  },
});
