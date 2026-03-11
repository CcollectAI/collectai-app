import React, { memo } from "react";
import { View, Text } from "react-native";
import { AnimatedPressable } from "@/motion";
import { useAppTheme } from "@/hooks/useAppTheme";

function ActionTile({
  label,
  emoji = "⭐",
  onPress,
}: {
  label: string;
  emoji?: string;
  onPress?: () => void;
}) {
  const { colors, radius, spacing, shadow } = useAppTheme();
  return (
    <AnimatedPressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={{
        width: "48%",
        backgroundColor: colors.card,
        borderRadius: radius["2xl"],
        padding: spacing.lg,
        margin: "1%",
        alignItems: "flex-start",
        justifyContent: "flex-start",
        borderWidth: 1,
        borderColor: colors.border,
        ...shadow.card,
      }}
    >
      <View
        style={{
          backgroundColor: colors.brand.light,
          borderRadius: 12,
          paddingHorizontal: 10,
          paddingVertical: 6,
          marginBottom: 10,
        }}
      >
        <Text style={{ fontWeight: "800", color: colors.text }}>{emoji}</Text>
      </View>
      <Text style={{ fontWeight: "800", color: colors.text }}>{label}</Text>
    </AnimatedPressable>
  );
}

export default memo(ActionTile);
