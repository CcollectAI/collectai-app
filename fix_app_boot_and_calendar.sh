#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

echo "==> Fixing app/index.tsx (simple redirect into tabs)..."

INDEX_FILE="app/index.tsx"
INDEX_BAK="${INDEX_FILE}.bak_rescue_$(date +%s)"

if [ -f "$INDEX_FILE" ]; then
  cp "$INDEX_FILE" "$INDEX_BAK"
  echo "  Backed up app/index.tsx to:"
  echo "    $INDEX_BAK"
fi

cat > "$INDEX_FILE" <<'TSX'
import React from "react";
import { Redirect } from "expo-router";

/**
 * Root entry – send user into the main tab nav (Portfolio as default).
 */
export default function Index() {
  return <Redirect href="/(tabs)/portfolio" />;
}
TSX

echo "  app/index.tsx overwritten with safe redirect."

echo
echo "==> Fixing app/calendar-v1-demo.tsx (simple themed version, no SafeAreaView)..."

CAL_FILE="app/calendar-v1-demo.tsx"
CAL_BAK="${CAL_FILE}.bak_rescue_$(date +%s)"

if [ -f "$CAL_FILE" ]; then
  cp "$CAL_FILE" "$CAL_BAK"
  echo "  Backed up app/calendar-v1-demo.tsx to:"
  echo "    $CAL_BAK"
else
  echo "  WARNING: app/calendar-v1-demo.tsx not found; creating new file."
fi

cat > "$CAL_FILE" <<'TSX'
import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { supabase } from "@/lib/supabaseClient";

type TabKey = "MY" | "DROPS";

type CalendarEvent = {
  id: string;
  kind: "MY" | "DROPS";
  title: string;
  description?: string | null;
  event_date: string; // YYYY-MM-DD
};

const useCalendarEvents = () => {
  const [myEvents, setMyEvents] = useState<CalendarEvent[]>([]);
  const [dropEvents, setDropEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, error } = await supabase
      .from("events")
      .select("*")
      .order("event_date", { ascending: true });

    if (error) {
      console.warn("Failed to load events from Supabase", error);
      setError("Could not load events.");
      setLoading(false);
      return;
    }

    const mapped: CalendarEvent[] = (data ?? []).map((row: any) => ({
      id: row.id,
      kind: row.kind,
      title: row.title,
      description: row.description,
      event_date: row.event_date,
    }));

    setMyEvents(mapped.filter((e) => e.kind === "MY"));
    setDropEvents(mapped.filter((e) => e.kind === "DROPS"));
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { myEvents, dropEvents, loading, error, reload: load };
};

const formatDate = (isoDate: string) => {
  try {
    const d = new Date(isoDate);
    if (Number.isNaN(d.getTime())) return isoDate;
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return isoDate;
  }
};

