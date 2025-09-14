import React, { useState } from "react";
import { View, Text, TextInput, Pressable } from "react-native";
import { theme } from "@/theme";

export default function AddScreen() {
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [price, setPrice] = useState("");

  const scanMock = () => {
    // pretend vision + knowledge fill
    setTitle("Charizard Holo 1999 (mock)");
    setCategory("Pokémon");
    setPrice("1200.00");
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, padding: 16 }}>
      <Text style={{ ...theme.font.title, marginBottom: 12 }}>Add Item</Text>

      <Pressable onPress={scanMock} style={{ padding: 12, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
        <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Scan item (mock)</Text>
      </Pressable>

      <View style={{ marginTop: 16, gap: 10 }}>
        <View>
          <Text style={{ ...theme.font.body, marginBottom: 4 }}>Title</Text>
          <TextInput value={title} onChangeText={setTitle} placeholder="Item title"
            style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10 }} />
        </View>
        <View>
          <Text style={{ ...theme.font.body, marginBottom: 4 }}>Category</Text>
          <TextInput value={category} onChangeText={setCategory} placeholder="e.g., Pokémon"
            style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10 }} />
        </View>
        <View>
          <Text style={{ ...theme.font.body, marginBottom: 4 }}>Estimated price (€)</Text>
          <TextInput value={price} onChangeText={setPrice} placeholder="0.00" keyboardType="decimal-pad"
            style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10 }} />
        </View>
      </View>

      <View style={{ marginTop: 16, alignItems: "flex-start" }}>
        <Pressable style={{ paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
          <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Save</Text>
        </Pressable>
      </View>
    </View>
  );
}
