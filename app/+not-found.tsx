import React from "react";
import { View, Text, Pressable } from "react-native";
import { Link, usePathname } from "expo-router";

export default function NotFoundScreen() {
  const pathname = usePathname();

  return (
    <View
      style={{
        flex: 1,
        padding: 24,
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#f9fafb",
      }}
    >
      <Text style={{ fontSize: 22, fontWeight: "700", marginBottom: 8 }}>
        Page not found
      </Text>
      <Text style={{ marginBottom: 16, textAlign: "center" }}>
        The route{" "}
        <Text style={{ fontWeight: "600" }}>{pathname || "unknown"}</Text>{" "}
        does not match any screen.
      </Text>

      <Link href={"/(tabs)/portfolio" as any} asChild>
        <Pressable
          accessibilityRole="link"
          accessibilityLabel="Go to Portfolio"
          style={{
            paddingHorizontal: 20,
            paddingVertical: 10,
            borderRadius: 8,
            backgroundColor: "#0f172a",
          }}
        >
          <Text style={{ color: "white", fontWeight: "600" }}>
            Go to Portfolio
          </Text>
        </Pressable>
      </Link>
    </View>
  );
}
