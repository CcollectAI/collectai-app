import React from "react";
import { Feather } from "@expo/vector-icons";
import { View } from "react-native";
import { theme } from "@/theme";

export default function BadgeIcon() {
  return (
    <View style={{ marginLeft: "auto" }}>
      <Feather name="shield" size={16} color={theme.colors.navy} />
    </View>
  );
}
