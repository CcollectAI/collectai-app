import React from "react";
import { View, Text, TouchableOpacity } from "react-native";
import { theme } from "../theme";

export default function ActionTile({
  label,
  emoji = "⭐",
  onPress,
}: {
  label: string;
  emoji?: string;
  onPress?: () => void;
}) {
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.85}
      style={{
        width: "48%",
        backgroundColor: "#fff",
        borderRadius: theme.radius["2xl"],
        padding: theme.spacing.lg,
        margin: "1%",
        alignItems: "flex-start",
        justifyContent: "flex-start",
        borderWidth: 1,
        borderColor: theme.colors.border,
        ...theme.shadow.card,
      }}
    >
      <View
        style={{
          backgroundColor: theme.colors.brand.light,
          borderRadius: 12,
          paddingHorizontal: 10,
          paddingVertical: 6,
          marginBottom: 10,
        }}
      >
        <Text style={{ fontWeight: "800", color: "#0F172A" }}>{emoji}</Text>
      </View>
      <Text style={{ fontWeight: "800", color: theme.colors.text }}>{label}</Text>
    </TouchableOpacity>
  );
}
