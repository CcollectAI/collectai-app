import React from "react";
import { View, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { theme } from "../theme";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";

export default function Header({ title = "Collectors" }: { title?: string }) {
  const router = useRouter();
  const { settings } = useSettings();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingHorizontal: theme.spacing.lg,
        paddingTop: theme.spacing.md,
        paddingBottom: theme.spacing.sm,
        backgroundColor: theme.colors.bg,
      }}
    >
      <Text style={{ fontSize: 22, fontWeight: "800", color: theme.colors.text }}>{title}</Text>
      <AnimatedPressable
        onPress={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          router.push("/settings");
        }}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        accessibilityRole="button"
        accessibilityLabel="Settings"
        style={{
          width: 36,
          height: 36,
          borderRadius: 18,
          backgroundColor: "#fff",
          alignItems: "center",
          justifyContent: "center",
          borderWidth: 1,
          borderColor: theme.colors.border,
          ...theme.shadow.card,
        }}
      >
        <Ionicons name="settings-outline" size={20} color="#0F172A" />
      </AnimatedPressable>
    </View>
  );
}
