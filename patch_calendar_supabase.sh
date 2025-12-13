#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/ubuntu/collectors-merge-recovered"
cd "$PROJECT_ROOT"

CAL_FILE="app/calendar-v1-demo.tsx"
ADD_FILE="app/calendar-add-event-demo.tsx"

# --- Safety checks ---
if [ ! -f "$CAL_FILE" ]; then
  echo "ERROR: $CAL_FILE not found. Are you in the right project?"
  exit 1
fi

if [ ! -f "$ADD_FILE" ]; then
  echo "ERROR: $ADD_FILE not found. Are you in the right project?"
  exit 1
fi

# --- Backups ---
CAL_BAK="${CAL_FILE}.bak_supabase_$(date +%s)"
ADD_BAK="${ADD_FILE}.bak_supabase_$(date +%s)"

cp "$CAL_FILE" "$CAL_BAK"
cp "$ADD_FILE" "$ADD_BAK"

echo "📦 Backed up:"
echo "  $CAL_FILE -> $CAL_BAK"
echo "  $ADD_FILE -> $ADD_BAK"
echo

# --- Rewrite calendar-v1-demo.tsx with Supabase-backed events ---

cat > "$CAL_FILE" <<'TSX'
import React, { useEffect, useState, useCallback } from "react";
import { View, Text, ScrollView, Pressable, ActivityIndicator } from "react-native";
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
    <Pressable
      onPress={onPress}
      style={{
        padding: 12,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: "#E0E0E0",
        marginBottom: 10,
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
    </Pressable>
  );
};

