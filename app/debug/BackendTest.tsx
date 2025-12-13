import { useEffect, useState } from "react";
import { View, Text, ScrollView, ActivityIndicator } from "react-native";
import { collectorsApi } from "@/api/collectorsApi";

export default function BackendTest() {
  const [data, setData] = useState<any>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const results = {
          watchlist: await collectorsApi.fetchWatchlist().catch(e => ({ error: e.message })),
          widget: await collectorsApi.fetchHomeWidget().catch(e => ({ error: e.message })),
          insights: await collectorsApi.fetchInsights().catch(e => ({ error: e.message })),
          quickscan: await collectorsApi.quickscanSingle().catch(e => ({ error: e.message })),
          screenshot: await collectorsApi.analyzeScreenshot({ screenshot_id: "demo-123", source_hint: "ebay" }).catch(e => ({ error: e.message })),
        };
        setData(results);
      } catch (err: any) {
        setError(err.message ?? String(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
        <Text style={{ marginTop: 8 }}>Loading backend data…</Text>
      </View>
    );
  }

  return (
    <ScrollView style={{ padding: 20 }}>
      <Text style={{ fontSize: 22, fontWeight: "bold", marginBottom: 12 }}>
        Backend Test
      </Text>
      {error && (
        <Text style={{ color: "red", marginBottom: 12 }}>
          Error: {error}
        </Text>
      )}
      <Text selectable style={{ fontFamily: "monospace" }}>
        {JSON.stringify(data, null, 2)}
      </Text>
    </ScrollView>
  );
}
