import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator } from "react-native";
import { supabase } from "@/lib/supabaseClient";

type Item = {
  id: string | number;
  title?: string;
  name?: string;
  created_at?: string;
};

export default function MyCollection() {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const { data, error } = await supabase
          .from("items")
          .select("id, title, name, created_at")
          .order("created_at", { ascending: false });
        if (error) throw error;
        if (mounted) setItems(data ?? []);
      } catch (e: any) {
        console.warn("Error loading collection:", e?.message);
        setItems([]);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  if (loading) {
    return <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}><ActivityIndicator /></View>;
  }

  if (!items.length) {
    return (
      <View style={{ flex: 1, padding: 20 }}>
        <Text style={{ fontSize: 18, fontWeight: "700" }}>My Collection</Text>
        <Text>No items yet.</Text>
      </View>
    );
  }

  return (
    <FlatList
      contentContainerStyle={{ padding: 16, gap: 8 }}
      data={items}
      keyExtractor={(item) => String(item.id)}
      renderItem={({ item }) => (
        <View style={{ padding: 14, borderRadius: 10, borderWidth: 1, borderColor: "#ddd", backgroundColor: "white" }}>
          <Text style={{ fontSize: 16, fontWeight: "600" }}>{item.title || item.name || `#${item.id}`}</Text>
          {item.created_at ? <Text style={{ color: "#666", marginTop: 2 }}>{new Date(item.created_at).toDateString()}</Text> : null}
        </View>
      )}
    />
  );
}
