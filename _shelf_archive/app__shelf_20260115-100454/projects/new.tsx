import React, { useMemo, useState } from "react";
import { View, Text, TextInput, Pressable, ScrollView, StyleSheet, Alert } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { CATEGORIES } from "@/data/categories"; // if this import fails, tell me the error; we’ll swap to getCategoryById list

const BG = "#F2F4F7";
const CARD = "#FFFFFF";
const BORDER = "#D6E4EC";
const TEXT = "#0C2233";
const MUTED = "#647589";
const TIFFANY = "#38D6C7";

type Step = { id: string; label: string; done: boolean };

export default function NewProjectScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const categoryOptions = useMemo(() => {
    // expects CATEGORIES to be an array; if your data file differs we’ll adjust fast
    return (Array.isArray((CATEGORIES as any)) ? (CATEGORIES as any) : []).map((c: any) => ({
      id: String(c.id ?? c.slug ?? c.key ?? ""),
      name: String(c.name ?? c.title ?? c.id ?? "Category"),
    })).filter((c: any) => c.id);
  }, []);

  const [title, setTitle] = useState("");
  const [categoryId, setCategoryId] = useState(categoryOptions[0]?.id ?? "pokemon");
  const [status, setStatus] = useState<"ongoing" | "closed">("ongoing");
  const [notes, setNotes] = useState("");

  const [steps, setSteps] = useState<Step[]>([
    { id: "acquire", label: "Acquire item(s)", done: false },
    { id: "prep", label: "Prep / clean", done: false },
    { id: "prime", label: "Prime / base", done: false },
    { id: "paint", label: "Paint", done: false },
    { id: "seal", label: "Seal / protect", done: false },
    { id: "photo", label: "Photograph & log", done: false },
  ]);

  const pct = useMemo(() => {
    const total = steps.length || 1;
    const done = steps.filter(s => s.done).length;
    return Math.round((done / total) * 100);
  }, [steps]);

  const toggleStep = (id: string) => {
    setSteps(prev => prev.map(s => (s.id === id ? { ...s, done: !s.done } : s)));
  };

  const save = () => {
    if (!title.trim()) {
      Alert.alert("Add a title", "Name your project (e.g., “Gunpla: RX-78 build”).");
      return;
    }

    // Mock save (no DB yet). We’ll wire persistence later.
    Alert.alert("Project created", "Saved locally (mock). Next: wire to storage/DB.", [
      { text: "Back", onPress: () => router.back() },
    ]);
  };

  return (
    <SafeAreaView style={[styles.safe, { paddingTop: Math.max(8, insets.top) }]} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.headerRow}>
          <Pressable onPress={() => router.back()} style={styles.iconBtn} accessibilityRole="button">
            <Ionicons name="chevron-back" size={18} color={MUTED} />
          </Pressable>
          <Text style={styles.headerTitle}>New project</Text>
          <Pressable onPress={save} style={styles.saveBtn} accessibilityRole="button">
            <Ionicons name="checkmark" size={18} color="#FFFFFF" />
            <Text style={styles.saveText}>Save</Text>
          </Pressable>
        </View>

        <View style={styles.card}>
          <Text style={styles.label}>Project title</Text>
          <TextInput
            value={title}
            onChangeText={setTitle}
            placeholder="e.g., Pokémon: PSA submission batch"
            placeholderTextColor={MUTED}
            style={styles.input}
          />

          <View style={{ height: 12 }} />

          <Text style={styles.label}>Category</Text>
          <View style={styles.pillsRow}>
            {categoryOptions.slice(0, 6).map((c: any) => {
              const active = c.id === categoryId;
              return (
                <Pressable
                  key={c.id}
                  onPress={() => setCategoryId(c.id)}
                  style={[styles.pill, active && styles.pillActive]}
                  accessibilityRole="button"
                >
                  <Text style={[styles.pillText, active && styles.pillTextActive]}>{c.name}</Text>
                </Pressable>
              );
            })}
          </View>

          <View style={{ height: 12 }} />

          <Text style={styles.label}>Status</Text>
          <View style={styles.pillsRow}>
            {(["ongoing", "closed"] as const).map((k) => {
              const active = k === status;
              return (
                <Pressable
                  key={k}
                  onPress={() => setStatus(k)}
                  style={[styles.pill, active && styles.pillActive]}
                  accessibilityRole="button"
                >
                  <Text style={[styles.pillText, active && styles.pillTextActive]}>
                    {k === "ongoing" ? "Ongoing" : "Closed"}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={styles.card}>
          <View style={styles.sectionTopRow}>
            <Text style={styles.sectionTitle}>Progress</Text>
            <Text style={styles.pct}>{pct}%</Text>
          </View>

          <View style={styles.barOuter}>
            <View style={[styles.barInner, { width: `${pct}%` }]} />
          </View>

          <View style={{ height: 10 }} />

          {steps.map((s) => (
            <Pressable
              key={s.id}
              onPress={() => toggleStep(s.id)}
              style={styles.stepRow}
              accessibilityRole="button"
            >
              <Ionicons
                name={s.done ? "checkmark-circle" : "ellipse-outline"}
                size={18}
                color={s.done ? TIFFANY : MUTED}
                style={{ marginRight: 10 }}
              />
              <Text style={styles.stepText}>{s.label}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Notes</Text>
          <TextInput
            value={notes}
            onChangeText={setNotes}
            placeholder="Add notes, paint mixes, comps, purchase info, deadlines…"
            placeholderTextColor={MUTED}
            style={[styles.input, { height: 120, textAlignVertical: "top" }]}
            multiline
          />
        </View>

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  content: { paddingHorizontal: 16, paddingBottom: 24 },

  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  iconBtn: {
    width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: BORDER,
    alignItems: "center", justifyContent: "center", backgroundColor: CARD,
  },
  headerTitle: { flex: 1, textAlign: "center", fontSize: 16, fontWeight: "900", color: TEXT },
  saveBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12,
    backgroundColor: TEXT,
  },
  saveText: { color: "#fff", fontSize: 12, fontWeight: "900" },

  card: { backgroundColor: CARD, borderColor: BORDER, borderWidth: 1, borderRadius: 14, padding: 14, marginBottom: 10 },

  label: { color: MUTED, fontSize: 11, fontWeight: "800", marginBottom: 6 },
  input: {
    borderWidth: 1, borderColor: BORDER, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10,
    fontSize: 13, fontWeight: "700", color: TEXT, backgroundColor: "#fff",
  },

  pillsRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  pill: {
    borderWidth: 1, borderColor: BORDER, backgroundColor: "#fff",
    paddingHorizontal: 10, paddingVertical: 8, borderRadius: 999,
  },
  pillActive: { borderColor: TIFFANY, backgroundColor: "rgba(56,214,199,0.12)" },
  pillText: { fontSize: 12, fontWeight: "800", color: MUTED },
  pillTextActive: { color: TEXT },

  sectionTopRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  sectionTitle: { fontSize: 13, fontWeight: "900", color: TEXT },
  pct: { fontSize: 12, fontWeight: "900", color: TEXT },

  barOuter: { height: 10, backgroundColor: "#E9EEF3", borderRadius: 999, overflow: "hidden", marginTop: 8 },
  barInner: { height: 10, backgroundColor: TIFFANY, borderRadius: 999 },

  stepRow: { flexDirection: "row", alignItems: "center", paddingVertical: 8 },
  stepText: { fontSize: 13, fontWeight: "800", color: TEXT },
});
