import React, { useMemo, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { MOCK_EVENTS, CollectionEvent, EventType } from "@/mockData";
import { useAppTheme } from "@/hooks/useAppTheme";

// Compatibility: replace old ./ui/theme usage with app theme hook
const useAppColors = () => {
  const { colors } = useAppTheme();
  return colors;
};

type FilterTab = "all" | EventType;

const EventsDropsScreen: React.FC = () => {
  const colors = useAppColors();
  const [filter, setFilter] = useState<FilterTab>("all");

  const filteredEvents = useMemo(() => {
    if (filter === "all") return MOCK_EVENTS;
    return MOCK_EVENTS.filter((e) => e.type === filter);
  }, [filter]);

  const total = MOCK_EVENTS.length;
  const twitchCount = MOCK_EVENTS.filter((e) => e.type === "twitch").length;
  const dropCount = MOCK_EVENTS.filter((e) => e.type === "drop").length;
  const localCount = MOCK_EVENTS.filter((e) => e.type === "local").length;

  const typeIcon = (t: EventType) => {
    switch (t) {
      case "twitch":
        return "logo-twitch";
      case "drop":
        return "flash-outline";
      case "local":
        return "location-outline";
      default:
        return "alert-circle-outline";
    }
  };

  const typeLabel = (t: EventType) => {
    switch (t) {
      case "twitch":
        return "Twitch stream";
      case "drop":
        return "Online drop";
      case "local":
        return "Local event";
      default:
        return t;
    }
  };

  return (
    <SafeAreaView
      style={[styles.safeArea, { backgroundColor: colors.background }]}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.title, { color: colors.text }]}>
              Events & drops (mock)
            </Text>
            <Text style={[styles.subtitle, { color: colors.muted }]}>
              Streams, releases and meetups that match your collection.
            </Text>
          </View>
          <View
            style={[
              styles.headerIconCircle,
              { backgroundColor: colors.chipBg },
            ]}
          >
            <Ionicons
              name="calendar-outline"
              size={20}
              color={colors.accent}
            />
          </View>
        </View>

        {/* Summary */}
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          <View style={styles.summaryRow}>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Upcoming
              </Text>
              <Text style={[styles.summaryValue, { color: colors.text }]}>
                {total}
              </Text>
            </View>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Twitch
              </Text>
              <Text style={[styles.summaryValue, { color: colors.text }]}>
                {twitchCount}
              </Text>
            </View>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Drops
              </Text>
              <Text style={[styles.summaryValue, { color: colors.text }]}>
                {dropCount}
              </Text>
            </View>
            <View style={styles.summaryBlock}>
              <Text style={[styles.summaryLabel, { color: colors.muted }]}>
                Local
              </Text>
              <Text style={[styles.summaryValue, { color: colors.text }]}>
                {localCount}
              </Text>
            </View>
          </View>
          <Text style={[styles.summaryHint, { color: colors.muted }]}>
            Later this will sync to your calendar and Twitch follows. Right now
            it is all mock data.
          </Text>
        </View>

        {/* Filter tabs */}
        <View style={styles.filterRow}>
          {[
            { id: "all" as FilterTab, label: "All" },
            { id: "twitch" as FilterTab, label: "Twitch" },
            { id: "drop" as FilterTab, label: "Drops" },
            { id: "local" as FilterTab, label: "Local" },
          ].map((tab) => {
            const active = tab.id === filter;
            return (
              <Pressable
                key={tab.id}
                onPress={() => setFilter(tab.id)}
                style={[
                  styles.filterChip,
                  {
                    backgroundColor: active ? colors.accent : colors.chipBg,
                    borderColor: active ? colors.accent : "transparent",
                  },
                ]}
                accessibilityRole="button"
                accessibilityLabel={`${tab.label}${active ? ', selected' : ''}`}
              >
                <Text
                  style={[
                    styles.filterChipText,
                    { color: active ? "#FFFFFF" : colors.muted },
                  ]}
                >
                  {tab.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* Events list */}
        <View
          style={[
            styles.card,
            {
              backgroundColor: colors.card,
              borderColor: colors.border,
              marginBottom: 24,
            },
          ]}
        >
          {filteredEvents.map((event: CollectionEvent, idx: number) => {
            const isLast = idx === filteredEvents.length - 1;

            return (
              <View key={event.id}>
                <View style={styles.eventRow}>
                  <View style={styles.eventIconWrap}>
                    <Ionicons
                      name={typeIcon(event.type) as keyof typeof Ionicons.glyphMap}
                      size={18}
                      color={colors.accent}
                    />
                  </View>
                  <View style={styles.eventMain}>
                    <Text
                      style={[styles.eventTitle, { color: colors.text }]}
                      numberOfLines={1}
                    >
                      {event.title}
                    </Text>
                    <Text
                      style={[styles.eventMeta, { color: colors.muted }]}
                      numberOfLines={1}
                    >
                      {event.date} · {event.time} · {event.platform}
                    </Text>
                    <Text
                      style={[styles.eventDesc, { color: colors.muted }]}
                      numberOfLines={2}
                    >
                      {event.description}
                    </Text>
                    <View style={styles.tagRow}>
                      <View
                        style={[
                          styles.typeTag,
                          { backgroundColor: colors.chipBg },
                        ]}
                      >
                        <Text
                          style={[
                            styles.typeTagText,
                            { color: colors.muted },
                          ]}
                        >
                          {typeLabel(event.type)}
                        </Text>
                      </View>
                      {event.tags.map((tag) => (
                        <View
                          key={tag}
                          style={[
                            styles.tag,
                            { borderColor: colors.border },
                          ]}
                        >
                          <Text
                            style={[
                              styles.tagText,
                              { color: colors.muted },
                            ]}
                          >
                            {tag}
                          </Text>
                        </View>
                      ))}
                    </View>
                  </View>
                  <View style={styles.eventActions}>
                    <Pressable style={styles.addButton} accessibilityRole="button" accessibilityLabel={`Add ${event.title} to calendar`}>
                      <Ionicons
                        name="calendar-outline"
                        size={14}
                        color="#FFFFFF"
                      />
                    </Pressable>
                    <Text
                      style={[styles.addButtonLabel, { color: colors.muted }]}
                    >
                      Add (mock)
                    </Text>
                  </View>
                </View>
                {!isLast && (
                  <View
                    style={[
                      styles.separator,
                      { backgroundColor: colors.border },
                    ]}
                  />
                )}
              </View>
            );
          })}

          {filteredEvents.length === 0 && (
            <Text style={[styles.emptyText, { color: colors.muted }]}>
              No events of this type yet. Later we will pull from Twitch,
              product drops and local stores.
            </Text>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  scroll: { flex: 1 },
  scrollContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 13,
    marginTop: 4,
  },
  headerIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 16,
  },
  summaryRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  summaryBlock: {
    flex: 1,
    marginRight: 8,
  },
  summaryLabel: {
    fontSize: 11,
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: "600",
    marginTop: 2,
  },
  summaryHint: {
    fontSize: 11,
    marginTop: 4,
  },
  filterRow: {
    flexDirection: "row",
    marginBottom: 8,
  },
  filterChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    marginRight: 8,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
  },
  eventRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 8,
  },
  eventIconWrap: {
    marginRight: 8,
    marginTop: 4,
  },
  eventMain: {
    flex: 1,
    marginRight: 8,
  },
  eventTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  eventMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  eventDesc: {
    fontSize: 12,
    marginTop: 4,
  },
  tagRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 6,
  },
  typeTag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  typeTagText: {
    fontSize: 11,
    fontWeight: "600",
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    borderWidth: 1,
  },
  tagText: {
    fontSize: 11,
  },
  eventActions: {
    alignItems: "center",
  },
  addButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#19A7AE",
  },
  addButtonLabel: {
    fontSize: 10,
    marginTop: 4,
  },
  separator: {
    height: StyleSheet.hairlineWidth,
    marginVertical: 6,
  },
  emptyText: {
    fontSize: 12,
    textAlign: "center",
    marginTop: 6,
  },
});

export default EventsDropsScreen;
