import React, { memo } from "react";
import { View, Text } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import { theme } from "../theme";
import { ItemRow } from "../hooks/useItems";
import { GRADING_ELIGIBLE_CATEGORIES } from "@/constants/categories";

type ItemCardProps = {
  item: ItemRow & { condition?: string };
};

function ItemCard({ item }: ItemCardProps) {
  const showGradeBadge =
    item.condition && item.category && GRADING_ELIGIBLE_CATEGORIES.has(item.category);

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
      accessibilityLabel={item.title ?? "Collectible item"}
      accessibilityRole="button"
    >
      <Image
        source={ item.image_url ? { uri: item.image_url } : require("../../assets/images/placeholder.png") }
        placeholder={ (item as ItemRow & { blurhash?: string }).blurhash ? { blurhash: (item as ItemRow & { blurhash?: string }).blurhash } : undefined }
        style={{ width: "100%", aspectRatio: 1 }}
        contentFit="cover"
        transition={200}
        cachePolicy="memory-disk"
        accessibilityLabel={`Photo of ${item.title ?? "item"}`}
      />
      <View style={{ padding: 10 }}>
        <Text numberOfLines={1} style={{ fontWeight: "700", color: theme.colors.text }}>
          {item.title}
        </Text>
        <Text style={{ color: theme.colors.muted, marginTop: 2 }}>
          {item.category ?? "Uncategorized"}
        </Text>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
          {typeof item.value === "number" ? (
            <View
              style={{
                alignSelf: "flex-start",
                backgroundColor: theme.colors.success + "15",
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
          {showGradeBadge ? (
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: 3,
                backgroundColor: theme.colors.brand.base + "15",
                paddingHorizontal: 6,
                paddingVertical: 3,
                borderRadius: 6,
              }}
            >
              <Ionicons name="shield-checkmark-outline" size={10} color={theme.colors.brand.base} />
              <Text style={{ fontSize: 10, fontWeight: "600", color: theme.colors.brand.base }}>
                {item.condition}
              </Text>
            </View>
          ) : null}
        </View>
      </View>
    </View>
  );
}

export default memo(ItemCard);
