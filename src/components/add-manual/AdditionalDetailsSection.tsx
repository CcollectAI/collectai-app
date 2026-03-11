import React from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, Keyboard } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

interface Props {
  source: string;
  onSourceChange: (text: string) => void;
  notes: string;
  onNotesChange: (text: string) => void;
}

export const AdditionalDetailsSection = React.memo(function AdditionalDetailsSection({
  source, onSourceChange, notes, onNotesChange,
}: Props) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="document-text-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Additional Details</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Source</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="storefront-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={source}
              onChangeText={onSourceChange}
              placeholder="Twitch stream, local shop, Cardmarket…"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Source where item was purchased"
            />
          </View>
        </View>

        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Notes</Text>
          <View style={[styles.inputWrapMultiline, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <TextInput
              value={notes}
              onChangeText={onNotesChange}
              multiline
              numberOfLines={3}
              placeholder="Print line, story, plans, etc."
              placeholderTextColor={colors.muted}
              style={[styles.inputMultiline, { color: colors.text }]}
              textAlignVertical="top"
              accessibilityLabel="Notes"
            />
            {notes.trim().length > 0 && (
              <TouchableOpacity
                onPress={() => Keyboard.dismiss()}
                style={[styles.notesDoneBtn, { backgroundColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Done editing notes"
              >
                <Ionicons name="checkmark" size={18} color="#fff" />
              </TouchableOpacity>
            )}
          </View>
        </View>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  section: { marginBottom: 20 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  sectionTitle: { fontSize: 14, fontWeight: '600' },
  card: { borderRadius: 12, borderWidth: 1, padding: 14 },
  fieldBlock: { marginBottom: 14 },
  fieldLabel: { fontSize: 13, fontWeight: '600', marginBottom: 6 },
  inputWrap: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, height: 44,
  },
  inputIcon: { marginRight: 8 },
  input: { flex: 1, fontSize: 14, paddingVertical: 0 },
  inputWrapMultiline: { borderWidth: 1, borderRadius: 10, padding: 12, minHeight: 88 },
  inputMultiline: { flex: 1, fontSize: 14, minHeight: 64 },
  notesDoneBtn: {
    position: 'absolute', bottom: 8, right: 8, width: 32, height: 32,
    borderRadius: 16, alignItems: 'center', justifyContent: 'center',
  },
});
