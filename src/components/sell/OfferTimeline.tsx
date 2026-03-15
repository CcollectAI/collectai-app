/**
 * OfferTimeline — Negotiation history timeline for P2P deals.
 * Extracted from sell/[offerId].tsx.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { formatPrice } from '@/lib/format';
import { timeAgo } from '@/lib/timeAgo';
import type { OfferEvent } from '@/data/types';
import { radius, text, fontWeight } from '@/theme/tokens';

const EVENT_DISPLAY_META: Record<string, { icon: keyof typeof Ionicons.glyphMap; label: string; colorKey: 'accent' | 'info' | 'success' | 'danger' | 'muted' | 'warning' }> = {
  proposed: { icon: 'pricetag-outline', label: 'Offer proposed', colorKey: 'accent' },
  countered: { icon: 'swap-horizontal-outline', label: 'Counter-offer', colorKey: 'info' },
  accepted: { icon: 'checkmark-circle-outline', label: 'Offer accepted', colorKey: 'success' },
  declined: { icon: 'close-circle-outline', label: 'Offer declined', colorKey: 'danger' },
  cancelled: { icon: 'ban-outline', label: 'Offer cancelled', colorKey: 'muted' },
  shipped: { icon: 'airplane-outline', label: 'Marked as shipped', colorKey: 'accent' },
  completed: { icon: 'checkmark-done-outline', label: 'Deal completed', colorKey: 'success' },
  expired: { icon: 'time-outline', label: 'Offer expired', colorKey: 'muted' },
};

function getEventDisplay(eventType: string, colors: ReturnType<typeof useAppTheme>['colors']) {
  const meta = EVENT_DISPLAY_META[eventType];
  if (!meta) return { icon: 'ellipsis-horizontal-outline' as keyof typeof Ionicons.glyphMap, label: eventType, color: colors.muted };
  return { icon: meta.icon, label: meta.label, color: colors[meta.colorKey] };
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
    ' at ' +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

type Props = {
  events: OfferEvent[];
  currency: string;
};

function OfferTimelineInner({ events, currency }: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const displayCurrency = (currency || settings.currency) as 'EUR';

  return (
    <View style={styles.timelineSection}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>Negotiation Timeline</Text>
      {events.length === 0 ? (
        <Text style={[styles.noEvents, { color: colors.muted }]}>No events yet</Text>
      ) : (
        events.map((ev, idx) => {
          const evDisplay = getEventDisplay(ev.eventType, colors);
          const isLast = idx === events.length - 1;

          return (
            <View key={ev.id} style={styles.timelineItem}>
              {/* Vertical line */}
              {!isLast && (
                <View style={[styles.timelineLine, { backgroundColor: colors.border }]} />
              )}
              {/* Dot */}
              <View style={[styles.timelineDot, { backgroundColor: evDisplay.color }]}>
                <Ionicons name={evDisplay.icon} size={14} color="#fff" />
              </View>
              {/* Content */}
              <View style={styles.timelineContent}>
                <Text style={[styles.timelineLabel, { color: colors.text }]}>
                  {evDisplay.label}
                </Text>
                {ev.price != null && (
                  <Text style={[styles.timelinePrice, { color: colors.accent }]}>
                    {formatPrice(ev.price, displayCurrency)}
                  </Text>
                )}
                {ev.message ? (
                  <Text style={[styles.timelineMessage, { color: colors.muted }]}>
                    &ldquo;{ev.message}&rdquo;
                  </Text>
                ) : null}
                <Text style={[styles.timelineTime, { color: colors.muted }]}>
                  {formatDateTime(ev.createdAt)}
                </Text>
              </View>
            </View>
          );
        })
      )}
    </View>
  );
}

export const OfferTimeline = React.memo(OfferTimelineInner);

const styles = StyleSheet.create({
  timelineSection: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
    marginBottom: 14,
  },
  noEvents: {
    fontSize: text.md,
    fontStyle: 'italic',
  },
  timelineItem: {
    flexDirection: 'row',
    paddingLeft: 4,
    marginBottom: 18,
    position: 'relative',
  },
  timelineLine: {
    position: 'absolute',
    left: 15,
    top: 28,
    bottom: -18,
    width: 2,
    borderRadius: 1,
  },
  timelineDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  timelineContent: {
    flex: 1,
    paddingTop: 2,
  },
  timelineLabel: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  timelinePrice: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
    marginTop: 2,
  },
  timelineMessage: {
    fontSize: text.md,
    fontStyle: 'italic',
    marginTop: 4,
    lineHeight: 18,
  },
  timelineTime: {
    fontSize: text.xs,
    marginTop: 4,
  },
});
