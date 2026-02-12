import React, { useEffect, useState } from "react";
import { View, Text, FlatList, Pressable, ActivityIndicator, Alert } from "react-native";
import { supabase } from "@/lib/supabase";
import { router } from "expo-router";

type Category = {
  id?: string | number;
  slug?: string;
  name?: string;
  title?: string;
  cover_url?: string | null;
};

export default function Categories() {
  const [data, setData] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        // Try canonical categories table first
        const { data: cats, error } = await supabase
          .from("categories")
          .select("id, slug, name, title, cover_url")
          .order("name", { ascending: true });
        if (error) throw error;

        if (mounted) {
          setData(cats ?? []);
        }
      } catch (_e: unknown) {
        // Fallback: try to derive categories from items table (distinct)
        try {
          const { data: rows, error } = await supabase
            .from("items")
            .select("category_slug, category_name")
            .not("category_slug", "is", null);
          if (error) throw error;

          const map = new Map<string, Category>();
          (rows ?? []).forEach(r => {
            const slug = r.category_slug || r.category_name;
            if (!slug) return;
            map.set(slug, { slug, name: r.category_name || slug });
          });
          setData(Array.from(map.values()).sort((a, b) => (a.name ?? "").localeCompare(b.name ?? "")));
        } catch (_e2: unknown) {
          Alert.alert("Categories unavailable", "No categories table found and could not infer from items.");
          setData([]);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  function openCategory(cat: Category) {
    const slug = cat.slug || String(cat.id || cat.name || cat.title || "").toLowerCase().replace(/\s+/g, "-");
    router.push(`/categories/${encodeURIComponent(slug)}`);
  }

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!data.length) {
    return (
      <View style={{ flex: 1, padding: 16 }}>
        <Text style={{ fontSize: 18, fontWeight: "700", marginBottom: 8 }}>Categories</Text>
        <Text>No categories to show.</Text>
      </View>
    );
  }

  return (
    <FlatList
      contentContainerStyle={{ padding: 16, gap: 8 }}
      data={data}
      keyExtractor={(item, idx) => String(item.slug ?? item.id ?? item.name ?? idx)}
      renderItem={({ item }) => (
        <Pressable
          onPress={() => openCategory(item)}
          style={{ padding: 14, borderRadius: 10, borderWidth: 1, borderColor: "#ddd", backgroundColor: "white" }}
        >
          <Text style={{ fontSize: 16, fontWeight: "600" }}>{item.name || item.title || item.slug}</Text>
          {item.slug ? <Text style={{ color: "#666", marginTop: 2 }}>{item.slug}</Text> : null}
        </Pressable>
      )}
    />
  );
}
