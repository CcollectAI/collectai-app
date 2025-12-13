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
