import React from "react";
import { View, Text, Pressable } from "react-native";
import { useRouter } from "expo-router";

/**
 * CTA banner for build & paint projects (Gunpla, minis, customs).
 */
export default function BuildProjectsBanner() {
  const router = useRouter();

  return (
    <View
      style={{
        marginTop: 8,
        marginBottom: 24,
        padding: 16,
        borderRadius: 12,
        backgroundColor: "#F7F2FF",
        borderWidth: 1,
        borderColor: "#D6C4F5",
      }}
    >
      <Text
        style={{
          fontSize: 14,
          fontWeight: "600",
          marginBottom: 4,
        }}
      >
        Build & paint projects
      </Text>
      <Text
        style={{
          fontSize: 12,
          marginBottom: 12,
          opacity: 0.85,
        }}
      >
        Track in-progress builds, paint queues, and kits that haven&apos;t hit
        your main portfolio yet.
      </Text>

      <Pressable
        // TODO: update this route to your real build/paint projects screen
        onPress={() => router.push("/build-paint-projects")}
        style={{
          alignSelf: "flex-start",
          paddingHorizontal: 14,
          paddingVertical: 8,
          borderRadius: 999,
          backgroundColor: "#7C5CFF",
        }}
      >
        <Text
          style={{
            color: "#FFFFFF",
            fontSize: 12,
            fontWeight: "600",
          }}
        >
          Open build & paint view
        </Text>
      </Pressable>
    </View>
  );
}
