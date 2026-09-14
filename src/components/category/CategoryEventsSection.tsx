import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { useTranslation } from 'react-i18next';
import type { AppTheme } from '@/hooks/useAppTheme';
import { KIND_ICON, KIND_LABEL } from '@/constants/eventConstants';
import type { EventKind } from '@/data/events';
import { formatEventWhen } from '@/lib/calendar';

type CategoryEvent = {
  id: string;
  title: string;
  kind: EventKind;
  date: string;
  time?: string;
};

// Kind icon + label come from the shared constants. This file used to carry its
// own copies, and they had already drifted: "convention" was `business-outline`
// here and `map-outline` everywhere else, "Drop" here and "Collection drop" on
// the Events tab.

type Props = {
  events: CategoryEvent[];
  onEventPress: (eventId: string) => void;
  colors: AppTheme['colors'];
};

const CategoryEventsSection: React.FC<Props> = ({ events, onEventPress, colors }) => {
  const { t } = useTranslation();
  // Hide the section entirely when this category has no events, rather than
  // rendering a permanent "No upcoming events" placeholder — most categories
  // have zero events pre-launch, so the empty state showed on nearly every page.
  if (events.length === 0) return null;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>
        {t('category.upcoming_events', { defaultValue: 'Upcoming events' })}
      </Text>
      {events.map((event) => {
        const kind = KIND_LABEL[event.kind] ?? event.kind;
        // formatEventWhen, not the raw fields: this row printed
        // "Convention · 2026-09-17 · 16:00:00" — the 2026-09-09 bug
        // (docs/ui-playbook.md "A backend field is a value") in a seventh place.
        const when = formatEventWhen(event.date, event.time);
        return (
          <AnimatedPressable
            key={event.id}
            style={[styles.eventCard, { backgroundColor: colors.card, borderColor: colors.border }]}
            onPress={() => onEventPress(event.id)}
            accessibilityRole="button"
            accessibilityLabel={`${event.title}, ${kind}, ${when}`}
          >
            <View
              style={[
                styles.eventIconBubble,
                { backgroundColor: colors.accent },
              ]}
            >
              <Ionicons
                name={KIND_ICON[event.kind] ?? 'calendar-outline'}
                size={18}
                color={colors.accentText}
              />
            </View>
            <View style={styles.eventInfo}>
              <Text style={[styles.eventTitle, { color: colors.text }]} numberOfLines={1}>
                {event.title}
              </Text>
              <Text style={[styles.eventMeta, { color: colors.muted }]}>
                {kind} · {when}
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </AnimatedPressable>
        );
      })}
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
