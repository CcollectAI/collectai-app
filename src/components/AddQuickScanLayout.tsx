import React from "react";
import { ScrollView, View, Text, TextInput, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/theme";

type Props = {
  name: string;
  setName: (v: string) => void;
  estimatedValue: string;
  setEstimatedValue: (v: string) => void;
  notes: string;
  setNotes: (v: string) => void;
  lastScanSummary?: string | null;
  onQuickScan: () => void;
  onSave: () => void;
};

export const AddQuickScanLayout: React.FC<Props> = ({
  name,
  setName,
  estimatedValue,
  setEstimatedValue,
  notes,
  setNotes,
  lastScanSummary,
  onQuickScan,
  onSave,
}) => {
  const theme = useAppTheme();

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.colors.background }}
      contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
    >
      {/* QuickScan hero */}
      <View style={[styles.card, { backgroundColor: theme.colors.card, marginBottom: 16 }]}>
        <Text style={[styles.title, { color: theme.colors.text }]}>QuickScan</Text>
        <Text style={[styles.subtitle, { color: theme.colors.muted }]}>
          Take a photo to identify the item and pre-fill details automatically.
        </Text>

        <Pressable
          onPress={onQuickScan}
          accessibilityRole="button"
          accessibilityLabel="Open camera for QuickScan"
          style={[styles.primaryButton, { backgroundColor: theme.colors.primary }]}
        >
          <Ionicons name="camera-outline" size={18} color="#fff" />
          <Text style={styles.primaryButtonText}>Open camera</Text>
        </Pressable>

        {lastScanSummary ? (
          <View style={{ marginTop: 4 }}>
            <Text style={[styles.label, { color: theme.colors.muted }]}>Last scan</Text>
            <Text style={[styles.body, { color: theme.colors.text }]}>{lastScanSummary}</Text>
          </View>
        ) : (
          <Text style={[styles.body, { color: theme.colors.muted }]}>
            No scan yet — try scanning a card, figure, or box.
          </Text>
        )}
      </View>

      {/* Manual entry */}
      <View style={[styles.card, { backgroundColor: theme.colors.card }]}>
        <Text style={[styles.title, { color: theme.colors.text }]}>Add manually</Text>

        <TextInput
          value={name}
          onChangeText={setName}
          placeholder="Item name"
          accessibilityLabel="Item name"
          style={[styles.input, { borderColor: theme.colors.border, color: theme.colors.text }]}
          placeholderTextColor={theme.colors.muted}
        />

        <TextInput
          value={estimatedValue}
          onChangeText={setEstimatedValue}
          placeholder="Estimated value (€)"
          accessibilityLabel="Estimated value"
          keyboardType="numeric"
          style={[styles.input, { borderColor: theme.colors.border, color: theme.colors.text }]}
          placeholderTextColor={theme.colors.muted}
        />

        <TextInput
          value={notes}
          onChangeText={setNotes}
          placeholder="Notes (set, condition, extras…)"
          accessibilityLabel="Notes"
          multiline
          style={[
            styles.input,
            {
              height: 80,
              textAlignVertical: "top",
              borderColor: theme.colors.border,
              color: theme.colors.text,
            },
          ]}
          placeholderTextColor={theme.colors.muted}
        />

        <Pressable
          onPress={onSave}
          accessibilityRole="button"
          accessibilityLabel="Save to collection"
          style={[
            styles.primaryButton,
            { backgroundColor: theme.colors.primary, marginTop: 12 },
          ]}
        >
          <Text style={styles.primaryButtonText}>Save to collection</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  card: {
    padding: 16,
    borderRadius: 12,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    marginBottom: 12,
  },
  label: {
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 2,
  },
  body: {
    fontSize: 12,
  },
  primaryButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    borderRadius: 999,
    marginBottom: 12,
  },
  primaryButtonText: {
    marginLeft: 8,
    fontSize: 14,
    fontWeight: "600",
    color: "#fff",
  },
  input: {
    marginTop: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    fontSize: 14,
  },
});
