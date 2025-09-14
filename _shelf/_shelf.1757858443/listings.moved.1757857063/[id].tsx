async function onAddToCollection() {
  try {
    if (!supabase) throw new Error("Supabase not configured");
    const priceNum = price ? Number(price.replace(/,/g, "")) : row.price ?? 0;
    const { error } = await supabase.from("items").insert({
      title: title.trim() || row.title,
      image_url: imageUri ? await uploadToSupabase(imageUri, "item") : row.image_url,
      category: row.category,
      value: priceNum,
    });
    if (error) throw error;
    Alert.alert("Added", "This listing was copied into your collection.");
  } catch (e: any) {
    Alert.alert("Error", e.message ?? "Could not add to collection");
  }
<TouchableOpacity onPress={onAddToCollection} style={{ marginTop: 10, backgroundColor: "#fff", borderWidth: 1, borderColor: theme.colors.border, height: 48, borderRadius:14, alignItems:"center", justifyContent:"center" }}>
  <Text style={{ color: theme.colors.text, fontWeight:"800" }}>Add to Collection</Text>
</TouchableOpacity>




}
