import React, { useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  TextInput,
  Pressable,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { formatPrice } from "@/lib/format";

type ItemDetailParams = {
  id?: string;
  name?: string;
  category?: string;
  collectionName?: string;
  value?: string;
  condition?: string;
  notes?: string;
};

const LIGHT_COLORS = {
  background: "#FFFFFF",
  text: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",
  card: "#F8FAFC",
  accent: "#40C9C6",
};

const ItemDetailScreen: React.FC = () => {
  const params = useLocalSearchParams<ItemDetailParams>();
  const colors = LIGHT_COLORS; // later we can hook this into global theme

  const name = params.name ?? "Unnamed item";
  const category = params.category ?? "Unknown category";
  const collectionName = params.collectionName ?? "Unknown collection";
  const condition = params.condition || "";
  const value = params.value;

  // Notes local state
  const [notes, setNotes] = useState(params.notes ?? "");
  const [draft, setDraft] = useState("");

  const handleAddNote = () => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    // Demo behaviour: append draft to the main notes block.
    const newNotes = notes ? `${notes}\n\n${trimmed}` : trimmed;
    setNotes(newNotes);
    setDraft("");
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.select({ ios: "padding", android: undefined })}
        keyboardVerticalOffset={Platform.OS === "ios" ? 80 : 0}
      >
        <View style={[styles.container, { backgroundColor: colors.background }]}>
          {/* Scrollable content */}
          <ScrollView
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
          >
            {/* Top card with image placeholder */}
            <View
              style={[
                styles.card,
                { backgroundColor: colors.card, borderColor: colors.border },
              ]}
            >
              <View style={styles.imagePlaceholder}>
                <Ionicons name="image-outline" size={40} color={colors.muted} />
                <Text style={[styles.imageText, { color: colors.muted }]}>
                  Item image (future)
                </Text>
              </View>

              <View style={styles.textBlock}>
                <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>
                  {name}
                </Text>
                <Text style={[styles.meta, { color: colors.muted }]} numberOfLines={2}>
                  {category} • {collectionName}
                </Text>

                <View style={styles.infoRow}>
                  {condition ? (
                    <View style={styles.infoPill}>
                      <Text style={[styles.infoPillText, { color: colors.muted }]}>
                        {condition}
                      </Text>
                    </View>
                  ) : null}
                  <View style={styles.infoPill}>
                    <Text style={[styles.infoPillText, { color: colors.muted }]}>
                      ID: {params.id ?? "n/a"}
                    </Text>
                  </View>
                </View>

                <View style={styles.valueRow}>
                  <Text
                    style={[styles.valueLabel, { color: colors.muted }]}
                  >
                    Estimated value
                  </Text>
                  <Text
                    style={[styles.valueText, { color: colors.text }]}
                  >
                    {formatPrice(typeof value === 'string' ? Number(value) : value)}
                  </Text>
                </View>
              </View>
            </View>

            {/* Notes section */}
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Notes
              </Text>
              {notes ? (
                <View
                  style={[
                    styles.notesBox,
                    { borderColor: colors.border, backgroundColor: colors.card },
                  ]}
                >
                  <Text style={[styles.notesText, { color: colors.text }]}>
                    {notes}
                  </Text>
                </View>
              ) : (
                <Text style={[styles.emptyNotesText, { color: colors.muted }]}>
                  No notes yet. Add context, purchase details, grading info, or anything
                  else you want to remember.
                </Text>
              )}
            </View>

            {/* Spacer so last content is visible above input bar */}
            <View style={{ height: 72 }} />
          </ScrollView>

          {/* Sticky bottom notes input bar (WhatsApp-style) */}
          <View
            style={[
              styles.bottomBar,
              {
                borderTopColor: colors.border,
                backgroundColor: colors.background,
              },
            ]}
          >
            <View
              style={[
                styles.inputContainer,
                { borderColor: colors.border, backgroundColor: colors.card },
              ]}
            >
              <TextInput
                value={draft}
                onChangeText={setDraft}
                placeholder="Add a note"
                placeholderTextColor={colors.muted}
                multiline
                style={[styles.input, { color: colors.text }]}
              />
              <Pressable
                style={[
                  styles.sendButton,
                  {
                    backgroundColor: draft.trim()
                      ? colors.accent
                      : "rgba(148, 163, 184, 0.25)",
                  },
                ]}
                onPress={handleAddNote}
                disabled={!draft.trim()}
              >
                <Ionicons
                  name="arrow-up-outline"
                  size={16}
                  color={draft.trim() ? "#0F172A" : "#94A3B8"}
                />
              </Pressable>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  container: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 0,
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 12,
    marginBottom: 16,
  },
  imagePlaceholder: {
    height: 180,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 12,
  },
  imageText: {
    marginTop: 6,
    fontSize: 11,
  },
  textBlock: {},
  title: {
    fontSize: 18,
    fontWeight: "700",
  },
  meta: {
    fontSize: 13,
    marginTop: 4,
  },
  infoRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 8,
  },
  infoPill: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  infoPillText: {
    fontSize: 11,
  },
  valueRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    marginTop: 12,
  },
  valueLabel: {
    fontSize: 12,
    fontWeight: "500",
  },
  valueText: {
    fontSize: 18,
    fontWeight: "700",
  },
  section: {
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 4,
  },
  notesBox: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 10,
    minHeight: 60,
  },
  notesText: {
    fontSize: 13,
    lineHeight: 18,
  },
  emptyNotesText: {
    fontSize: 12,
    marginTop: 4,
  },
  bottomBar: {
    paddingHorizontal: 16,
    paddingBottom: Platform.OS === "ios" ? 16 : 10,
    paddingTop: 6,
    borderTopWidth: 1,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "flex-end",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  input: {
    flex: 1,
    fontSize: 13,
    paddingVertical: 4,
    maxHeight: 80,
  },
  sendButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: "center",
    alignItems: "center",
    marginLeft: 8,
  },
});

export default ItemDetailScreen;
