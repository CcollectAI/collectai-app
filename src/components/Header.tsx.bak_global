import React from "react";
import { View, Text, TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { theme } from "../theme";

export default function Header({ title = "Collectors" }: { title?: string }) {
  const router = useRouter();
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
      <TouchableOpacity
        onPress={() => router.push("/settings")}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
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
      </TouchableOpacity>
    </View>
  );
}
