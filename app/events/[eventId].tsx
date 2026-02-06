/**
 * Event Detail Screen — View event details, host, and attendees.
 * Route: /events/[eventId]
 */

import React, { useMemo, useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Linking,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { dataProvider, type PublicUserProfile } from '@/data';
import type { CollectorsEvent, EventKind } from '@/data/events';
import { getCategoryById } from '@/data/categories';
import { getUserById } from '@/data/users';
import { PublicUserProfileCard } from '@/components/PublicUserProfileCard';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

const kindLabel: Record<EventKind, string> = {
  collection_drop: 'Collection drop',
  meetup: 'Meetup',
  stream: 'Twitch stream',
  convention: 'Convention',
  release: 'New release',
};

const kindIcon: Record<EventKind, keyof typeof Ionicons.glyphMap> = {
  collection_drop: 'pricetag-outline',
  meetup: 'people-outline',
  stream: 'videocam-outline',
  convention: 'map-outline',
  release: 'rocket-outline',
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

export default function EventDetailScreen() {
  const { eventId } = useLocalSearchParams<{ eventId?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();

  const [event, setEvent] = useState<CollectorsEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [hostProfile, setHostProfile] = useState<PublicUserProfile | null>(null);
  const [hostProfileLoading, setHostProfileLoading] = useState(false);

  const [alertsOn, setAlertsOn] = useState(false);
  const [followingStream, setFollowingStream] = useState(false);
  const [rsvpStatus, setRsvpStatus] = useState<string | undefined>(undefined);

  // Load event data
  const loadEvent = useCallback(async () => {
    if (!eventId) return;
    setLoading(true);
    try {
      const eventData = await dataProvider.getEventById(eventId);
      setEvent(eventData);
    } catch (err) {
      console.warn('[EventDetail] loadEvent error:', err);
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    loadEvent();
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

  const handleRsvp = async () => {
    if (!event) return;
    try {
      if (rsvpStatus === 'going') {
        await dataProvider.unrsvpEvent(event.id);
        setRsvpStatus(undefined);
      } else {
        await dataProvider.rsvpEvent(event.id, 'going');
        setRsvpStatus('going');
      }
    } catch (err) {
      console.warn('[EventDetail] RSVP error:', err);
    }
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
      console.log('[EventDetail] failed to open url', err),
    );
  };

  const isStream = event?.kind === 'stream';
  const isDrop = event?.kind === 'collection_drop';
  const isMeetup = event?.kind === 'meetup';

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
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  // Not found state
  if (!event) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
        <View style={styles.emptyContainer}>
          <Ionicons name="calendar-outline" size={48} color={colors.muted} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>Event not found</Text>
          <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
            This event doesn't exist yet. Try opening it from the Events tab again.
          </Text>
          <AnimatedPressable
            onPress={() => router.back()}
            style={[styles.emptyBtn, { borderColor: colors.border }]}
          >
            <Text style={[styles.emptyBtnText, { color: colors.text }]}>Go back</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Event Kind Badge */}
        <View style={[styles.kindBadge, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}>
          <Ionicons
            name={kindIcon[event.kind]}
            size={14}
            color={colors.accent}
            style={{ marginRight: 6 }}
          />
          <Text style={[styles.kindText, { color: colors.accent }]}>
            {kindLabel[event.kind]}
          </Text>
        </View>

        {/* Source badge for scraped events */}
        {event.source && event.source !== 'user' && (
          <View style={[styles.sourceBadge, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Ionicons name="globe-outline" size={12} color={colors.muted} style={{ marginRight: 4 }} />
            <Text style={[styles.sourceText, { color: colors.muted }]}>
              {event.source === 'admin' ? 'Official' : event.source === 'newsletter' ? 'From newsletter' : 'Auto-discovered'}
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
            {event.time ? ` • ${event.time}` : ''}
          </Text>
        </View>

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

        {/* Participation controls */}
        <View style={styles.actionsRow}>
          {isDrop && (
            <AnimatedPressable
              onPress={() => {
                setAlertsOn(!alertsOn);
                console.log('[EventDetail] toggle drop alerts', event.id, !alertsOn);
              }}
              style={[
                styles.actionBtn,
                {
                  backgroundColor: alertsOn ? `${colors.accent}15` : colors.card,
                  borderColor: alertsOn ? colors.accent : colors.border,
                },
              ]}
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
                setFollowingStream(!followingStream);
                console.log('[EventDetail] toggle stream follow', event.id, !followingStream);
              }}
              style={[
                styles.actionBtn,
                {
                  backgroundColor: followingStream ? `${colors.accent}15` : colors.card,
                  borderColor: followingStream ? colors.accent : colors.border,
                },
              ]}
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

          <AnimatedPressable
            onPress={handleRsvp}
            style={[
              styles.actionBtn,
              {
                backgroundColor: rsvpStatus === 'going' ? `${colors.accent}15` : colors.card,
                borderColor: rsvpStatus === 'going' ? colors.accent : colors.border,
              },
            ]}
          >
            <Ionicons
              name={rsvpStatus === 'going' ? 'checkmark-circle' : 'person-add-outline'}
              size={16}
              color={rsvpStatus === 'going' ? colors.accent : colors.muted}
              style={{ marginRight: 6 }}
            />
            <Text style={[styles.actionBtnText, { color: rsvpStatus === 'going' ? colors.accent : colors.muted }]}>
              {rsvpStatus === 'going' ? 'Going' : 'Attend'}
            </Text>
          </AnimatedPressable>
        </View>

        {/* Attendee count */}
        {event.attendeeCount != null && event.attendeeCount > 0 && (
          <Text style={[styles.attendeeCountText, { color: colors.muted }]}>
            {event.attendeeCount} {event.attendeeCount === 1 ? 'collector' : 'collectors'} attending
          </Text>
        )}

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
    </SafeAreaView>
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
    marginBottom: 16,
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
  attendeeCountText: {
    fontSize: 12,
    marginTop: 4,
    marginBottom: 8,
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
});
