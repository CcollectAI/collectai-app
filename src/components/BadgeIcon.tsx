import React from "react";
import { Ionicons } from "@expo/vector-icons";

export default function BadgeIcon({
  tier = "silver",
  size = 18,
}: { tier?: "gold" | "silver" | "bronze"; size?: number }) {
  const color = tier === "gold" ? "#D4AF37" : tier === "silver" ? "#C0C0C0" : "#CD7F32";
  return <Ionicons name="shield" size={size} color={color} />;
}
