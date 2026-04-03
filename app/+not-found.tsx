import React from "react";
import { View, Text, Pressable } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";

export default function NotFoundScreen() {
  const pathname = usePathname();
  const router = useRouter();
  const { colors } = useAppTheme();

  return (
    <View
      style={{
        flex: 1,
        padding: 24,
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: colors.background,
      }}
    >
      <Text style={{ fontSize: 22, fontWeight: "700", marginBottom: 8, color: colors.text }}>
        Page not found
      </Text>
      <Text style={{ marginBottom: 16, textAlign: "center", color: colors.muted }}>
        The route{" "}
        <Text style={{ fontWeight: "600" }}>{pathname || "unknown"}</Text>{" "}
        does not match any screen.
      </Text>

      <Pressable
        onPress={() => router.replace("/(tabs)")}
        accessibilityRole="button"
        accessibilityLabel="Go to Portfolio"
        style={{
          paddingHorizontal: 20,
          paddingVertical: 10,
          borderRadius: 8,
          backgroundColor: colors.accent,
        }}
      >
        <Text style={{ color: colors.accentText, fontWeight: "600" }}>
          Go to Portfolio
        </Text>
      </Pressable>
    </View>
  );
}
