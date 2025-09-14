import React, { useMemo } from "react";
import { View, Text, ActivityIndicator } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { FlashList } from "@shopify/flash-list";
import { theme } from "../../../src/theme";
import useItems from "../../../src/hooks/useItems";
import ItemCard from "../../../src/components/ItemCard";

export default function CategoryDetail() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { items, loading, refresh } = useItems();

  const filtered = useMemo(
    () => items.filter((it) => (it.category ?? "").toLowerCase() === String(slug ?? "").toLowerCase()),
    [items, slug]
  );

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, paddingTop: theme.spacing.sm }}>
      <Text style={{ fontSize: 22, fontWeight: "800", color: theme.colors.text, marginHorizontal: 16, marginBottom: 8 }}>
        {String(slug ?? "").toUpperCase()}
      </Text>

      {loading && filtered.length === 0 ? (
        <ActivityIndicator style={{ marginTop: 20 }} />
      ) : filtered.length === 0 ? (
        <Text style={{ color: theme.colors.muted, margin: 16 }}>No items yet in this category.</Text>
      ) : (
        <FlashList
          data={filtered}
          keyExtractor={(it) => it.id}
          numColumns={2}
          renderItem={({ item }) => <ItemCard item={item} />}
          estimatedItemSize={260}
          contentContainerStyle={{ paddingBottom: 50, paddingHorizontal: 6 }}
          onRefresh={refresh as any}
          refreshing={loading}
        />
      )}
    </View>
  );
}
