import React from "react";
import { View, Text } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useAppTheme } from "@/hooks/useAppTheme";

export default function Header({ title = "Collectors" }: { title?: string }) {
  const router = useRouter();
  const { settings } = useSettings();
  const { colors, spacing, shadow } = useAppTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingHorizontal: spacing.lg,
        paddingTop: spacing.md,
        paddingBottom: spacing.sm,
        backgroundColor: colors.background,
      }}
    >
      <Text style={{ fontSize: 22, fontWeight: "800", color: colors.text }}>{title}</Text>
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
          backgroundColor: colors.card,
          alignItems: "center",
          justifyContent: "center",
          borderWidth: 1,
          borderColor: colors.border,
          ...shadow.card,
        }}
      >
        <Ionicons name="settings-outline" size={20} color={colors.text} />
      </AnimatedPressable>
    </View>
  );
}
