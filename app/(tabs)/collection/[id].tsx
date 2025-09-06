import React, { useMemo, useState } from "react";
import { View, Text, TextInput, TouchableOpacity, Alert, ScrollView } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Image } from "expo-image";
import { theme } from "../../../src/theme";
import useItems from "../../../src/hooks/useItems";
import supabase from "../../../lib/supabaseClient";
import { pickImage, uploadToSupabase } from "../../../lib/upload";

export default function ItemDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { items, refresh } = useItems();
  const router = useRouter();

  const row = useMemo(() => items.find((x) => String(x.id) === String(id)), [items, id]);
  const [title, setTitle] = useState(row?.title ?? "");
  const [value, setValue] = useState(row?.value ? String(row.value) : "");
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  if (!row) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <Text>Item not found.</Text>
      </View>
    );
  }

  async function onPick() {
    try {
      const uri = await pickImage({ aspect: [1, 1] });
      if (uri) setImageUri(uri);
    } catch (e: any) {
      Alert.alert("Image", e.message ?? "Could not pick image");
    }
  }

  async function onSave() {
    try {
      if (!supabase) throw new Error("Supabase not configured");
      setSaving(true);

      let image_url = row.image_url;
      if (imageUri) image_url = await uploadToSupabase(imageUri, "item");

      const { error } = await supabase
        .from("items")
        .update({
          title: title.trim() || row.title,
          value: value ? Number(value.replace(/,/g, "")) : row.value ?? 0,
          image_url,
        })
        .eq("id", row.id);
      if (error) throw error;

      await refresh(); // revalidate cached list
      Alert.alert("Saved", "Item updated.");
      router.back();
    } catch (e: any) {
      Alert.alert("Error", e.message ?? "Update failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: 16 }}>
      <Text style={{ fontSize: 22, fontWeight: "800", marginBottom: 10 }}>Edit Item</Text>

      <TouchableOpacity onPress={onPick} style={{ backgroundColor: "#fff", borderRadius: 14, borderWidth: 1, borderColor: theme.colors.border, overflow: "hidden" }}>
        <Image
          source={imageUri ? { uri: imageUri } : (row.image_url ? { uri: row.image_url } : require("../../../assets/images/placeholder.png"))}
          style={{ width: "100%", height: 220 }}
          contentFit="cover"
        />
      </TouchableOpacity>

      <Text style={{ color: theme.colors.muted, marginTop: 12 }}>Title</Text>
      <TextInput value={title} onChangeText={setTitle} placeholder="Title" style={{ backgroundColor: "#fff", borderRadius: 14, paddingHorizontal: 14, height: 46, borderWidth: 1, borderColor: theme.colors.border, marginTop: 6 }} />

      <Text style={{ color: theme.colors.muted, marginTop: 12 }}>Value</Text>
      <TextInput value={value} onChangeText={setValue} placeholder="e.g. 250" keyboardType="decimal-pad" style={{ backgroundColor: "#fff", borderRadius: 14, paddingHorizontal: 14, height: 46, borderWidth: 1, borderColor: theme.colors.border, marginTop: 6 }} />

      <TouchableOpacity disabled={saving} onPress={onSave} style={{ marginTop: 16, backgroundColor: theme.colors.brand.base, height: 48, borderRadius: 14, alignItems: "center", justifyContent: "center" }}>
        <Text style={{ color: "#0F172A", fontWeight: "800" }}>{saving ? "Saving…" : "Save"}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
