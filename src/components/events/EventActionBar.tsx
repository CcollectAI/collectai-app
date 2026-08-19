/**
 * EventActionBar — External link button + share button.
 *
 * Returns the buttons as a FRAGMENT, not a row of its own. Share used to sit on
 * its own line directly above Going / Interested, so the event screen showed two
 * rows of pill buttons stacked on top of each other — reported 2026-08-17 as
 * wanting them "all aligned". `EventRsvpSection` now owns the single action row
 * and takes these as `leadingActions`, which is also why the metrics here match
 * `actionBtn` there exactly: two components drawing buttons into one row have to
 * agree on padding and radius or the row looks ragged.
 */

import React from 'react';
import { Text, StyleSheet, Linking, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useToast } from '@/components/Toast';
import logger from '@/utils/logger';
import type { CollectorsEvent } from '@/data/events';

interface EventActionBarProps {
  event: CollectorsEvent;
  hapticsEnabled: boolean;
}

export const EventActionBar = React.memo(function EventActionBar({
  event,
  hapticsEnabled,
}: EventActionBarProps) {
  const { colors } = useAppTheme();
  const { showToast } = useToast();

  const isStream = event.kind === 'stream';
  const isDrop = event.kind === 'collection_drop';

  const openExternal = () => {
    if (!event.onlineUrl) return;
    Linking.openURL(event.onlineUrl).catch((err) =>
      logger.info('[EventDetail] failed to open url', err),
    );
  };

  const handleShare = async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
    try {
      // Optimized for messaging (WhatsApp / iMessage): the details a recipient
      // needs (what, when, where) on their own lines + a tappable link — the
      // event's own URL when it has one, else the app site.
      const link = event.onlineUrl || 'https://sparrowcollect.com';
      const message =
        `${event.title}` +
        `\n${event.date}${event.time ? ` at ${event.time}` : ''}` +
        (event.location ? `\n${event.location}` : '') +
        `\n\n${link}` +
        `\n\nShared via Sparrow Collect`;
      await Share.share({ message, title: event.title });
    } catch {
      showToast({ message: 'Failed to share event', type: 'error' });
    }
  };

  return (
    <>
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
      <AnimatedPressable
        onPress={handleShare}
        style={[styles.shareBtn, { backgroundColor: colors.card, borderColor: colors.border }]}
        accessibilityRole="button"
        accessibilityLabel="Share this event"
      >
        <Ionicons name="share-outline" size={16} color={colors.accent} style={{ marginRight: 6 }} />
        <Text style={[styles.shareBtnText, { color: colors.accent }]}>Share</Text>
      </AnimatedPressable>
    </>
  );
});

// Padding, radius and label size are deliberately identical to `actionBtn` in
// EventRsvpSection — these buttons render inside THAT row. `flex: 1` used to
// stretch the primary button across its own row; in a shared row it would eat
// the whole line and push Going / Interested onto a second one, which is the
// bug being fixed. `flexShrink` + centred labels instead, per "flexWrap: 'wrap'
// on an action row strands the third button" in docs/ui-playbook.md.
const styles = StyleSheet.create({
  primaryBtn: {
    flexShrink: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
  },
  primaryBtnText: {
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },
  shareBtn: {
    flexShrink: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
  },
  shareBtnText: {
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },
});
