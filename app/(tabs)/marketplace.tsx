import React, { useMemo, useRef, useState } from "react";
import { View, Text, ScrollView, Pressable, TextInput, KeyboardAvoidingView, Platform } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { theme } from "@/theme";
import { mockSearch, MarketHit } from "@/lib/market";

type Tab = "Chat" | "Search" | "Sell";
type Msg = { id: string; who: "me" | "them"; text: string; ts: number };

const CARD = theme.colors.card;           // white squares
const BG = theme.colors.bg;               // Tiffany blue page bg
const BORDER = theme.colors.border;

function Segmented({ value, onChange }: { value: Tab; onChange: (t: Tab) => void }) {
  const tabs: Tab[] = ["Chat", "Search", "Sell"];
  return (
    <View style={{ flexDirection: "row", borderWidth: 1, borderColor: BORDER }}>
      {tabs.map((t, i) => {
        const active = value === t;
        return (
          <Pressable
            key={t}
            onPress={() => onChange(t)}
            style={{
              flex: 1,
              paddingVertical: 10,
              backgroundColor: active ? CARD : "transparent",
              alignItems: "center",
              borderRightWidth: i < tabs.length - 1 ? 1 : 0,
              borderRightColor: BORDER,
            }}
          >
            <Text style={{ ...theme.font.body, fontWeight: active ? "700" : "600", color: theme.colors.text }}>{t}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function Bubble({ m }: { m: Msg }) {
  const self = m.who === "me";
  return (
    <View style={{ alignItems: self ? "flex-end" : "flex-start", marginBottom: 8 }}>
      <View
        style={{
          maxWidth: "82%",
          backgroundColor: CARD,
          borderWidth: 1,
          borderColor: BORDER,
          padding: 10,
        }}
      >
        <Text style={{ color: theme.colors.text }}>{m.text}</Text>
      </View>
    </View>
  );
}

function SearchRow({ hit }: { hit: MarketHit }) {
  return (
    <View style={{ paddingVertical: 14, paddingHorizontal: 10, backgroundColor: CARD, borderBottomWidth: 1, borderBottomColor: BORDER }}>
      <Text style={{ ...theme.font.body, fontWeight: "600", marginBottom: 6 }}>{hit.title}</Text>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={{ fontSize: 12, color: theme.colors.subtext }}>{hit.marketplace}</Text>
        <Text style={{ fontWeight: "800", color: theme.colors.text }}>€{new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(hit.price)}</Text>
      </View>
    </View>
  );
}

export default function MarketplaceScreen() {
  const [tab, setTab] = useState<Tab>("Chat");

  // --- Chat state (mock, realtime-ready structure) ---
  const [msgs, setMsgs] = useState<Msg[]>([
    { id: "m1", who: "them", text: "Hey! Is your Charizard still available?", ts: Date.now() - 120000 },
    { id: "m2", who: "me", text: "Yes, still available. PSA 9.", ts: Date.now() - 60000 },
  ]);
  const [input, setInput] = useState("");
  const send = () => {
    const t = input.trim();
    if (!t) return;
    setMsgs(prev => [...prev, { id: String(Date.now()), who: "me", text: t, ts: Date.now() }]);
    setInput("");
  };

  // --- Search state ---
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<MarketHit[]>([]);
  const [searching, setSearching] = useState(false);
  const doSearch = async () => {
    setSearching(true);
    try { setHits(await mockSearch(q)); } finally { setSearching(false); }
  };

  // --- Sell form ---
  const [title, setTitle] = useState("");
  const [cat, setCat] = useState("");
  const [price, setPrice] = useState("");
  const [desc, setDesc] = useState("");
  const publish = () => {
    // mock publish
    setTitle(""); setCat(""); setPrice(""); setDesc("");
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: BG }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 24 }}>
          {/* Top title */}
          <Text style={{ ...theme.font.title, marginBottom: 12 }}>Marketplace</Text>

          {/* Segmented control */}
          <Segmented value={tab} onChange={setTab} />

          {/* Panels */}
          {tab === "Chat" && (
            <View style={{ marginTop: 12 }}>
              <View style={{ backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 10 }}>
                {msgs.map(m => <Bubble key={m.id} m={m} />)}
              </View>

              {/* Composer */}
              <View style={{ flexDirection: "row", marginTop: 12, gap: 8 }}>
                <TextInput
                  value={input}
                  onChangeText={setInput}
                  placeholder="Message…"
                  placeholderTextColor={theme.colors.subtext}
                  style={{ flex: 1, backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 10 }}
                />
                <Pressable onPress={send} style={{ paddingHorizontal: 14, justifyContent: "center", borderWidth: 1, borderColor: BORDER, backgroundColor: CARD }}>
                  <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Send</Text>
                </Pressable>
              </View>
            </View>
          )}

          {tab === "Search" && (
            <View style={{ marginTop: 12 }}>
              <View style={{ flexDirection: "row", gap: 8, marginBottom: 10 }}>
                <TextInput
                  value={q}
                  onChangeText={setQ}
                  placeholder="Search all marketplaces"
                  placeholderTextColor={theme.colors.subtext}
                  style={{ flex: 1, backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 10 }}
                />
                <Pressable onPress={doSearch} style={{ paddingHorizontal: 14, justifyContent: "center", borderWidth: 1, borderColor: BORDER, backgroundColor: CARD }}>
                  <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>{searching ? "…" : "Search"}</Text>
                </Pressable>
              </View>

              <View style={{ borderWidth: 1, borderColor: BORDER }}>
                {hits.length === 0 && !searching ? (
                  <View style={{ padding: 12, backgroundColor: CARD }}>
                    <Text style={{ color: theme.colors.subtext }}>Try searching for “Charizard”, “LEGO 75192”, “Pikachu”…</Text>
                  </View>
                ) : hits.map(h => <SearchRow key={h.id} hit={h} />)}
              </View>
            </View>
          )}

          {tab === "Sell" && (
            <View style={{ marginTop: 12, gap: 10 }}>
              <View style={{ backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 12 }}>
                <Text style={{ ...theme.font.h1, marginBottom: 8 }}>Create a listing</Text>

                <Text style={{ ...theme.font.body, marginBottom: 4 }}>Title</Text>
                <TextInput value={title} onChangeText={setTitle} placeholder="e.g., Charizard Holo 1999 PSA 9"
                  placeholderTextColor={theme.colors.subtext}
                  style={{ backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 10, marginBottom: 8 }} />

                <Text style={{ ...theme.font.body, marginBottom: 4 }}>Category</Text>
                <TextInput value={cat} onChangeText={setCat} placeholder="Pokémon / LEGO / Funko / …"
                  placeholderTextColor={theme.colors.subtext}
                  style={{ backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 10, marginBottom: 8 }} />

                <Text style={{ ...theme.font.body, marginBottom: 4 }}>Price (€)</Text>
                <TextInput value={price} onChangeText={setPrice} keyboardType="decimal-pad" placeholder="0.00"
                  placeholderTextColor={theme.colors.subtext}
                  style={{ backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 10, marginBottom: 8 }} />

                <Text style={{ ...theme.font.body, marginBottom: 4 }}>Description</Text>
                <TextInput value={desc} onChangeText={setDesc} placeholder="Condition, grading, accessories, etc."
                  placeholderTextColor={theme.colors.subtext} multiline
                  style={{ backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 10, minHeight: 80, textAlignVertical: "top" }} />

                <Pressable onPress={publish} style={{ marginTop: 12, alignSelf: "flex-start", paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: BORDER, backgroundColor: CARD }}>
                  <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Publish (mock)</Text>
                </Pressable>
              </View>

              <View style={{ backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, padding: 12 }}>
                <Text style={{ ...theme.font.h1, marginBottom: 6 }}>Tips</Text>
                <Text style={{ color: theme.colors.subtext, marginBottom: 4 }}>• Clear photos, front/back, close-ups of defects.</Text>
                <Text style={{ color: theme.colors.subtext, marginBottom: 4 }}>• Add grading or set/edition numbers where applicable.</Text>
                <Text style={{ color: theme.colors.subtext }}>• Use realistic pricing; include shipping or pickup details.</Text>
              </View>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
