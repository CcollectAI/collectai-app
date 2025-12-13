import React, { useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator } from "react-native";
import { supabase } from "@/lib/supabaseClient";

type Listing = {
  id: string|number;
  title?: string;
  price?: number|null;
  created_at?: string|null;
};

export default function Listings() {
  const [rows, setRows] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        // Adjust table/columns to your schema if different:
        const { data, error } = await supabase
          .from("listings")
          .select("id, title, price, created_at")
          .order("created_at", { ascending: false });
        if (error) throw error;
        if (mounted) setRows(data ?? []);
      } catch {
        setRows([]);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  if (loading) return <View style={{ flex:1, alignItems:"center", justifyContent:"center" }}><ActivityIndicator/></View>;

  if (!rows.length) {
    return (
      <View style={{ flex:1, padding:16 }}>
        <Text style={{ fontSize:18, fontWeight:"700", marginBottom:8 }}>Listings</Text>
        <Text>No listings yet.</Text>
      </View>
    );
  }

  return (
    <FlatList
      contentContainerStyle={{ padding: 16, gap: 8 }}
      data={rows}
      keyExtractor={(l) => String(l.id)}
      renderItem={({ item }) => (
        <View style={{ padding:14, borderRadius:10, borderWidth:1, borderColor:"#ddd", backgroundColor:"white" }}>
          <Text style={{ fontSize:16, fontWeight:"600" }}>{item.title || `#${item.id}`}</Text>
          {item.price != null ? <Text style={{ color:"#666", marginTop:2 }}>€{item.price}</Text> : null}
          {item.created_at ? <Text style={{ color:"#999", marginTop:2 }}>{new Date(item.created_at).toDateString()}</Text> : null}
        </View>
      )}
    />
  );
}
