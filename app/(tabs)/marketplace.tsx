import React, { useState } from "react";
import { View, Text, ScrollView, Pressable, TextInput } from "react-native";
import { theme } from "@/theme";

type Tab = "Chat" | "Search" | "Sell";

export default function Marketplace() {
  const [tab, setTab] = useState<Tab>("Chat");
  return (
    <ScrollView style={{ flex:1, backgroundColor: theme.colors.background }} contentContainerStyle={{ padding: 16 }}>
      <Text style={{ fontSize: 22, fontWeight: "800", color: theme.colors.text, marginBottom: 12 }}>Marketplace</Text>

      <View style={{ flexDirection:"row", backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border }}>
        {(["Chat","Search","Sell"] as Tab[]).map(t => (
          <Pressable key={t} onPress={()=>setTab(t)} style={{ flex:1, paddingVertical:10, alignItems:"center", borderRightWidth: t==="Sell"?0:1, borderRightColor: theme.colors.border }}>
            <Text style={{ fontWeight: t===tab ? "800":"600", color: theme.colors.text }}>{t}</Text>
          </Pressable>
        ))}
      </View>

      <View style={{ height: 16 }} />

      {tab === "Chat" && (
        <View style={{ backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border, padding: 12 }}>
          <Text style={{ color: theme.colors.subtext }}>Community chat (mock)</Text>
          <View style={{ height: 8 }} />
          <TextInput placeholder="Type a message…" placeholderTextColor="#94A3B8"
            style={{ borderWidth:1, borderColor: theme.colors.border, padding: 10 }} />
        </View>
      )}

      {tab === "Search" && (
        <View style={{ backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border, padding: 12 }}>
          <TextInput placeholder="Search marketplaces…" placeholderTextColor="#94A3B8"
            style={{ borderWidth:1, borderColor: theme.colors.border, padding: 10, marginBottom: 12 }} />
          <Text style={{ color: theme.colors.subtext }}>Results appear here (mock).</Text>
        </View>
      )}

      {tab === "Sell" && (
        <View style={{ backgroundColor: theme.colors.card, borderWidth:1, borderColor: theme.colors.border, padding: 12 }}>
          <Text style={{ color: theme.colors.subtext }}>Listing form (mock).</Text>
        </View>
      )}
    </ScrollView>
  );
}
