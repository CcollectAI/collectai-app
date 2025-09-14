import React, { useState } from "react";
import { View, TextInput, Text, TouchableOpacity, ScrollView, RefreshControl } from "react-native";
import { Image } from "expo-image";
import { theme } from "../../../src/theme";
import { useRouter } from "expo-router";
import useListings from "../../../src/hooks/useListings";

export default function Listings() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string | undefined>(undefined);
  const { rows, loading, refresh } = useListings({ q: query, status });
  const router = useRouter();

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: 80 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={refresh} />}
      >
        <View style={{ padding: 16 }}>
          <TextInput
            placeholder="Search listings…"
            value={query}
            onChangeText={setQuery}
            style={{
              backgroundColor: "#fff",
              borderRadius: 14,
              paddingHorizontal: 14,
              height: 44,
              borderWidth: 1,
              borderColor: theme.colors.border,
            }}
          />
          <View style={{ flexDirection: "row", gap: 8, marginTop: 12 }}>
            {["all", "active", "sold"].map((tag) => {
              const active = (status ?? "all") === tag;
              return (
                <TouchableOpacity
                  key={tag}
                  onPress={() => setStatus(tag === "all" ? undefined : tag)}
                  style={{
                    backgroundColor: active ? theme.colors.brand.light : "#fff",
                    borderRadius: 999,
                    paddingHorizontal: 12,
                    paddingVertical: 6,
                    borderWidth: 1,
                    borderColor: theme.colors.border,
                  }}
                >
                <Text style={{ color: active ? "#0F172A" : theme.colors.muted, fontWeight: "700" }}>
                    {tag.toUpperCase()}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        <View style={{ paddingHorizontal: 12, gap: 12 }}>
          {rows.map((l) => (
            <TouchableOpacity
              key={l.id}
              onPress={() => router.push(`/listings/${l.id}`)}
              style={{ backgroundColor: "#fff", borderRadius: 18, padding: 12, flexDirection: "row", alignItems: "center", gap: 12, ...theme.shadow.card }}
            >
              <Image
                source={ l.image_url ? { uri: l.image_url } : require("../../../assets/images/placeholder.png") }
                style={{ width: 64, height: 64, borderRadius: 12 }}
                contentFit="cover"
              />
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: "800", color: theme.colors.text }}>{l.title}</Text>
                <Text style={{ color: theme.colors.muted }}>{l.category ?? "—"}</Text>
              </View>
              <Text style={{ fontWeight: "800", color: theme.colors.text }}>${(l.price ?? 0).toFixed(0)}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* FAB */}
      <TouchableOpacity
        onPress={() => router.push("/listings/new")}
        style={{
          position: "absolute",
          right: 18,
          bottom: 18,
          backgroundColor: theme.colors.brand.base,
          width: 56,
          height: 56,
          borderRadius: 28,
          alignItems: "center",
          justifyContent: "center",
          ...theme.shadow.card,
        }}
      >
        <Text style={{ color: "#0F172A", fontWeight: "900", fontSize: 22 }}>＋</Text>
      </TouchableOpacity>
    </View>
  );
}
