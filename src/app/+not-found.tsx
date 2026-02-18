import React from "react";
import { View, Text, Pressable } from "react-native";
import { Link, usePathname } from "expo-router";

export default function NotFoundScreen() {
  const pathname = usePathname();

  console.log("[SRC/+not-found] unmatched path:", pathname);

  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        backgroundColor: "#f1f5f9",
      }}
    >
      <Text style={{ fontSize: 20, fontWeight: "700", marginBottom: 8 }}>
        Route not found
      </Text>
      <Text style={{ marginBottom: 16, textAlign: "center" }}>
        The path <Text style={{ fontWeight: "600" }}>{pathname}</Text> does not
        match any screen.
      </Text>

      <Link href={"/portfolio" as any} asChild>
        <Pressable
          style={{
            paddingHorizontal: 20,
            paddingVertical: 10,
            borderRadius: 999,
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
