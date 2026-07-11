import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import type { AppTheme } from '@/hooks/useAppTheme';

type CategoryEvent = {
  id: string;
  title: string;
  kind: string;
  date: string;
  time?: string;
};

const kindIcon: Record<string, keyof typeof Ionicons.glyphMap> = {
  collection_drop: 'cube-outline',
  meetup: 'people-outline',
  stream: 'logo-twitch',
  convention: 'business-outline',
  release: 'disc-outline',
};

const kindLabel: Record<string, string> = {
  collection_drop: 'Drop',
  meetup: 'Meetup',
  stream: 'Stream',
  convention: 'Convention',
  release: 'Release',
};

type Props = {
  events: CategoryEvent[];
  onEventPress: (eventId: string) => void;
  colors: AppTheme['colors'];
};

const CategoryEventsSection: React.FC<Props> = ({ events, onEventPress, colors }) => {
  // Hide the section entirely when this category has no events, rather than
  // rendering a permanent "No upcoming events" placeholder — most categories
  // have zero events pre-launch, so the empty state showed on nearly every page.
  if (events.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>Upcoming Events & Drops</Text>
      {events.map((event) => (
        <AnimatedPressable
          key={event.id}
          style={[styles.eventCard, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={() => onEventPress(event.id)}
          accessibilityRole="button"
          accessibilityLabel={`${event.title}, ${kindLabel[event.kind] || event.kind}, ${event.date}`}
        >
          <View
            style={[
              styles.eventIconBubble,
              { backgroundColor: colors.accent },
            ]}
          >
            <Ionicons
              name={kindIcon[event.kind] || 'calendar-outline'}
              size={18}
              color="#fff"
            />
          </View>
          <View style={styles.eventInfo}>
            <Text style={[styles.eventTitle, { color: colors.text }]} numberOfLines={1}>
              {event.title}
            </Text>
            <Text style={[styles.eventMeta, { color: colors.muted }]}>
              {kindLabel[event.kind] || event.kind} · {event.date}
              {event.time ? ` · ${event.time}` : ''}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </AnimatedPressable>
      ))}
    </View>
  );
};

export default React.memo(CategoryEventsSection);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  eventCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    marginBottom: 8,
  },
  eventIconBubble: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  eventInfo: {
    flex: 1,
    marginRight: 8,
  },
  eventTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  eventMeta: {
    fontSize: 11,
    marginTop: 2,
  },
});
