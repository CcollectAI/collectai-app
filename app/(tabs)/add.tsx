import React, { useState } from "react";
import { View, Text, TextInput, Pressable } from "react-native";
import { theme } from "@/theme";

type Cat = "Pokémon" | "LEGO" | "Funko" | "Cards" | "";

export default function AddScreen() {
  const [category, setCategory] = useState<Cat>("");
  const [title, setTitle] = useState("");
  const [price, setPrice] = useState("");

  // Pokémon
  const [setName, setSetName] = useState("");
  const [cardNo, setCardNo] = useState("");
  const [grade, setGrade] = useState("");
  const [year, setYear] = useState("");

  // LEGO
  const [legoSetNo, setLegoSetNo] = useState("");
  const [condition, setCondition] = useState("");
  const [sealed, setSealed] = useState("");

  // Funko
  const [funkoEdition, setFunkoEdition] = useState("");
  const [funkoNo, setFunkoNo] = useState("");
  const [boxCondition, setBoxCondition] = useState("");

  const scanMock = () => {
    setCategory("Pokémon");
    setTitle("Charizard Holo 1999 (mock)");
    setSetName("Base Set");
    setCardNo("4/102");
    setGrade("PSA 9");
    setYear("1999");
    setPrice("1200.00");
  };

  const Field = ({ label, value, onChangeText, keyboardType="default" as any }) => (
    <View style={{ marginTop: 10 }}>
      <Text style={{ ...theme.font.body, marginBottom: 4 }}>{label}</Text>
      <TextInput value={value} onChangeText={onChangeText} keyboardType={keyboardType}
        style={{ borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, padding: 10 }} />
    </View>
  );

  const CatButton = ({ label }: { label: Exclude<Cat,""> }) => (
    <Pressable
      onPress={() => setCategory(label)}
      style={{
        paddingHorizontal: 12, paddingVertical: 8,
        borderWidth: 1, borderColor: theme.colors.border,
        backgroundColor: category === label ? theme.colors.card : "transparent",
        marginRight: 8,
      }}
    >
      <Text style={{ color: theme.colors.text }}>{label}</Text>
    </Pressable>
  );

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, padding: 16 }}>
      <Text style={{ ...theme.font.title, marginBottom: 12 }}>Add Item</Text>

      <Pressable onPress={scanMock} style={{ padding: 12, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card, marginBottom: 12, alignSelf: "flex-start" }}>
        <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Scan item (mock)</Text>
      </Pressable>

      {/* Category first */}
      <Text style={{ ...theme.font.h1, marginBottom: 6, color: theme.colors.brand.base }}>Category</Text>
      <View style={{ flexDirection: "row", marginBottom: 8 }}>
        <CatButton label="Pokémon" />
        <CatButton label="LEGO" />
        <CatButton label="Funko" />
        <CatButton label="Cards" />
      </View>

      {/* Title next */}
      <Field label="Title" value={title} onChangeText={setTitle} />

      {/* Dynamic detail fields */}
      {category === "Pokémon" && (
        <View style={{ marginTop: 10 }}>
          <Field label="Set" value={setName} onChangeText={setSetName} />
          <Field label="Card number" value={cardNo} onChangeText={setCardNo} />
          <Field label="Grading" value={grade} onChangeText={setGrade} />
          <Field label="Year" value={year} onChangeText={setYear} keyboardType="numeric" />
        </View>
      )}
      {category === "LEGO" && (
        <View style={{ marginTop: 10 }}>
          <Field label="Set number" value={legoSetNo} onChangeText={setLegoSetNo} />
          <Field label="Condition" value={condition} onChangeText={setCondition} />
          <Field label="Box sealed (yes/no)" value={sealed} onChangeText={setSealed} />
        </View>
      )}
      {category === "Funko" && (
        <View style={{ marginTop: 10 }}>
          <Field label="Edition" value={funkoEdition} onChangeText={setFunkoEdition} />
          <Field label="Number" value={funkoNo} onChangeText={setFunkoNo} />
          <Field label="Box condition" value={boxCondition} onChangeText={setBoxCondition} />
        </View>
      )}

      {/* Price */}
      <Field label="Estimated price (€)" value={price} onChangeText={setPrice} keyboardType="decimal-pad" />

      {/* Save */}
      <View style={{ marginTop: 16, alignItems: "flex-start" }}>
        <Pressable style={{ paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: theme.colors.card }}>
          <Text style={{ fontWeight: "700", color: theme.colors.brand.base }}>Save</Text>
        </Pressable>
      </View>
    </View>
  );
}
