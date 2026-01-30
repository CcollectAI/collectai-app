import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  SafeAreaView,
} from "react-native";
import { router } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { dataProvider, type Item } from "@/data";

export default function SearchScreen() {
  const t = useAppTheme();
  const colors = (t as any)?.colors ?? (t as any);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setSearched(false);
      return;
    }

    setLoading(true);
    setError(null);
    setSearched(true);

    try {
      const items = await dataProvider.searchItems(trimmed);
      setResults(items);
    } catch (err: any) {
      console.warn("[Search] error:", err);
      setError(err?.message || "Search failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleItemPress = (item: Item) => {
    router.push({
      pathname: "/item/[id]",
      params: {
        id: item.id,
        name: item.name,
        category: item.category,
        value: String(item.price),
        imageUri: item.imageUrl || "",
      },
    });
  };

  const renderItem = ({ item }: { item: Item }) => (
    <Pressable
      style={[styles.itemRow, { backgroundColor: colors?.card ?? "#fff", borderColor: colors?.border ?? "#e0e0e0" }]}
      onPress={() => handleItemPress(item)}
    >
      <View style={styles.itemInfo}>
        <Text style={[styles.itemName, { color: colors?.text ?? "#000" }]} numberOfLines={1}>
          {item.name}
        </Text>
        <Text style={[styles.itemCategory, { color: colors?.mutedText ?? "#666" }]}>
          {item.category}
        </Text>
      </View>
      <Text style={[styles.itemPrice, { color: colors?.text ?? "#000" }]}>
        €{item.price}
      </Text>
    </Pressable>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors?.background ?? "#f5f7fa" }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors?.text ?? "#0b1f3a" }]}>
          Search
        </Text>
      </View>

      <View style={styles.searchRow}>
        <TextInput
          style={[
            styles.input,
            {
              backgroundColor: colors?.card ?? "#fff",
              borderColor: colors?.border ?? "#ddd",
              color: colors?.text ?? "#000",
            },
          ]}
          placeholder="Search items..."
          placeholderTextColor={colors?.mutedText ?? "#999"}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={handleSearch}
          returnKeyType="search"
        />
        <Pressable
          style={[styles.searchButton, { backgroundColor: colors?.accent ?? "#007AFF" }]}
          onPress={handleSearch}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.searchButtonText}>Search</Text>
          )}
        </Pressable>
      </View>

      {error && (
        <Text style={[styles.errorText, { color: "#B00020" }]}>{error}</Text>
      )}

      {searched && !loading && results.length === 0 && !error && (
        <Text style={[styles.emptyText, { color: colors?.mutedText ?? "#666" }]}>
          No items found for "{query}"
        </Text>
      )}

      <FlatList
        data={results}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
  },
  searchRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 8,
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
  },
  searchButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
    minWidth: 80,
  },
  searchButtonText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
  errorText: {
    paddingHorizontal: 16,
    paddingBottom: 8,
    fontSize: 13,
  },
  emptyText: {
    paddingHorizontal: 16,
    paddingVertical: 24,
    fontSize: 14,
    textAlign: "center",
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 8,
  },
  itemInfo: {
    flex: 1,
    marginRight: 12,
  },
  itemName: {
    fontSize: 15,
    fontWeight: "600",
  },
  itemCategory: {
    fontSize: 12,
    marginTop: 2,
  },
  itemPrice: {
    fontSize: 15,
    fontWeight: "700",
  },
});
