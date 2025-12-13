import React, { useEffect, useState, useCallback } from "react";
import { View, Text, FlatList, RefreshControl, Pressable } from "react-native";
import { supabase } from "@/lib/supabase";

type Session = {
  id: string;
  user_id: string | null;
  category: string;
  status: "pending" | "processing" | "done" | "error";
  confidence: number | null;
  price_low_eur: number | null;
  price_mid_eur: number | null;
  price_high_eur: number | null;
  created_at: string;
};

export default function AdminReview() {
  const [rows, setRows] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [onlyLow, setOnlyLow] = useState(true);

  const fetchRows = useCallback(async () => {
    setLoading(true);
    const { data, error } = await supabase
      .from("prediction_sessions")
      .select("id,user_id,category,status,confidence,price_low_eur,price_mid_eur,price_high_eur,created_at")
      .order("created_at", { ascending: false })
      .limit(100);
    if (!error && data) {
      setRows(onlyLow ? data.filter(d => (d.confidence ?? 1) < 0.6) : data);
    }
    setLoading(false);
  }, [onlyLow]);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  return (
    <View style={{ flex: 1, backgroundColor: "#E6FBFE", padding: 16 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 12 }}>
        <Text style={{ fontSize: 18, fontWeight: "600", color: "#0a2b4a" }}>
          Admin • Review ({onlyLow ? "<0.6 conf" : "All"})
        </Text>
        <Pressable onPress={() => setOnlyLow(v => !v)} style={{ padding: 8, backgroundColor: "white", borderRadius: 8 }}>
          <Text style={{ color: "#0a2b4a" }}>{onlyLow ? "Show All" : "Show <0.6"}</Text>
        </Pressable>
      </View>

      <FlatList
        data={rows}
        keyExtractor={(i) => i.id}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={fetchRows} />}
        renderItem={({ item }) => (
          <View style={{ backgroundColor: "white", padding: 14, marginBottom: 10, borderRadius: 10 }}>
            <Text style={{ fontWeight: "600", color: "#0a2b4a" }}>
              {String(item.category).toUpperCase()} • {item.status}
            </Text>
            <Text>Session: {item.id.slice(0,8)}…</Text>
            <Text>Confidence: {item.confidence ?? 0}</Text>
            <Text>€ {item.price_low_eur ?? "—"} / {item.price_mid_eur ?? "—"} / {item.price_high_eur ?? "—"}</Text>
            <Text style={{ color: "#486" }}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
        )}
      />
    </View>
  );
}
