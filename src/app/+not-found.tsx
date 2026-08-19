import React from "react";
import { View, Text, Pressable } from "react-native";
import { Link, usePathname, type Href } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";

export default function NotFoundScreen() {
  const pathname = usePathname();
  const { colors } = useAppTheme();

  if (__DEV__) console.log("[+not-found] unmatched path:", pathname);

  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        backgroundColor: colors.background,
      }}
    >
      <Text style={{ fontSize: 20, fontWeight: "700", marginBottom: 8, color: colors.text }}>
        Route not found
      </Text>
      <Text style={{ marginBottom: 16, textAlign: "center", color: colors.muted }}>
        The path <Text style={{ fontWeight: "600" }}>{pathname}</Text> does not
        match any screen.
      </Text>

      <Link href={"/portfolio" as Href} asChild>
        <Pressable
          style={{
            paddingHorizontal: 20,
            paddingVertical: 10,
            borderRadius: 999,
            backgroundColor: colors.accent,
          }}
        >
          <Text style={{ color: colors.accentText, fontWeight: "600" }}>
            Go to Portfolio
          </Text>
        </Pressable>
      </Link>
    </View>
  );
}
