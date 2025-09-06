import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, Alert, ScrollView } from "react-native";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { theme } from "../../../src/theme";
import supabase from "../../../lib/supabaseClient";
import { pickImage, uploadToSupabase } from "../../../lib/upload";

export default function NewListing() {
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("");
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const router = useRouter();

  async function onPick() {
    try {
      const uri = await pickImage({ aspect: [1, 1] });
      if (uri) setImageUri(uri);
    } catch (e: any) {
      Alert.alert("Image", e.message ?? "Could not pick image");
    }
  }

  async function onCreate() {
    try {
      if (!supabase) throw new Error("Supabase not configured");
      if (!title.trim()) return Alert.alert("Title required", "Please provide a title.");
      setSaving(true);

      let image_url: string | undefined = undefined;
      if (imageUri) image_url = await uploadToSupabase(imageUri, "listing");

      const { error } = await supabase.from("listings").insert({
        title: title.trim(),
        price: price ? Number(price.replace(/,/g, "")) : 0,
        category: category.trim() || null,
        image_url,
        status: "active",
      });
      if (error) throw error;

      Alert.alert("Created", "Listing posted.");
      router.replace("/listings");
    } catch (e: any) {
      Alert.alert("Error", e.message ?? "Could not create listing");
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: 16 }}>
      <Text style={{ fontSize: 22, fontWeight: "800", marginBottom: 10 }}>New Listing</Text>

      <TouchableOpacity onPress={onPick} style={{ backgroundColor: "#fff", borderRadius: 14, overflow: "hidden", borderWidth: 1, borderColor: theme.colors.border }}>
        <Image
          source={imageUri ? { uri: imageUri } : require("../../../assets/images/placeholder.png")}
          style={{ width: "100%", height: 220 }}
          contentFit="cover"
        />
      </TouchableOpacity>

      <Text style={{ color: theme.colors.muted, marginTop: 12 }}>Title</Text>
      <TextInput value={title} onChangeText={setTitle} placeholder="e.g. Charizard Holo" style={{ backgroundColor: "#fff", borderRadius: 14, paddingHorizontal: 14, height: 46, borderWidth: 1, borderColor: theme.colors.border, marginTop: 6 }} />

      <Text style={{ color: theme.colors.muted, marginTop: 12 }}>Price</Text>
      <TextInput value={price} onChangeText={setPrice} placeholder="e.g. 199" keyboardType="decimal-pad" style={{ backgroundColor: "#fff", borderRadius: 14, paddingHorizontal: 14, height: 46, borderWidth: 1, borderColor: theme.colors.border, marginTop: 6 }} />

      <Text style={{ color: theme.colors.muted, marginTop: 12 }}>Category</Text>
      <TextInput value={category} onChangeText={setCategory} placeholder="e.g. pokemon" autoCapitalize="none" style={{ backgroundColor: "#fff", borderRadius: 14, paddingHorizontal: 14, height: 46, borderWidth: 1, borderColor: theme.colors.border, marginTop: 6 }} />

      <TouchableOpacity disabled={saving} onPress={onCreate} style={{ marginTop: 16, backgroundColor: theme.colors.brand.base, height: 48, borderRadius: 14, alignItems: "center", justifyContent: "center" }}>
        <Text style={{ color: "#0F172A", fontWeight: "800" }}>{saving ? "Saving…" : "Create"}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
