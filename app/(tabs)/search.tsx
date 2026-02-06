import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { dataProvider, type Item } from "@/data";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";

export default function SearchScreen() {
  const t = useAppTheme();
  const colors = (t as any)?.colors ?? (t as any);
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
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
  }, [query, settings.hapticsEnabled]);

  const handleItemPress = (item: Item) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
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
    <AnimatedPressable
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
    </AnimatedPressable>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors?.background ?? "#f5f7fa" }]}>
      <Animated.View style={[{ flex: 1 }, settings.animationsEnabled ? animatedStyle : undefined]}>
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Text style={[styles.title, { color: colors?.text ?? "#0b1f3a" }]}>
            Search
          </Text>
          <Text style={[styles.subtitle, { color: colors?.muted ?? colors?.mutedText ?? "#666" }]}>
            Find items in your collection.
          </Text>
        </View>
        <View style={styles.headerIcons}>
          <InboxHeaderButton color={colors?.text ?? "#0b1f3a"} size={22} />
          <ThemeToggleButton size={22} />
        </View>
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
        <AnimatedPressable
          style={[styles.searchButton, { backgroundColor: colors?.accent ?? "#007AFF" }]}
          onPress={handleSearch}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.searchButtonText}>Search</Text>
          )}
        </AnimatedPressable>
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
      </Animated.View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  headerLeft: {
    flex: 1,
  },
  headerIcons: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 12,
    marginTop: 4,
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
