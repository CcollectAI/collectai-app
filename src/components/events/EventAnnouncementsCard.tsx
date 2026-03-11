/**
 * EventAnnouncementsCard — Announcements list with unread badge + post button for hosts.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface EventAnnouncementsCardProps {
  eventId: string;
  unreadCount: number;
  isCreator: boolean;
  onNavigate: (path: string) => void;
}

export const EventAnnouncementsCard = React.memo(function EventAnnouncementsCard({
  eventId,
  unreadCount,
  isCreator,
  onNavigate,
}: EventAnnouncementsCardProps) {
  const { colors } = useAppTheme();
  const path = `/events/${encodeURIComponent(eventId)}/announcements`;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        Announcements
      </Text>

      <AnimatedPressable
        onPress={() => onNavigate(path)}
        style={[styles.announcementsCard, { backgroundColor: colors.card, borderColor: colors.border }]}
        accessibilityRole="button"
        accessibilityLabel={`View announcements${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
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
          {unreadCount > 0 && (
            <View style={[styles.unreadBadge, { backgroundColor: colors.accent }]}>
              <Text style={styles.unreadBadgeText}>
                {unreadCount > 99 ? '99+' : unreadCount}
              </Text>
            </View>
          )}
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </View>
      </AnimatedPressable>

      {/* Post Announcement button for host/sponsor */}
      {isCreator && (
        <AnimatedPressable
          onPress={() => onNavigate(path)}
          style={[styles.postAnnouncementBtn, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}
          accessibilityRole="button"
          accessibilityLabel="Post announcement"
        >
          <Ionicons name="add-circle-outline" size={16} color={colors.accent} style={{ marginRight: 6 }} />
          <Text style={[styles.postAnnouncementText, { color: colors.accent }]}>Post Announcement</Text>
        </AnimatedPressable>
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
});
