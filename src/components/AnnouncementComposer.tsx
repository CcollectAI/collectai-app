/**
 * AnnouncementComposer — Inline announcement creation form with event selector.
 * Extracted from sponsor/dashboard.tsx for reusability and file-size reduction.
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { CollectorsEvent } from '@/data/events';
import { useAppTheme } from '@/hooks/useAppTheme';

/* -------------------------------------------------------------------------- */
/*  Helper                                                                     */
/* -------------------------------------------------------------------------- */

function getEventStatusColor(event: CollectorsEvent, dangerColor: string): string {
  if (event.status === 'cancelled') return dangerColor;
  if (event.status === 'draft') return '#F59E0B';
  const eventDate = new Date(event.date);
  const now = new Date();
  if (eventDate < now) return '#94A3B8';
  return '#10B981';
}

/* -------------------------------------------------------------------------- */
/*  Props                                                                      */
/* -------------------------------------------------------------------------- */

export type AnnouncementComposerProps = {
  /** List of events the sponsor owns — used for the event selector chips. */
  sponsoredEvents: CollectorsEvent[];

  /* ---- Compose state (lifted from parent) ---- */
  composeEventId: string | null;
  onComposeEventIdChange: (id: string) => void;
  composeTitle: string;
  onComposeTitleChange: (v: string) => void;
  composeBody: string;
  onComposeBodyChange: (v: string) => void;
  composeSending: boolean;

  /* ---- Actions ---- */
  onCancel: () => void;
  onSend: () => void;
};

/* -------------------------------------------------------------------------- */
/*  Shadows                                                                    */
/* -------------------------------------------------------------------------- */

const SHADOW_MD = Platform.select({
  ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 8 },
  android: { elevation: 3 },
  default: {},
}) as Record<string, unknown>;

/* -------------------------------------------------------------------------- */
/*  Component                                                                  */
/* -------------------------------------------------------------------------- */

