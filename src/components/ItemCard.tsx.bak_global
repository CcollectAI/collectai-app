import React from "react";
import { View, Text } from "react-native";
import { Image } from "expo-image";
import { theme } from "../theme";
import { ItemRow } from "../hooks/useItems";

export default function ItemCard({ item }: { item: ItemRow }) {
  return (
    <View
      style={{
        backgroundColor: theme.colors.card,
        borderRadius: theme.radius.xl,
        overflow: "hidden",
        margin: 6,
        width: "48%",
        ...theme.shadow.card,
      }}
    >
      <Image
        source={ item.image_url ? { uri: item.image_url } : require("../../assets/images/placeholder.png") }
        style={{ width: "100%", aspectRatio: 1 }}
        contentFit="cover"
        transition={200}
      />
      <View style={{ padding: 10 }}>
        <Text numberOfLines={1} style={{ fontWeight: "700", color: theme.colors.text }}>
          {item.title}
        </Text>
        <Text style={{ color: theme.colors.muted, marginTop: 2 }}>
          {item.category ?? "Uncategorized"}
        </Text>
        {typeof item.value === "number" ? (
          <View
            style={{
              marginTop: 8,
              alignSelf: "flex-start",
              backgroundColor: "#ECFDF5",
              borderRadius: 10,
              paddingHorizontal: 8,
              paddingVertical: 4,
            }}
          >
            <Text style={{ color: theme.colors.success, fontWeight: "800" }}>
              ${item.value.toFixed(0)}
            </Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}
