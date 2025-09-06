import React from "react";
import { View, ActivityIndicator, RefreshControl } from "react-native";
import { FlashList } from "@shopify/flash-list";
import useItems from "../../../src/hooks/useItems";
import ItemCard from "../../../src/components/ItemCard";
import { theme } from "../../../src/theme";

export default function Collection() {
  const { items, loading, refresh } = useItems();

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, paddingTop: theme.spacing.sm }}>
      {loading && (!items || items.length === 0) ? (
        <ActivityIndicator style={{ marginTop: 40 }} />
      ) : (
        <FlashList
          data={items}
          keyExtractor={(it) => it.id}
          numColumns={2}
          renderItem={({ item }) => <ItemCard item={item} />}
          estimatedItemSize={260}
          contentContainerStyle={{ paddingBottom: 50, paddingHorizontal: 6 }}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
        />
      )}
    </View>
  );
}
