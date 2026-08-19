/**
 * EventRsvpSection — Going/Interested buttons, waitlist, drop alerts,
 * stream follow, ticket badge, RSVP counts and capacity bar.
 * Also shows "Attended" badge for past events.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import type { CollectorsEvent } from '@/data/events';

interface EventRsvpSectionProps {
  /**
   * Buttons rendered at the START of the action row — in practice
   * `<EventActionBar />` (Open link / Share). They live here rather than in a
   * row of their own because Share stacked above Going / Interested read as two
   * separate decisions instead of one set of actions.
   *
   * Rendered in BOTH branches below. Putting it only in the upcoming-event
   * branch would silently delete Share from every past event, which is the kind
   * of "one branch got the fix" bug this repo keeps paying for.
   */
  leadingActions?: React.ReactNode;
  event: CollectorsEvent;
  rsvpStatus: string | undefined;
  isPastEvent: boolean;
  alertsOn: boolean;
  alertsLoading: boolean;
  followingStream: boolean;
  onRsvpGoing: () => void;
  onRsvpInterested: () => void;
  onJoinWaitlist: () => void;
  onToggleDropAlert: () => void;
  onToggleStreamFollow: () => void;
}

export const EventRsvpSection = React.memo(function EventRsvpSection({
  leadingActions,
  event,
  rsvpStatus,
  isPastEvent,
  alertsOn,
  alertsLoading,
  followingStream,
  onRsvpGoing,
  onRsvpInterested,
  onJoinWaitlist,
  onToggleDropAlert,
  onToggleStreamFollow,
}: EventRsvpSectionProps) {
  const { colors } = useAppTheme();

  const goingCount = event.goingCount ?? 0;
  const interestedCount = event.interestedCount ?? 0;
  const isStream = event.kind === 'stream';
  const isDrop = event.kind === 'collection_drop';

  // There is no 'waitlist' RSVP status — the server implements the waitlist by
  // storing 'interested' when a 'going' lands on a full event
  // (events_rsvp.py:65-89). So on a FULL event "interested" IS "on the
  // waitlist"; this used to compare against a literal 'waitlist' the API can
  // never return, so the button read "Join Waitlist" forever.
  const onWaitlist = !!event.isFull && rsvpStatus === 'interested';

  // ...and for the same reason the separate Interested button is suppressed
  // while the event is full: it would write the exact same row as the waitlist
  // button, so showing both offers the user a distinction the data cannot keep.
  const showInterestedBtn = !event.isFull;

  return (
    <>
      {isPastEvent ? (
        <View style={styles.actionsRow}>
          {leadingActions}
          {rsvpStatus === 'going' ? (
            <View style={[styles.attendedBadge, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}>
              <Ionicons name="checkmark-circle" size={16} color={colors.accent} style={{ marginRight: 6 }} />
              <Text style={[styles.attendedBadgeText, { color: colors.accent }]}>Attended</Text>
            </View>
          ) : rsvpStatus === 'interested' ? (
            <View style={[styles.attendedBadge, { backgroundColor: colors.border + '40', borderColor: colors.border }]}>
              <Ionicons name="star" size={16} color={colors.muted} style={{ marginRight: 6 }} />
              <Text style={[styles.attendedBadgeText, { color: colors.muted }]}>Was interested</Text>
            </View>
          ) : null}
        </View>
      ) : (
        <View style={styles.actionsRow}>
          {leadingActions}
          {isDrop && (
            <AnimatedPressable
              onPress={onToggleDropAlert}
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
              onPress={onToggleStreamFollow}
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
              onPress={onJoinWaitlist}
              style={[
                styles.actionBtn,
                {
                  backgroundColor: onWaitlist ? `${colors.accent}15` : colors.card,
                  borderColor: onWaitlist ? colors.accent : colors.border,
                },
              ]}
              accessibilityRole="button"
              accessibilityLabel={onWaitlist ? 'On waitlist' : 'Join waitlist'}
            >
              <Ionicons
                name={onWaitlist ? 'time' : 'hourglass-outline'}
                size={16}
                color={onWaitlist ? colors.accent : colors.muted}
                style={{ marginRight: 6 }}
              />
              <Text style={[styles.actionBtnText, { color: onWaitlist ? colors.accent : colors.muted }]}>
                {onWaitlist ? 'On Waitlist' : 'Join Waitlist'}
              </Text>
            </AnimatedPressable>
          ) : (
            <AnimatedPressable
              onPress={onRsvpGoing}
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
                {event.ticketPriceCents && event.ticketPriceCents > 0 && rsvpStatus !== 'going'
                  ? `Buy Ticket \u20AC${(event.ticketPriceCents / 100).toFixed(2)}`
                  : 'Going'}
              </Text>
            </AnimatedPressable>
          )}

          {/* Interested button — hidden on a full event, see showInterestedBtn */}
          {showInterestedBtn && (
          <AnimatedPressable
            onPress={onRsvpInterested}
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
          )}
        </View>
      )}

      {/* Ticket price badge */}
      {event.ticketPriceCents != null && event.ticketPriceCents > 0 && (
        <View style={[styles.ticketBadge, { backgroundColor: colors.accent + '15', borderColor: colors.accent }]}>
          <Ionicons name="ticket-outline" size={14} color={colors.accent} style={{ marginRight: 4 }} />
          <Text style={[styles.ticketBadgeText, { color: colors.accent }]}>
            Ticket: {'\u20AC'}{(event.ticketPriceCents / 100).toFixed(2)}
          </Text>
        </View>
      )}

      {/* RSVP counts */}
      {(goingCount > 0 || interestedCount > 0) && (
        <Text style={[styles.rsvpCountText, { color: colors.muted }]}>
          {goingCount} going{interestedCount > 0 ? ` \u00B7 ${interestedCount} interested` : ''}
        </Text>
      )}

      {/* Fallback: old attendeeCount display */}
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
                  backgroundColor: goingCount >= event.maxAttendees ? colors.danger : colors.accent,
                },
              ]}
            />
          </View>
          <Text style={[styles.capacityText, { color: colors.muted }]}>
            {goingCount}/{event.maxAttendees} spots filled
          </Text>
        </View>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  actionsRow: {
    flexDirection: 'row',
    // 'nowrap', not 'wrap': this row can hold four pills (Open link, Share,
    // Going, Interested) and wrapping strands the last one on its own line,
    // where it reads as a separate decision rather than the fourth option in a
    // set. Let the BUTTONS shrink instead — see "flexWrap: 'wrap' on an action
    // row strands the third button" in docs/ui-playbook.md.
    flexWrap: 'nowrap',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  actionBtn: {
    flexShrink: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  actionBtnText: {
    fontSize: 13,
    fontWeight: '500',
    textAlign: 'center',
  },
  attendedBadge: {
    flexShrink: 1,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  attendedBadgeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  ticketBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 8,
  },
  ticketBadgeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  rsvpCountText: {
    fontSize: 12,
    marginTop: 4,
    marginBottom: 12,
  },
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
});
