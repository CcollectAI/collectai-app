import React from "react";
import { View, FlatList } from "react-native";
import { CATEGORIES } from "../../../src/constants/categories";
import CategoryCard from "../../../src/components/CategoryCard";
import { theme } from "../../../src/theme";

export default function Categories() {
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, paddingTop: theme.spacing.sm }}>
      <FlatList
        data={CATEGORIES}
        keyExtractor={(it) => it.slug}
        numColumns={2}
        renderItem={({ item }) => (
          <CategoryCard
            item={item}
            onPress={() => {
              // later: router.push(`/categories/${item.slug}`)
            }}
          />
        )}
        contentContainerStyle={{ paddingHorizontal: 6, paddingBottom: 40 }}
      />
    </View>
  );
}
