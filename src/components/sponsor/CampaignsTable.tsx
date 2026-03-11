import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { EmptyState } from '@/components/EmptyState';
import type { CollectorsEvent } from '@/data/events';

const SHADOW_SM = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, shadowRadius: 3 },
  android: { elevation: 1 },
  default: {},
}) as Record<string, unknown>;

function getEventStatus(event: CollectorsEvent): { label: string; color: string } {
  if (event.status === 'cancelled') return { label: 'Cancelled', color: '#EF4444' };
  if (event.status === 'draft') return { label: 'Draft', color: '#F59E0B' };
  const eventDate = new Date(event.date);
  if (eventDate < new Date()) return { label: 'Past', color: '#94A3B8' };
  return { label: 'Upcoming', color: '#10B981' };
}

interface Props {
  events: CollectorsEvent[];
  onEventPress: (eventId: string) => void;
  onAnnouncePress: (eventId: string) => void;
  onCreateEvent: () => void;
  hapticsEnabled?: boolean;
}

export const CampaignsTable = React.memo(function CampaignsTable({
  events, onEventPress, onAnnouncePress, onCreateEvent, hapticsEnabled,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.sectionWrap}>
      <View style={styles.sectionLabelRow}>
        <Text style={[styles.sectionLabel, { color: colors.muted }]}>CAMPAIGNS</Text>
        {events.length > 0 && (
          <View style={[styles.countBadge, { backgroundColor: colors.accent + '15' }]}>
            <Text style={[styles.countBadgeText, { color: colors.accent }]}>{events.length}</Text>
          </View>
        )}
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border, padding: 0, overflow: 'hidden' }, SHADOW_SM]}>
        {events.length > 0 && (
          <View style={[styles.tableHead, { backgroundColor: colors.background, borderBottomColor: colors.border }]}>
            <Text style={[styles.tableHeadCell, styles.colStatus, { color: colors.muted }]}>Status</Text>
            <Text style={[styles.tableHeadCell, styles.colCampaign, { color: colors.muted }]}>Campaign</Text>
            <Text style={[styles.tableHeadCell, styles.colReach, { color: colors.muted }]}>Reach</Text>
            <View style={styles.colActions} />
          </View>
        )}

        {events.length > 0 ? (
          events.map((event, idx) => {
            const status = getEventStatus(event);
            const reach = event.attendeeCount ?? event.attendeeIds?.length ?? 0;
            const isLast = idx === events.length - 1;
            return (
              <AnimatedPressable
                key={event.id}
                style={[styles.tableRow, !isLast && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }]}
                onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onEventPress(event.id); }}
                accessibilityRole="button"
                accessibilityLabel={`${event.title}, ${status.label}, ${reach} attendees`}
              >
                <View style={styles.colStatus}>
                  <View style={[styles.statusPill, { backgroundColor: status.color + '18' }]}>
                    <View style={[styles.statusDot, { backgroundColor: status.color }]} />
                    <Text style={[styles.statusText, { color: status.color }]}>{status.label}</Text>
                  </View>
                </View>
                <View style={styles.colCampaign}>
                  <Text style={[styles.campaignName, { color: colors.text }]} numberOfLines={1}>{event.title}</Text>
                  <View style={styles.campaignMeta}>
                    <Text style={[styles.campaignMetaText, { color: colors.muted }]}>{event.kind.replace('_', ' ')} · {event.date}</Text>
                    {event.sponsorTier && (
                      <View style={[styles.tierChip, { backgroundColor: colors.accent + '12' }]}>
                        <Text style={[styles.tierChipText, { color: colors.accent }]}>
                          {event.sponsorTier.charAt(0).toUpperCase() + event.sponsorTier.slice(1)}
                        </Text>
                      </View>
                    )}
                  </View>
                </View>
                <View style={styles.colReach}>
                  <Text style={[styles.reachValue, { color: colors.text }]}>{reach}</Text>
                </View>
                <View style={styles.colActions}>
                  <AnimatedPressable
                    onPress={(e) => { e.stopPropagation?.(); fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onAnnouncePress(event.id); }}
                    style={[styles.iconBtn, { backgroundColor: colors.accent + '10' }]}
                    accessibilityRole="button"
                    accessibilityLabel={`Announce to ${event.title}`}
                  >
                    <Ionicons name="megaphone-outline" size={13} color={colors.accent} />
                  </AnimatedPressable>
                  <Ionicons name="chevron-forward" size={14} color={colors.muted} />
                </View>
              </AnimatedPressable>
            );
          })
        ) : (
          <View style={{ padding: 20 }}>
            <EmptyState
              icon="layers-outline"
              title="No Campaigns Yet"
              subtitle="Create your first sponsored event to start reaching collectors."
              colors={colors}
              style={{ paddingVertical: 16 }}
              action={
                <AnimatedPressable onPress={onCreateEvent} style={[styles.primaryBtn, { backgroundColor: colors.accent }]} accessibilityRole="button" accessibilityLabel="Create your first event">
                  <Ionicons name="add" size={16} color="#FFFFFF" />
                  <Text style={styles.primaryBtnText}>New Campaign</Text>
                </AnimatedPressable>
              }
            />
          </View>
        )}
      </View>
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
  tableHead: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, paddingHorizontal: 14, borderBottomWidth: 1 },
  tableHeadCell: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  colStatus: { width: 78 },
  colCampaign: { flex: 1, paddingRight: 8 },
  colReach: { width: 44, alignItems: 'center' },
  colActions: { width: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 6 },
  tableRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 14 },
  statusPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, alignSelf: 'flex-start' },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 10, fontWeight: '600' },
  campaignName: { fontSize: 14, fontWeight: '600', letterSpacing: -0.1 },
  campaignMeta: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 3 },
  campaignMetaText: { fontSize: 11 },
  tierChip: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4 },
  tierChipText: { fontSize: 9, fontWeight: '700' },
  reachValue: { fontSize: 14, fontWeight: '700' },
  iconBtn: { width: 28, height: 28, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10 },
  primaryBtnText: { fontSize: 13, fontWeight: '600', color: '#FFFFFF' },
});