export default function CalendarV1DemoScreen() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>("MY");

  const { myEvents, dropEvents, loading, error, reload } = useCalendarEvents();

  const events = activeTab === "MY" ? myEvents : dropEvents;

  const handleAddEvent = () => {
    // We pass the current tab as a hint for default kind
    router.push({
      pathname: "/calendar-add-event-demo",
      params: { kind: activeTab },
    });
  };

  const handleEventPress = (ev: CalendarEvent) => {
    // Detail screen is still demo-only; we just pass an id param for future use.
    router.push({
      pathname: "/calendar-event-detail-demo",
      params: { id: ev.id },
    });
  };

  return (
    <View style={{ flex: 1, backgroundColor: "#F5F7FA" }}>
      {/* Header */}
      <View
        style={{
          paddingHorizontal: 16,
          paddingTop: 16,
          paddingBottom: 8,
          backgroundColor: "#FFFFFF",
          borderBottomWidth: 1,
          borderBottomColor: "#E5E5E5",
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: "700" }}>
          Events & drops
        </Text>
        <Text style={{ fontSize: 13, opacity: 0.7, marginTop: 4 }}>
          Track your own events plus major releases.
        </Text>
      </View>

      {/* Tabs */}
      <View
        style={{
          flexDirection: "row",
          paddingHorizontal: 16,
          paddingVertical: 12,
          gap: 8,
          backgroundColor: "#FFFFFF",
        }}
      >
        <Pressable
          onPress={() => setActiveTab("MY")}
          style={{
            flex: 1,
            paddingVertical: 8,
            borderRadius: 999,
            borderWidth: 1,
            borderColor: activeTab === "MY" ? "#00A3C4" : "#D0D7DD",
            backgroundColor: activeTab === "MY" ? "#E0F7FC" : "#FFFFFF",
            alignItems: "center",
          }}
        >
          <Text
            style={{
              fontSize: 13,
              fontWeight: "600",
              color: activeTab === "MY" ? "#006A80" : "#4A4A4A",
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
            borderColor: activeTab === "DROPS" ? "#00A3C4" : "#D0D7DD",
            backgroundColor: activeTab === "DROPS" ? "#E0F7FC" : "#FFFFFF",
            alignItems: "center",
          }}
        >
          <Text
            style={{
              fontSize: 13,
              fontWeight: "600",
              color: activeTab === "DROPS" ? "#006A80" : "#4A4A4A",
            }}
          >
            Major drops
          </Text>
        </Pressable>
      </View>

      {/* Content */}
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{
          paddingHorizontal: 16,
          paddingTop: 8,
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
            <Text style={{ fontSize: 13, opacity: 0.85, marginBottom: 8 }}>
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
        ) : events.length === 0 ? (
          <View
            style={{
              paddingVertical: 24,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Text style={{ fontSize: 14, fontWeight: "600", marginBottom: 4 }}>
              No events yet
            </Text>
            <Text
              style={{
                fontSize: 13,
                opacity: 0.8,
                textAlign: "center",
                marginBottom: 12,
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

echo "✅ Updated $CAL_FILE to load events from Supabase."

# --- Rewrite calendar-add-event-demo.tsx to insert into Supabase ---

cat > "$ADD_FILE" <<'TSX'
import React, { useState } from "react";
import { View, Text, TextInput, Pressable, Alert, ScrollView } from "react-native";
import { useRouter, useLocalSearchParams } from "expo-router";
import { supabase } from "@/lib/supabaseClient";

type TabKey = "MY" | "DROPS";

export default function CalendarAddEventDemoScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ kind?: TabKey }>();

  const [title, setTitle] = useState("");
  const [date, setDate] = useState(""); // YYYY-MM-DD
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const defaultKind: TabKey = params.kind === "DROPS" ? "DROPS" : "MY";

  const handleSave = async () => {
    if (!title.trim() || !date.trim()) {
      Alert.alert("Missing information", "Please enter a title and date.");
      return;
    }

    setSaving(true);
    const { error } = await supabase.from("events").insert({
      kind: defaultKind,
      title: title.trim(),
      description: description.trim() || null,
      event_date: date.trim(), // expect 'YYYY-MM-DD'
    });

    setSaving(false);

    if (error) {
      console.warn("Error inserting event into Supabase", error);
      Alert.alert("Could not save", "Something went wrong while saving the event.");
      return;
    }

    // Go back to calendar; it will reload events.
    router.back();
  };

  return (
    <View style={{ flex: 1, backgroundColor: "#F5F7FA" }}>
      {/* Header */}
      <View
        style={{
          paddingHorizontal: 16,
          paddingTop: 16,
          paddingBottom: 8,
          backgroundColor: "#FFFFFF",
          borderBottomWidth: 1,
          borderBottomColor: "#E5E5E5",
        }}
      >
        <Text style={{ fontSize: 18, fontWeight: "700" }}>Add event</Text>
        <Text style={{ fontSize: 13, opacity: 0.7, marginTop: 4 }}>
          {defaultKind === "MY"
            ? "Create a personal event related to your collection."
            : "Add a major drop or release you want to track."}
        </Text>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{
          paddingHorizontal: 16,
          paddingTop: 16,
          paddingBottom: 24,
        }}
      >
        <View style={{ marginBottom: 16 }}>
          <Text style={{ fontSize: 13, fontWeight: "600", marginBottom: 4 }}>
            Title
          </Text>
          <TextInput
            value={title}
            onChangeText={setTitle}
            placeholder={
              defaultKind === "MY"
                ? "Friday locals at LGS"
                : "New set release: XYZ"
            }
            style={{
              borderWidth: 1,
              borderColor: "#D0D7DD",
              borderRadius: 8,
              paddingHorizontal: 10,
              paddingVertical: 8,
              backgroundColor: "#FFFFFF",
            }}
          />
        </View>

        <View style={{ marginBottom: 16 }}>
          <Text style={{ fontSize: 13, fontWeight: "600", marginBottom: 4 }}>
            Date (YYYY-MM-DD)
          </Text>
          <TextInput
            value={date}
            onChangeText={setDate}
            placeholder="2025-12-04"
            autoCorrect={false}
            autoCapitalize="none"
            style={{
              borderWidth: 1,
              borderColor: "#D0D7DD",
              borderRadius: 8,
              paddingHorizontal: 10,
              paddingVertical: 8,
              backgroundColor: "#FFFFFF",
            }}
          />
        </View>

        <View style={{ marginBottom: 24 }}>
          <Text style={{ fontSize: 13, fontWeight: "600", marginBottom: 4 }}>
            Notes (optional)
          </Text>
          <TextInput
            value={description}
            onChangeText={setDescription}
            placeholder={
              defaultKind === "MY"
                ? "Location, time, format, who you're meeting…"
                : "Link to announcement, expected impact, your plan…"
            }
            multiline
            style={{
              borderWidth: 1,
              borderColor: "#D0D7DD",
              borderRadius: 8,
              paddingHorizontal: 10,
              paddingVertical: 8,
              minHeight: 80,
              backgroundColor: "#FFFFFF",
              textAlignVertical: "top",
            }}
          />
        </View>

        <Pressable
          onPress={handleSave}
          disabled={saving}
          style={{
            marginTop: 8,
            paddingVertical: 12,
            borderRadius: 999,
            alignItems: "center",
            backgroundColor: saving ? "#9BCFD9" : "#00A3C4",
          }}
        >
          <Text
            style={{
              color: "#FFFFFF",
              fontSize: 14,
              fontWeight: "600",
            }}
          >
            {saving ? "Saving…" : "Save event"}
          </Text>
        </Pressable>

        <Pressable
          onPress={() => router.back()}
          disabled={saving}
          style={{
            marginTop: 12,
            alignItems: "center",
          }}
        >
          <Text
            style={{
              fontSize: 13,
              opacity: 0.8,
            }}
          >
            Cancel
          </Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}
TSX

echo "✅ Updated $ADD_FILE to insert new events into Supabase."

echo
echo "Done. Calendar now reads from and writes to Supabase 'events' table."