const CalendarEventCard: React.FC<{
  ev: CalendarEvent;
  onPress: () => void;
}> = ({ ev, onPress }) => {
  return (
    <Pressable onPress={onPress} style={{ marginBottom: 10 }}>
      <View
        style={{
          padding: 12,
          borderRadius: 10,
          borderWidth: 1,
          borderColor: "#D5E6EC",
          backgroundColor: "#FFFFFF",
        }}
      >
        <Text style={{ fontSize: 13, opacity: 0.8, marginBottom: 4 }}>
          {formatDate(ev.event_date)}
        </Text>
        <Text style={{ fontSize: 15, fontWeight: "600", marginBottom: 4 }}>
          {ev.title}
        </Text>
        {ev.description ? (
          <Text
            style={{ fontSize: 13, opacity: 0.85 }}
            numberOfLines={2}
            ellipsizeMode="tail"
          >
            {ev.description}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
};

export default function CalendarV1DemoScreen() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>("MY");
  const { myEvents, dropEvents, loading, error, reload } = useCalendarEvents();

  const events = activeTab === "MY" ? myEvents : dropEvents;

  const handleAddEvent = () => {
    router.push({
      pathname: "/calendar-add-event-demo",
      params: { kind: activeTab },
    });
  };

  const handleEventPress = (ev: CalendarEvent) => {
    router.push({
      pathname: "/calendar-event-detail-demo",
      params: { id: ev.id },
    });
  };

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: "#F0FAFC", // light Tiffany-ish
      }}
    >
      {/* Fake safe area padding at top to avoid notch bleed */}
      <View style={{ height: 40 }} />

      {/* Header */}
      <View
        style={{
          paddingHorizontal: 16,
          paddingBottom: 8,
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: "700", color: "#003B4A" }}>
          Events & drops
        </Text>
        <Text
          style={{
            fontSize: 13,
            opacity: 0.8,
            marginTop: 4,
            color: "#335B63",
          }}
        >
          Track your own events plus major releases.
        </Text>
      </View>

      {/* Tabs */}
      <View
        style={{
          marginTop: 8,
          paddingHorizontal: 16,
        }}
      >
        <View
          style={{
            flexDirection: "row",
            gap: 8,
          }}
        >
          <Pressable
            onPress={() => setActiveTab("MY")}
            style={{
              flex: 1,
              paddingVertical: 8,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: activeTab === "MY" ? "#00A3C4" : "#C1D8E0",
              backgroundColor: activeTab === "MY" ? "#D7F3FA" : "#FFFFFF",
              alignItems: "center",
            }}
          >
            <Text
              style={{
                fontSize: 13,
                fontWeight: "600",
                color: activeTab === "MY" ? "#003B4A" : "#4A4A4A",
              }}
            >
              My events
            </Text>
          </Pressable>
          <Pressable
            onPress={() => setActiveTab("DROPS")}
            style={{
              flex: 1,
              paddingVertical: 8,
              borderRadius: 999,
              borderWidth: 1,
              borderColor: activeTab === "DROPS" ? "#00A3C4" : "#C1D8E0",
              backgroundColor: activeTab === "DROPS" ? "#D7F3FA" : "#FFFFFF",
              alignItems: "center",
            }}
          >
            <Text
              style={{
                fontSize: 13,
                fontWeight: "600",
                color: activeTab === "DROPS" ? "#003B4A" : "#4A4A4A",
              }}
            >
              Major drops
            </Text>
          </Pressable>
        </View>
      </View>

      {/* Content */}
      <ScrollView
        style={{ flex: 1, marginTop: 12 }}
        contentContainerStyle={{
          paddingHorizontal: 16,
          paddingBottom: 24,
        }}
      >
        {loading ? (
          <View
            style={{
              paddingVertical: 24,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ActivityIndicator />
            <Text style={{ marginTop: 8, fontSize: 13, opacity: 0.7 }}>
              Loading events…
            </Text>
          </View>
        ) : error ? (
          <View
            style={{
              paddingVertical: 24,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <View
              style={{
                padding: 12,
                borderRadius: 10,
                borderWidth: 1,
                borderColor: "#D5E6EC",
                backgroundColor: "#FFFFFF",
                alignItems: "center",
              }}
            >
              <Text style={{ fontSize: 13, opacity: 0.9, marginBottom: 8 }}>
                {error}
              </Text>
              <Pressable
                onPress={reload}
                style={{
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                  borderRadius: 999,
                  backgroundColor: "#00A3C4",
                }}
              >
                <Text
                  style={{
                    color: "#FFFFFF",
                    fontSize: 13,
                    fontWeight: "600",
                  }}
                >
                  Retry
                </Text>
              </Pressable>
            </View>
          </View>
        ) : events.length === 0 ? (
          <View
            style={{
              paddingVertical: 24,
            }}
          >
            <View
              style={{
                padding: 12,
                borderRadius: 10,
                borderWidth: 1,
                borderColor: "#D5E6EC",
                backgroundColor: "#FFFFFF",
                alignItems: "center",
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: "600",
                  marginBottom: 4,
                  color: "#003B4A",
                }}
              >
                No events yet
              </Text>
              <Text
                style={{
                  fontSize: 13,
                  opacity: 0.8,
                  textAlign: "center",
                  marginBottom: 12,
                  color: "#335B63",
                }}
              >
                {activeTab === "MY"
                  ? "Create your first event to track tournaments, meetups, or personal milestones."
                  : "Add upcoming set releases or big drops you want to watch."}
              </Text>
              <Pressable
                onPress={handleAddEvent}
                style={{
                  paddingHorizontal: 16,
                  paddingVertical: 9,
                  borderRadius: 999,
                  backgroundColor: "#00A3C4",
                }}
              >
                <Text
                  style={{
                    color: "#FFFFFF",
                    fontSize: 13,
                    fontWeight: "600",
                  }}
                >
                  Add event
                </Text>
              </Pressable>
            </View>
          </View>
        ) : (
          <>
            <View
              style={{
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <Text
                style={{
                  fontSize: 13,
                  opacity: 0.8,
                  color: "#335B63",
                }}
              >
                {events.length} event{events.length === 1 ? "" : "s"}
              </Text>
              <Pressable onPress={handleAddEvent}>
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: "600",
                    color: "#00A3C4",
                  }}
                >
                  + Add event
                </Text>
              </Pressable>
            </View>

            {events.map((ev) => (
              <CalendarEventCard
                key={ev.id}
                ev={ev}
                onPress={() => handleEventPress(ev)}
              />
            ))}
          </>
        )}
      </ScrollView>
    </View>
  );
}
TSX

echo "  app/calendar-v1-demo.tsx overwritten with simplified themed version."

echo
echo "✅ Done. app should now boot into tabs again, and calendar uses Supabase without SafeAreaView."
