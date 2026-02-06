import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator, Alert } from "react-native";
import { supabase } from "@/lib/supabase";

type Item = {
  id: string | number;
  title?: string;
  name?: string;
  category_slug?: string | null;
  category?: string | null;
  created_at?: string;
};

export default function CategoryDetail({ slug }: { slug: string }) {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        // Try matching by category_slug first
        let query = supabase.from("items").select("id, title, name, category_slug, category, created_at");
        query = query.eq("category_slug", slug);
        let { data, error } = await query;
        if (error) throw error;

        // If none found, try a more lenient filter (category field)
        if (!data || data.length === 0) {
          const alt = await supabase
            .from("items")
            .select("id, title, name, category_slug, category, created_at")
            .eq("category", slug);
          if (alt.error) throw alt.error;
          data = alt.data ?? [];
        }

        if (mounted) setItems(data ?? []);
      } catch (e: any) {
        Alert.alert("Error", e?.message ?? "Failed to load items for category");
        setItems([]);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [slug]);

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <FlatList
      contentContainerStyle={{ padding: 16, gap: 8 }}
      data={items}
      keyExtractor={(it) => String(it.id)}
      ListHeaderComponent={
        <Text style={{ fontSize: 20, fontWeight: "700", marginBottom: 8 }}>
          {slug}
        </Text>
      }
      renderItem={({ item }) => (
        <View style={{ padding: 14, borderRadius: 10, borderWidth: 1, borderColor: "#ddd", backgroundColor: "white" }}>
          <Text style={{ fontSize: 16, fontWeight: "600" }}>{item.title || item.name || `#${item.id}`}</Text>
          {item.category_slug || item.category ? (
            <Text style={{ color: "#666", marginTop: 2 }}>
              {item.category_slug || item.category}
            </Text>
          ) : null}
        </View>
      )}
      ListEmptyComponent={<Text>No items in this category yet.</Text>}
    />
  );
}
