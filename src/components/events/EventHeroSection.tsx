/**
 * EventHeroSection — Hero image, badges (kind/source/cancelled), title,
 * date/time, countdown, location and description card.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { useAppTheme } from '@/hooks/useAppTheme';
import { KIND_ICON, KIND_LABEL } from '@/constants/eventConstants';
import { parseEventDate, getCountdown } from '@/lib/calendar';
import type { CollectorsEvent } from '@/data/events';

const EVENT_SOURCE_LABELS: Record<string, string> = {
  admin: 'Official',
  newsletter: 'Newsletter',
  community: 'Community',
  scraped: 'Scraped',
  user: 'Community',
};

interface EventHeroSectionProps {
  event: CollectorsEvent;
}

export const EventHeroSection = React.memo(function EventHeroSection({
  event,
}: EventHeroSectionProps) {
  const { colors } = useAppTheme();

  return (
    <>
      {/* Hero image */}
      {event.imageUrl && (
        <Image
          source={{ uri: event.imageUrl }}
          style={styles.heroImage}
          contentFit="cover"
          cachePolicy="memory-disk"
          transition={200}
        />
      )}

      {/* Cancelled banner */}
      {event.status === 'cancelled' && (
        <View style={[styles.cancelledBanner, { backgroundColor: colors.danger + '15' }]}>
          <Ionicons name="close-circle-outline" size={16} color={colors.danger} />
          <Text style={[styles.cancelledBannerText, { color: colors.danger }]}>This event has been cancelled</Text>
        </View>
      )}

      {/* Event Kind Badge */}
      <View style={[styles.kindBadge, { backgroundColor: colors.accent + '15', borderColor: colors.accent + '40' }]}>
        <Ionicons
          name={KIND_ICON[event.kind]}
          size={14}
          color={colors.accent}
          style={{ marginRight: 6 }}
        />
        <Text style={[styles.kindText, { color: colors.accent }]}>
          {KIND_LABEL[event.kind]}
        </Text>
      </View>

      {/* Source badge for scraped events */}
      {event.source && event.source !== 'user' && (
        <View style={[styles.sourceBadge, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Ionicons name="globe-outline" size={12} color={colors.muted} style={{ marginRight: 4 }} />
          <Text style={[styles.sourceText, { color: colors.muted }]}>
            {EVENT_SOURCE_LABELS[event.source] || event.source}
          </Text>
        </View>
      )}

      {/* Title & Date/Time */}
      <Text style={[styles.eventTitle, { color: colors.text }]}>
        {event.title}
      </Text>

      <View style={styles.metaRow}>
        <Ionicons name="calendar-outline" size={16} color={colors.muted} style={{ marginRight: 6 }} />
        <Text style={[styles.metaText, { color: colors.muted }]}>
          {event.date}
          {event.time ? ` \u2022 ${event.time}` : ''}
        </Text>
      </View>

      {event.date && (() => {
        const eventDate = parseEventDate(event.date, event.time);
        const countdown = getCountdown(eventDate);
        const isUpcoming = !countdown.isPast;
        return (
          <View style={[styles.countdownBadge, { backgroundColor: isUpcoming ? colors.accent + '15' : colors.border + '40' }]}>
            <Ionicons name={isUpcoming ? 'time-outline' : 'checkmark-circle-outline'} size={14} color={isUpcoming ? colors.accent : colors.muted} />
            <Text style={[styles.countdownText, { color: isUpcoming ? colors.accent : colors.muted }]}>{countdown.formatted}</Text>
          </View>
        );
      })()}

      {/* Ticket price badge */}
      {event.ticketPriceCents != null && event.ticketPriceCents > 0 && (
        <View style={[styles.ticketBadge, { backgroundColor: colors.warningBg, borderColor: colors.warning + '40' }]}>
          <Ionicons name="ticket-outline" size={14} color={colors.warning} style={{ marginRight: 6 }} />
          <Text style={[styles.ticketText, { color: colors.warning }]}>
            Ticket required · {(event.ticketPriceCents / 100).toFixed(2)}
          </Text>
        </View>
      )}

      {event.location && (
        <View style={styles.metaRow}>
          <Ionicons name="location-outline" size={16} color={colors.muted} style={{ marginRight: 6 }} />
          <Text style={[styles.metaText, { color: colors.muted }]}>
            {event.location}
          </Text>
        </View>
      )}

      {/* Description — only when there IS one. Rendered unconditionally, this
          card was an empty grey rectangle on every event without a description,
          which is most scraped ones (Ticketmaster feeds give us a title, a date
          and a venue and nothing else). A bordered card with no content reads as
          a component that failed to load, not as an absent optional field.
          `.trim()` because a whitespace-only string is the same nothing. */}
      {event.description?.trim() ? (
        <View style={[styles.descriptionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={[styles.descriptionText, { color: colors.text }]}>
            {event.description}
          </Text>
        </View>
      ) : null}
    </>
  );
});

const styles = StyleSheet.create({
  heroImage: {
    width: '100%',
    height: 200,
    borderRadius: 12,
    marginBottom: 16,
  },
  cancelledBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    marginBottom: 12,
  },
  cancelledBannerText: {
    fontSize: 13,
    fontWeight: '600',
  },
  kindBadge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    marginBottom: 8,
  },
  kindText: {
    fontSize: 12,
    fontWeight: '500',
  },
  sourceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 8,
  },
  sourceText: {
    fontSize: 11,
  },
  eventTitle: {
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 6,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 2,
  },
  metaText: {
    fontSize: 14,
  },
  countdownBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  countdownText: {
    fontSize: 13,
    fontWeight: '600',
  },
  ticketBadge: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    marginBottom: 8,
  },
  ticketText: {
    fontSize: 12,
    fontWeight: '500',
  },
  descriptionCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginTop: 12,
    marginBottom: 12,
  },
  descriptionText: {
    fontSize: 14,
    lineHeight: 20,
  },
});
