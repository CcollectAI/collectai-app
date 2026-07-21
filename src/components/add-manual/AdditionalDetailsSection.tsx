import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, Keyboard, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@/hooks/useAppTheme';

interface CustomField {
  key: string;
  value: string;
}

interface Props {
  source: string;
  onSourceChange: (text: string) => void;
  notes: string;
  onNotesChange: (text: string) => void;
  quantity: string;
  onQuantityChange: (text: string) => void;
  acquisitionDate: string;
  onAcquisitionDateChange: (text: string) => void;
  /** When true, show the "add custom fields" UI for non-standard categories. */
  showCustomFields?: boolean;
  customFields: CustomField[];
  onCustomFieldsChange: (fields: CustomField[]) => void;
}

export const AdditionalDetailsSection = React.memo(function AdditionalDetailsSection({
  source, onSourceChange, notes, onNotesChange,
  quantity, onQuantityChange, acquisitionDate, onAcquisitionDateChange,
  showCustomFields, customFields, onCustomFieldsChange,
}: Props) {
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="document-text-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>{t('add_manual.additional_details')}</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Quantity */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Quantity</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="layers-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={quantity}
              onChangeText={onQuantityChange}
              placeholder="1"
              placeholderTextColor={colors.muted}
              keyboardType="number-pad"
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Quantity"
              returnKeyType="next"
            />
          </View>
        </View>

        {/* Acquisition date */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>{t('add_manual.date_acquired')}</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={acquisitionDate}
              onChangeText={onAcquisitionDateChange}
              placeholder="DD-MM-YYYY"
              placeholderTextColor={colors.muted}
              keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'default'}
              maxLength={10}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel={t('add_manual.date_acquired_a11y')}
              returnKeyType="next"
            />
          </View>
        </View>

        {/* Source */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Source</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="storefront-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={source}
              onChangeText={onSourceChange}
              placeholder={t('add_manual.source_placeholder')}
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel={t('add_manual.source_a11y')}
              returnKeyType="next"
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
              placeholder={t('add_manual.notes_placeholder')}
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
                accessibilityLabel={t('add_manual.done_notes_a11y')}
              >
                <Ionicons name="checkmark" size={18} color="#fff" />
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Custom key/value fields — shown for custom categories */}
        {showCustomFields && (
          <View style={styles.fieldBlock}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>{t('add_manual.custom_details')}</Text>
            <Text style={[styles.customHint, { color: colors.muted }]}>
              Add any details specific to your item (e.g. Vintage, Region, Size)
            </Text>
            {customFields.map((field, idx) => (
              <View key={idx} style={styles.customFieldRow}>
                <View style={[styles.customFieldInput, { borderColor: colors.border, backgroundColor: colors.background }]}>
                  <TextInput
                    value={field.key}
                    onChangeText={(text) => {
                      const updated = [...customFields];
                      updated[idx] = { ...updated[idx], key: text };
                      onCustomFieldsChange(updated);
                    }}
                    placeholder={t('add_manual.field_name_placeholder')}
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    accessibilityLabel={`Custom field ${idx + 1} name`}
                  />
                </View>
                <View style={[styles.customFieldInput, { flex: 1.5, borderColor: colors.border, backgroundColor: colors.background }]}>
                  <TextInput
                    value={field.value}
                    onChangeText={(text) => {
                      const updated = [...customFields];
                      updated[idx] = { ...updated[idx], value: text };
                      onCustomFieldsChange(updated);
                    }}
                    placeholder="Value"
                    placeholderTextColor={colors.muted}
                    style={[styles.input, { color: colors.text }]}
                    accessibilityLabel={`Custom field ${idx + 1} value`}
                  />
                </View>
                <TouchableOpacity
                  onPress={() => onCustomFieldsChange(customFields.filter((_, i) => i !== idx))}
                  hitSlop={8}
                  accessibilityLabel={t('add_manual.remove_field_a11y')}
                >
                  <Ionicons name="close-circle" size={20} color={colors.muted} />
                </TouchableOpacity>
              </View>
            ))}
            <TouchableOpacity
              onPress={() => onCustomFieldsChange([...customFields, { key: '', value: '' }])}
              style={[styles.addFieldBtn, { borderColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel={t('add_manual.add_custom_field_a11y')}
            >
              <Ionicons name="add" size={16} color={colors.accent} />
              <Text style={[styles.addFieldText, { color: colors.accent }]}>{t('add_manual.add_field')}</Text>
            </TouchableOpacity>
          </View>
        )}
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
  customHint: { fontSize: 12, marginBottom: 10, fontStyle: 'italic' },
  customFieldRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8,
  },
  customFieldInput: {
    flex: 1, flexDirection: 'row', alignItems: 'center',
    borderWidth: 1, borderRadius: 10, paddingHorizontal: 10, height: 40,
  },
  addFieldBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, paddingVertical: 10, borderWidth: 1, borderRadius: 10, borderStyle: 'dashed',
  },
  addFieldText: { fontSize: 13, fontWeight: '600' },
});
