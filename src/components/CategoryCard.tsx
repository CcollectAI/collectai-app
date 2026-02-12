import React from "react";
import { Pressable, Text } from "react-native";

type Props = { item?: { name?: string; emoji?: string }; onPress?: () => void };

export default function CategoryCard({ item, onPress }: Props) {
  const label = item?.name ?? "Category";
  const emoji = item?.emoji ?? "★";
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={{
        padding: 12,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#e5e7eb",
        backgroundColor: "#ffffff",
        gap: 6,
      }}
    >
      <Text style={{ fontWeight: "800", color: "#0F172A" }}>{emoji}</Text>
      <Text style={{ fontSize: 15, fontWeight: "700", color: "#111827" }}>{label}</Text>
    </Pressable>
  );
}
