/**
 * EventAttendeesSection — Attendees list with avatars and connect buttons.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { COMMUNITY_GATED } from '@/config/featureFlags';

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

  // When community is gated and there are 0 attendees, hide the whole
  // section. Every event showing "no one attending" reads as ghost town;
  // when real RSVPs land the section reappears automatically.
  if (COMMUNITY_GATED && attendees.length === 0) {
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
