import React from 'react';
import { View, Text, StyleSheet, Image, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import type { EventAnnouncement } from '@/data/events';
import { timeAgo } from '@/lib/timeAgo';
import { MS_PER_WEEK } from '@/constants/time';

const SHADOW_SM = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 3 },
  android: { elevation: 1 },
  default: {},
}) as Record<string, unknown>;

function formatRelativeDate(dateStr?: string): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const diff = Date.now() - date.getTime();
  if (diff < MS_PER_WEEK) return timeAgo(date);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

interface Props {
  announcements: EventAnnouncement[];
  eventNameMap: Map<string, string>;
  hasEvents: boolean;
  onAnnounce: () => void;
}

export const AnnouncementsListSection = React.memo(function AnnouncementsListSection({
  announcements, eventNameMap, hasEvents, onAnnounce,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.sectionWrap}>
      <View style={styles.sectionLabelRow}>
        <Text style={[styles.sectionLabel, { color: colors.muted }]}>ANNOUNCEMENTS</Text>
        {announcements.length > 0 && (
          <View style={[styles.countBadge, { backgroundColor: '#F59E0B15' }]}>
            <Text style={[styles.countBadgeText, { color: '#F59E0B' }]}>{announcements.length}</Text>
          </View>
        )}
      </View>

      {announcements.length > 0 ? (
        <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border, padding: 0, overflow: 'hidden' }, SHADOW_SM]}>
          {announcements.slice(0, 10).map((ann, idx) => {
            const eventTitle = eventNameMap.get(ann.eventId) || 'Event';
            const isLast = idx === Math.min(announcements.length, 10) - 1;
            return (
              <View key={ann.id} style={[styles.annRow, !isLast && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }]}>
                <View style={styles.annRowLeft}>
                  <View style={[styles.annIcon, { backgroundColor: '#F59E0B12' }]}>
                    <Ionicons name="megaphone" size={12} color="#F59E0B" />
                  </View>
                </View>
                <View style={styles.annRowContent}>
                  <View style={styles.annRowHeader}>
                    <Text style={[styles.annTitle, { color: colors.text }]} numberOfLines={1}>{ann.title || eventTitle}</Text>
                    <Text style={[styles.annTime, { color: colors.muted }]}>{formatRelativeDate(ann.createdAt)}</Text>
                  </View>
                  {ann.title && <Text style={[styles.annEventName, { color: colors.muted }]}>{eventTitle}</Text>}
                  <Text style={[styles.annBody, { color: colors.text }]} numberOfLines={2}>{ann.body}</Text>
                  {ann.imageUrl && <Image source={{ uri: ann.imageUrl }} style={styles.annImage} accessibilityLabel="Announcement image" />}
                </View>
              </View>
            );
          })}
        </View>
      ) : (
        <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_SM]}>
          <View style={styles.emptyCenter}>
            <View style={[styles.emptyIconCircle, { backgroundColor: '#F59E0B10' }]}>
              <Ionicons name="megaphone-outline" size={24} color="#F59E0B" />
            </View>
            <Text style={[styles.emptyTitle, { color: colors.text }]}>No Announcements Yet</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Notify event attendees about updates, schedule changes, or exclusive offers.
            </Text>
            {hasEvents && (
              <AnimatedPressable onPress={onAnnounce} style={styles.emptyAction} accessibilityRole="button" accessibilityLabel="Send your first announcement">
                <Ionicons name="megaphone-outline" size={13} color={colors.accent} />
                <Text style={[styles.emptyActionText, { color: colors.accent }]}>Send First Announcement</Text>
              </AnimatedPressable>
            )}
          </View>
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  sectionWrap: { marginBottom: 24 },
  sectionLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  sectionLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 0.8, marginBottom: 10 },
  countBadge: { paddingHorizontal: 7, paddingVertical: 1, borderRadius: 8, marginBottom: 10 },
  countBadgeText: { fontSize: 10, fontWeight: '700' },
  card: { borderRadius: 14, borderWidth: 1, padding: 16 },
  annRow: { flexDirection: 'row', padding: 14, gap: 10 },
  annRowLeft: { paddingTop: 2 },
  annIcon: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  annRowContent: { flex: 1 },
  annRowHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 },
  annTitle: { fontSize: 13, fontWeight: '700', flex: 1, marginRight: 8 },
  annTime: { fontSize: 10, fontWeight: '500' },
  annEventName: { fontSize: 11, marginBottom: 4 },
  annBody: { fontSize: 13, lineHeight: 18 },
  annImage: { width: '100%', height: 120, borderRadius: 8, marginTop: 8 },
  emptyCenter: { alignItems: 'center', paddingVertical: 20, paddingHorizontal: 12 },
  emptyIconCircle: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  emptyTitle: { fontSize: 15, fontWeight: '700', letterSpacing: -0.1 },
  emptySubtitle: { fontSize: 12, textAlign: 'center', lineHeight: 17, marginTop: 4, maxWidth: 260 },
  emptyAction: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 14, paddingVertical: 6 },
  emptyActionText: { fontSize: 13, fontWeight: '600' },
});
