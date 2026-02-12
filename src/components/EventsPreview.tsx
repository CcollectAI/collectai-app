import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";

export type EventItem = {
  id: string;
  title: string;
  start_at: string; // ISO
  category?: string;
  is_twitch?: boolean;
};

type Props = {
  events: EventItem[];
  onPressEvent?: (event: EventItem) => void;
};

export const EventsPreview: React.FC<Props> = ({ events, onPressEvent }) => {
  const upcoming = events.slice(0, 3);

  if (upcoming.length === 0) {
    return (
      <View style={styles.emptyWrap}>
        <Text style={styles.emptyText}>No upcoming events yet.</Text>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      {upcoming.map((event) => {
        const date = new Date(event.start_at);
        const dateLabel = `${date.getDate()}/${date.getMonth() + 1}`;
        return (
          <Pressable
            key={event.id}
            style={styles.card}
            onPress={() => onPressEvent?.(event)}
            accessibilityRole="button"
            accessibilityLabel={`${event.title}, ${dateLabel}${event.category ? `, ${event.category}` : ''}`}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>{event.title}</Text>
              <Text style={styles.meta}>
                {dateLabel}
                {event.category ? ` · ${event.category}` : ""}
              </Text>
            </View>
            {event.is_twitch && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>Twitch</Text>
              </View>
            )}
          </Pressable>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  wrap: {
    gap: 8,
    marginTop: 8,
  },
  emptyWrap: {
    paddingVertical: 8,
  },
  emptyText: {
    fontSize: 12,
    color: "#496C86",
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "white",
    borderRadius: 8,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  title: {
    fontSize: 13,
    fontWeight: "600",
    color: "#0B2342",
  },
  meta: {
    marginTop: 2,
    fontSize: 11,
    color: "#496C86",
  },
  badge: {
    marginLeft: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "#F2D9FF",
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "600",
    color: "#7B3FE4",
  },
});
