import React, { useState, useRef } from "react";
import { Link } from 'expo-router';
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  Image,
  TextInput,
  Pressable,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { useColorTheme } from "../../src/theme/colors";

export default function ItemDetailScreen() {
  const theme = useColorTheme();
  const params = useLocalSearchParams<{
    id?: string;
    draft?: string;
    name?: string;
    category?: string;
    collection?: string;
    condition?: string;
    value?: string;
    notes?: string;
    imageUri?: string;
    q10?: string;
    q50?: string;
    q90?: string;
    confidence?: string;
  }>();

  const {
    id,
    draft,
    name = "Unknown item",
    category = "Unknown category",
    collection = "Not set",
    condition = "Not set",
    value = "0",
    notes: initialNotes = "",
    imageUri,
    q10,
    q50,
    q90,
    confidence,
  } = params;

  const isDraft = id === 'draft' || draft === '1';

  const [notes, setNotes] = useState(initialNotes || "");
  const [saving, setSaving] = useState(false);
  const notesInputRef = useRef<TextInput | null>(null);

  const onSaveNotes = () => {
    setSaving(true);
    // For now this is local-only; later we hook into Supabase / API.
    setTimeout(() => {
      setSaving(false);
      Alert.alert("Notes saved", "Your notes for this item have been updated.");
    }, 300);
  };

  const focusNotes = () => {
    notesInputRef.current?.focus();
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 80 : 0}
    >
      <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.background }]}>
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={[
            styles.content,
            { backgroundColor: theme.background },
          ]}
          keyboardShouldPersistTaps="handled"
        >
          {/* Image — use captured imageUri in draft mode, placeholder otherwise */}
          <View style={[styles.imageWrapper, { borderColor: theme.border }]}>
            {imageUri ? (
              <Image
                source={{ uri: imageUri }}
                style={styles.image}
                resizeMode="cover"
              />
            ) : (
              <Image
                source={require("../../assets/placeholder.png")}
                style={styles.image}
                resizeMode="cover"
              />
            )}
          </View>

          {/* Draft mode indicator */}
          {isDraft && (
            <View style={[styles.draftBanner, { backgroundColor: theme.accent }]}>
              <Text style={[styles.draftText, { color: theme.accentText }]}>
                Draft — not saved yet
              </Text>
            </View>
          )}

          {/* Details card */}
          <View
            style={[
              styles.card,
              { backgroundColor: theme.card, borderColor: theme.border },
            ]}
          >
            <Text style={[styles.name, { color: theme.text }]}>{name}</Text>
            <Text style={[styles.category, { color: theme.mutedText }]}>
              {category}
            </Text>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.mutedText }]}>
                Collection
              </Text>
              <Text style={[styles.value, { color: theme.text }]}>{collection}</Text>
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.mutedText }]}>
                Condition
              </Text>
              <Text style={[styles.value, { color: theme.text }]}>{condition}</Text>
            </View>

            <View style={styles.row}>
              <Text style={[styles.label, { color: theme.mutedText }]}>
                Estimated value
              </Text>
              <Text style={[styles.valueHighlight, { color: theme.text }]}>
                €{value}
              </Text>
            </View>

            {/* Price bands (q10/q50/q90) — shown in draft mode */}
            {(q10 || q50 || q90) && (
              <View style={styles.priceBandsRow}>
                <Text style={[styles.label, { color: theme.mutedText }]}>
                  Price range
                </Text>
                <Text style={[styles.value, { color: theme.text }]}>
                  €{q10 ?? '?'} – €{q50 ?? '?'} – €{q90 ?? '?'}
                </Text>
              </View>
            )}

            {/* Confidence — shown in draft mode */}
            {confidence && (
              <View style={styles.row}>
                <Text style={[styles.label, { color: theme.mutedText }]}>
                  Confidence
                </Text>
                <Text style={[styles.value, { color: theme.text }]}>
                  {confidence}%
                </Text>
              </View>
            )}

            {/* Notes (editable) */}
            <View style={styles.notesBlock}>
              <View style={styles.notesHeaderRow}>
                <Text style={[styles.label, { color: theme.mutedText }]}>
                  Notes
                </Text>
                <Pressable
                  onPress={focusNotes}
                  style={[
                    styles.notesAddButton,
                    { borderColor: theme.border, backgroundColor: theme.card },
                  ]}
                >
                  <Text
                    style={{
                      fontSize: 16,
                      fontWeight: "700",
                      color: theme.text,
                    }}
                  >
                    +
                  </Text>
                </Pressable>
              </View>

              <TextInput
                ref={notesInputRef}
                style={[
                  styles.notesInput,
                  {
                    color: theme.text,
                    borderColor: theme.border,
                    backgroundColor: theme.background,
                  },
                ]}
                placeholder="Add your notes about condition, provenance, where you bought it, etc."
                placeholderTextColor={theme.mutedText as string}
                multiline
                value={notes}
                onChangeText={setNotes}
                textAlignVertical="top"
                blurOnSubmit={false}
              />
              <View style={styles.notesActions}>
                <Pressable
                  onPress={onSaveNotes}
                  style={[
                    styles.saveButton,
                    { backgroundColor: theme.accent, opacity: saving ? 0.7 : 1 },
                  ]}
                  disabled={saving}
                >
                  <Text
                    style={[
                      styles.saveButtonText,
                      { color: theme.accentText },
                    ]}
                  >
                    {saving ? "Saving…" : "Save notes"}
                  </Text>
                </Pressable>
              </View>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 32,
  },
  imageWrapper: {
    width: "100%",
    height: 260,
    borderRadius: 16,
    borderWidth: 1,
    overflow: "hidden",
    marginBottom: 16,
  },
  draftBanner: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
    marginBottom: 16,
    alignItems: 'center',
  },
  draftText: {
    fontSize: 13,
    fontWeight: '600',
  },
  priceBandsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  image: {
    width: "100%",
    height: "100%",
  },
  card: {
    borderWidth: 1,
    borderRadius: 16,
    padding: 16,
    gap: 12,
  },
  name: {
    fontSize: 20,
    fontWeight: "700",
  },
  category: {
    fontSize: 13,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  label: {
    fontSize: 13,
  },
  value: {
    fontSize: 13,
    fontWeight: "500",
  },
  valueHighlight: {
    fontSize: 16,
    fontWeight: "700",
  },
  notesBlock: {
    marginTop: 16,
  },
  notesHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  notesAddButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  notesInput: {
    marginTop: 8,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    lineHeight: 18,
    minHeight: 100,
    maxHeight: 220,
  },
  notesActions: {
    marginTop: 8,
    flexDirection: "row",
    justifyContent: "flex-end",
  },
  saveButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
  },
  saveButtonText: {
    fontSize: 13,
    fontWeight: "600",
  },
});