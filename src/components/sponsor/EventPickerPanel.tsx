import React from 'react';
import { View, Text, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import type { CollectorsEvent } from '@/data/events';

const SHADOW_MD = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 8 },
  android: { elevation: 3 },
  default: {},
}) as Record<string, unknown>;

function getEventStatus(event: CollectorsEvent, colors: { danger: string; warning: string; muted: string; success: string }): { label: string; color: string } {
  if (event.status === 'cancelled') return { label: 'Cancelled', color: colors.danger };
  if (event.status === 'draft') return { label: 'Draft', color: colors.warning };
  if (new Date(event.date) < new Date()) return { label: 'Past', color: colors.muted };
  return { label: 'Upcoming', color: colors.success };
}

interface Props {
  events: CollectorsEvent[];
  onSelect: (eventId: string) => void;
  onCancel: () => void;
  hapticsEnabled?: boolean;
}

export const EventPickerPanel = React.memo(function EventPickerPanel({
  events, onSelect, onCancel, hapticsEnabled,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }, SHADOW_MD]}>
      <View style={styles.header}>
        <View style={[styles.iconCircle, { backgroundColor: colors.accent + '12' }]}>
          <Ionicons name="megaphone-outline" size={16} color={colors.accent} />
        </View>
        <View>
          <Text style={[styles.title, { color: colors.text }]}>Send Announcement</Text>
          <Text style={[styles.subtitle, { color: colors.muted }]}>Select which event to notify</Text>
        </View>
      </View>

      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      {events.map((event) => {
        const status = getEventStatus(event, colors);
        return (
          <AnimatedPressable
            key={event.id}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onSelect(event.id); }}
            style={[styles.row, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel={`Announce to ${event.title}`}
          >
            <View style={[styles.dot, { backgroundColor: status.color }]} />
            <View style={styles.info}>
              <Text style={[styles.name, { color: colors.text }]} numberOfLines={1}>{event.title}</Text>
              <Text style={[styles.meta, { color: colors.muted }]}>
                {event.date} · {event.attendeeCount ?? event.attendeeIds?.length ?? 0} attendees
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.muted} />
          </AnimatedPressable>
        );
      })}

      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      <AnimatedPressable onPress={onCancel} style={[styles.cancelBtn, { borderColor: colors.border }]} accessibilityRole="button" accessibilityLabel="Cancel">
        <Text style={[styles.cancelText, { color: colors.muted }]}>Cancel</Text>
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  container: { borderRadius: 14, borderWidth: 1, padding: 16, marginBottom: 24 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  iconCircle: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 15, fontWeight: '700', letterSpacing: -0.2 },
  subtitle: { fontSize: 12, marginTop: 1 },
  divider: { height: 1, marginVertical: 14 },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 4, borderBottomWidth: StyleSheet.hairlineWidth, gap: 10 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  info: { flex: 1 },
  name: { fontSize: 14, fontWeight: '600' },
  meta: { fontSize: 11, marginTop: 2 },
  cancelBtn: { alignItems: 'center', justifyContent: 'center', paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10, borderWidth: 1, alignSelf: 'stretch' },
  cancelText: { fontSize: 13, fontWeight: '600' },
});
