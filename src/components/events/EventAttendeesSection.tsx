/**
 * EventAttendeesSection — Attendees list with avatars and connect buttons.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface AttendeeUser {
  id: string;
  displayName: string;
  handle: string;
  avatarColor: string;
}

const AvatarSmall: React.FC<{ name: string; color: string }> = ({ name, color }) => {
  const initials =
    name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?';
  return (
    <View style={[styles.avatarSmall, { backgroundColor: color }]}>
      <Text style={styles.avatarSmallText}>{initials}</Text>
    </View>
  );
};

interface EventAttendeesSectionProps {
  attendees: AttendeeUser[];
  onUserPress: (userId: string) => void;
  onConnectPress: (userId: string) => void;
}

export const EventAttendeesSection = React.memo(function EventAttendeesSection({
  attendees,
  onUserPress,
  onConnectPress,
}: EventAttendeesSectionProps) {
  const { colors } = useAppTheme();

  // Hide whenever there is nobody to show — NOT only when COMMUNITY_GATED.
  //
  // Corrected 2026-07-27. The old guard was `COMMUNITY_GATED && length === 0`,
  // and COMMUNITY_GATED is currently false, so the empty state rendered. On
  // the "Hello" event that produced a screen reading
  //
  //     1 going
  //     Collectors attending / following
  //     No collectors are marked as attending yet. You can be the first.
  //
  // — the section flatly contradicting the count directly above it.
  //
  // The old comment claimed "when real RSVPs land the section reappears
  // automatically". That was not true. This list can NEVER populate:
  //   * eventsProvider.ts:35 and :429 hardcode `attendeeIds: []`;
  //   * GET /events/{id} returns counts only (attendee_count, going_count,
  //     interested_count, user_rsvp_status) and no attendee id list;
  //   * getUserById resolves against USER_PROFILES, a static array of demo
  //     collectors, so real user UUIDs would not match even if they arrived.
  //
  // Exposing real attendees is deliberately OFF the table: event_attendees
  // carries a deny-all RLS policy on purpose — "attendee lists are not public
  // data" (2026-07-27). So the honest fix is to show nothing rather than
  // assert that nobody is attending.
  if (attendees.length === 0) {
    return null;
  }

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        Collectors attending / following
      </Text>
      {attendees.length === 0 ? (
        <Text style={[styles.emptyText, { color: colors.muted }]}>
          No collectors are marked as attending yet. You can be the first.
        </Text>
      ) : (
        <View style={[styles.attendeesCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {attendees.map((u) => (
            <View key={u.id} style={styles.attendeeRow}>
              <AnimatedPressable
                onPress={() => onUserPress(u.id)}
                style={styles.attendeeLeft}
                accessibilityRole="button"
                accessibilityLabel={`View ${u.displayName}'s profile`}
              >
                <AvatarSmall name={u.displayName} color={u.avatarColor} />
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
                onPress={() => onConnectPress(u.id)}
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
            {attendees.length === 1
              ? '1 collector is attending/following this event.'
              : `${attendees.length} collectors are attending/following this event.`}
          </Text>
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 8,
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
    color: '#ffffff',
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
});
