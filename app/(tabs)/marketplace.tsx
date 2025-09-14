import React, { useState } from "react";
import { View, Text, ScrollView, Pressable, TextInput } from "react-native";
import { theme } from "@/theme";

type Msg = { id: string; who: "me" | "peer"; text: string };
const START: Msg[] = [
  { id: "m1", who: "peer", text: "Welcome to Marketplace! 👋 Looking for anything?" },
];

const MOCK_HITS = [
  { id: "h1", title: "Charizard Holo 1999", marketplace: "eBay", price: 1210 },
  { id: "h2", title: "LEGO Falcon 75192", marketplace: "BrickLink", price: 675 },
];

export default function Marketplace() {
  const [tab, setTab] = useState<"Chat"|"Search"|"Sell">("Chat");
  const [msgs, setMsgs] = useState<Msg[]>(START);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [sellTitle, setSellTitle] = useState("");
  const [sellPrice, setSellPrice] = useState("");

  const send = () => {
    const t = draft.trim(); if (!t) return;
    setMsgs(m => [...m, { id: String(Date.now()), who: "me", text: t }]);
    setDraft("");
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <View style={{ padding: 16 }}>
        <Text style={{ ...theme.font.title, marginBottom: 10 }}>Marketplace</Text>

        <View style={{ flexDirection: "row", gap: 8, marginBottom: 12 }}>
          {(["Chat","Search","Sell"] as const).map(k => (
            <Pressable key={k} onPress={() => setTab(k)}
              style={{ paddingHorizontal: 10, paddingVertical: 6, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: tab===k ? theme.colors.card : "transparent" }}>
              <Text style={{ color: theme.colors.text, fontWeight: "600" }}>{k}</Text>
            </Pressable>
          ))}
        </View>

        {tab === "Chat" && (
          <View>
            <View style={{ gap: 8, marginBottom: 12 }}>
              {msgs.map(m => (
                <View key={m.id} style={{
                  alignSelf: m.who === "me" ? "flex-end" : "flex-start",
                  backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border,
                  paddingHorizontal: 10, paddingVertical: 8, maxWidth: "80%"
                }}>
                  <Text style={{ color: theme.colors.text }}>{m.text}</Text>
                </View>
              ))}
            </View>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <TextInput value={draft} onChangeText={setDraft} placeholder="Type a message"
                style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10 }} />
              <Pressable onPress={send} style={{ paddingHorizontal: 12, justifyContent: "center", borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
                <Text style={{ color: theme.colors.brand.base, fontWeight: "700" }}>Send</Text>
              </Pressable>
            </View>
          </View>
        )}

        {tab === "Search" && (
          <View>
            <TextInput value={query} onChangeText={setQuery} placeholder="Search all marketplaces"
              style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10, marginBottom: 12 }} />
            <View style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
              {MOCK_HITS
                .filter(h => !query || h.title.toLowerCase().includes(query.toLowerCase()))
                .map(h => (
                  <View key={h.id} style={{ paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: theme.colors.border }}>
                    <Text style={{ fontWeight: "700", color: theme.colors.text }}>{h.title}</Text>
                    <Text style={{ color: theme.colors.subtext, marginTop: 2 }}>{h.marketplace} • €{h.price.toFixed(2)}</Text>
                  </View>
                ))}
            </View>
          </View>
        )}

        {tab === "Sell" && (
          <View>
            <TextInput value={sellTitle} onChangeText={setSellTitle} placeholder="Item title"
              style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10, marginBottom: 8 }} />
            <TextInput value={sellPrice} onChangeText={setSellPrice} placeholder="Price (€)" keyboardType="decimal-pad"
              style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10, marginBottom: 12 }} />
            <Pressable style={{ paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, alignSelf: "flex-start" }}>
              <Text style={{ color: theme.colors.brand.base, fontWeight: "700" }}>Publish (mock)</Text>
            </Pressable>
            <Text style={{ color: theme.colors.subtext, marginTop: 12 }}>
              Listings post to your CollectAI profile; cross-post integrations will come next.
            </Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
}
