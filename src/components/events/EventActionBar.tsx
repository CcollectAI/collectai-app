/**
 * EventActionBar — External link button + share button.
 */

import React from 'react';
import { View, Text, StyleSheet, Linking, Share } from 'react-native';
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
      await Share.share({
        message: `${event.title}\n${event.date}${event.time ? ` at ${event.time}` : ''}${event.location ? `\n${event.location}` : ''}\n\nCheck it out on Sparrow Collect!`,
        title: event.title,
      });
    } catch {
      showToast({ message: 'Failed to share event', type: 'error' });
    }
  };

  return (
    <View style={styles.actionRow}>
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
    </View>
  );
});

const styles = StyleSheet.create({
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  primaryBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 24,
  },
  primaryBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },
  shareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 24,
    borderWidth: 1,
  },
  shareBtnText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