const AnnouncementComposerInner: React.FC<AnnouncementComposerProps> = ({
  sponsoredEvents,
  composeEventId,
  onComposeEventIdChange,
  composeTitle,
  onComposeTitleChange,
  composeBody,
  onComposeBodyChange,
  composeSending,
  onCancel,
  onSend,
}) => {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.composeCard, { backgroundColor: colors.card, borderColor: colors.accent }, SHADOW_MD]}>
      <View style={styles.composeHeader}>
        <View style={[styles.composeIconCircle, { backgroundColor: colors.accent + '12' }]}>
          <Ionicons name="create-outline" size={14} color={colors.accent} />
        </View>
        <Text style={[styles.composeTitle, { color: colors.text }]}>New Announcement</Text>
      </View>

      <View style={[styles.composeDivider, { backgroundColor: colors.border }]} />

      {/* Event selector (if multiple events) */}
      {sponsoredEvents.length > 1 && (
        <View style={styles.composeField}>
          <Text style={[styles.composeLabel, { color: colors.muted }]}>Sending to</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.composeChipsRow}>
            {sponsoredEvents.map((ev) => {
              const isSelected = composeEventId === ev.id;
              return (
                <AnimatedPressable
                  key={ev.id}
                  onPress={() => onComposeEventIdChange(ev.id)}
                  style={[
                    styles.composeChip,
                    { borderColor: isSelected ? colors.accent : colors.border },
                    isSelected && { backgroundColor: colors.accent + '08' },
                  ]}
                >
                  <View style={[styles.statusDot, { backgroundColor: getEventStatusColor(ev, colors.danger) }]} />
                  <Text
                    style={[styles.composeChipText, { color: isSelected ? colors.accent : colors.text }]}
                    numberOfLines={1}
                  >
                    {ev.title}
                  </Text>
                  {!!isSelected && <Ionicons name="checkmark" size={13} color={colors.accent} />}
                </AnimatedPressable>
              );
            })}
          </ScrollView>
        </View>
      )}

      {/* Subject */}
      <View style={styles.composeField}>
        <Text style={[styles.composeLabel, { color: colors.muted }]}>Subject</Text>
        <TextInput
          value={composeTitle}
          onChangeText={onComposeTitleChange}
          placeholder="Optional subject line"
          placeholderTextColor={colors.muted}
          style={[styles.composeInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
          accessibilityLabel="Announcement subject"
          returnKeyType="next"
        />
      </View>

      {/* Message */}
      <View style={styles.composeField}>
        <Text style={[styles.composeLabel, { color: colors.muted }]}>Message</Text>
        <TextInput
          value={composeBody}
          onChangeText={onComposeBodyChange}
          placeholder="Write your announcement..."
          placeholderTextColor={colors.muted}
          multiline
          numberOfLines={5}
          maxLength={2000}
          style={[styles.composeTextArea, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
          textAlignVertical="top"
          accessibilityLabel="Announcement message"
        />
        <View style={styles.composeTextAreaFooter}>
          <View style={[styles.composeHint, { backgroundColor: colors.accent + '06' }]}>
            <Ionicons name="information-circle-outline" size={11} color={colors.accent} />
            <Text style={[styles.composeHintText, { color: colors.accent }]}>
              Sent as a DM to all attendees
            </Text>
          </View>
          <Text style={[styles.composeCharCount, { color: composeBody.length > 1800 ? colors.danger : colors.muted }]}>
            {composeBody.length}/2,000
          </Text>
        </View>
      </View>

      <View style={[styles.composeDivider, { backgroundColor: colors.border }]} />

      {/* Actions */}
      <View style={styles.composeFooter}>
        <AnimatedPressable
          onPress={onCancel}
          style={[styles.outlineBtn, { borderColor: colors.border, flex: 1 }]}
          accessibilityRole="button"
          accessibilityLabel="Cancel"
        >
          <Text style={[styles.outlineBtnText, { color: colors.muted }]}>Cancel</Text>
        </AnimatedPressable>
        <AnimatedPressable
          onPress={onSend}
          disabled={composeSending || !composeBody.trim()}
          style={[
            styles.primaryBtn,
            { backgroundColor: composeBody.trim() ? colors.accent : colors.border, flex: 1 },
          ]}
          accessibilityRole="button"
          accessibilityLabel="Send announcement"
        >
          {!!composeSending ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <>
              <Ionicons name="send" size={13} color="#FFFFFF" />
              <Text style={styles.primaryBtnText}>Send</Text>
            </>
          )}
        </AnimatedPressable>
      </View>
    </View>
  );
};

export const AnnouncementComposer = React.memo(AnnouncementComposerInner);

/* -------------------------------------------------------------------------- */
/*  Styles                                                                     */
/* -------------------------------------------------------------------------- */

const styles = StyleSheet.create({
  composeCard: {
    borderRadius: 14,
    borderWidth: 1.5,
    padding: 16,
    marginBottom: 12,
  },
  composeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  composeIconCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  composeTitle: {
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: -0.1,
  },
  composeDivider: {
    height: 1,
    marginVertical: 14,
  },
  composeField: {
    marginBottom: 14,
  },
  composeLabel: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  composeChipsRow: {
    gap: 6,
    paddingRight: 4,
  },
  composeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
    borderWidth: 1,
  },
  composeChipText: {
    fontSize: 12,
    fontWeight: '600',
    maxWidth: 140,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  composeInput: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 11,
    fontSize: 14,
  },
  composeTextArea: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    fontSize: 14,
    minHeight: 100,
  },
  composeTextAreaFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  composeHint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  composeHintText: {
    fontSize: 10,
  },
  composeCharCount: {
    fontSize: 10,
    fontWeight: '600',
  },
  composeFooter: {
    flexDirection: 'row',
    gap: 10,
  },

  /* Shared buttons */
  primaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 11,
    paddingHorizontal: 18,
    borderRadius: 10,
  },
  primaryBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  outlineBtn: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 11,
    paddingHorizontal: 18,
    borderRadius: 10,
    borderWidth: 1,
  },
  outlineBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});

export default AnnouncementComposer;
