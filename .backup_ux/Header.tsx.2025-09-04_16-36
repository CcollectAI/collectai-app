import React from "react";
import { View, Text, Pressable } from "react-native";
import { useRouter } from "expo-router";

type Props = {
  title: string;
  subtitle?: string;
  back?: boolean;
  right?: React.ReactNode;
};

export default function Header({ title, subtitle, back=false, right }: Props) {
  const router = useRouter();
  return (
    <View style={{
      paddingHorizontal: 16,
      paddingVertical: 12,
      borderBottomWidth: 1,
      borderColor: "#eee",
      backgroundColor: "#fff"
    }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          {back ? (
            <Pressable onPress={() => router.back()} hitSlop={10}>
              <Text style={{ fontSize: 16 }}>‹ Back</Text>
            </Pressable>
          ) : null}
          <Text style={{ fontSize: 20, fontWeight: "700" }}>{title}</Text>
        </View>
        <View>{right ?? null}</View>
      </View>
      {subtitle ? (
        <Text style={{ marginTop: 4, color: "#666" }}>{subtitle}</Text>
      ) : null}
    </View>
  );
}
