import React from "react";
import { View } from "react-native";
import { theme } from "@/theme";

export default function BadgeIcon({ tier = "silver", size = 16 }: { tier?: "gold"|"silver"|"bronze"; size?: number }) {
  const color = tier === "gold" ? "#D4AF37" : tier === "silver" ? "#C0C0C0" : "#CD7F32";
  return (
    <View style={{
      width: size, height: size,
      backgroundColor: color,
      borderColor: theme.colors.border, borderWidth: 1
    }} />
  );
}
