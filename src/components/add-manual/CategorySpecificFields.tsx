import React from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import type { CategoryField } from '@/constants/categoryFields';

interface Props {
  categoryLabel: string;
  fields: CategoryField[];
  values: Record<string, string | boolean>;
  onChange: (key: string, value: string | boolean) => void;
}

export const CategorySpecificFields = React.memo(function CategorySpecificFields({
  categoryLabel, fields, values, onChange,
}: Props) {
  const { colors } = useAppTheme();

  if (fields.length === 0) return null;

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="options-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>{categoryLabel} Details</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {fields.map((field) => {
          const val = values[field.key];

          if (field.type === 'boolean') {
            return (
              <TouchableOpacity
                key={field.key}
                activeOpacity={0.7}
                onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onChange(field.key, !val); }}
                style={[styles.booleanRow, { borderBottomColor: colors.border }]}
                accessibilityRole="switch"
                accessibilityLabel={field.label}
                accessibilityState={{ checked: !!val }}
              >
                <View style={styles.booleanLeft}>
                  <Ionicons
                    name={(field.icon ?? 'checkbox-outline') as keyof typeof Ionicons.glyphMap}
                    size={16}
                    color={val ? colors.accent : colors.muted}
                    style={{ marginRight: 8 }}
                  />
                  <Text style={[styles.fieldLabel, { color: colors.text, marginBottom: 0 }]}>{field.label}</Text>
                </View>
                <View style={[styles.toggleTrack, val ? { backgroundColor: colors.accent } : { backgroundColor: colors.border }]}>
                  <View style={[styles.toggleThumb, val ? styles.toggleThumbOn : undefined]} />
                </View>
              </TouchableOpacity>
            );
          }

          if (field.type === 'select' && field.options) {
            return (
              <View key={field.key} style={styles.fieldBlock}>
                <Text style={[styles.fieldLabel, { color: colors.text }]}>{field.label}</Text>
                <View style={styles.chipRow}>
                  {field.options.map((opt) => {
                    const isSelected = val === opt;
                    return (
                      <AnimatedPressable
                        key={opt}
                        style={[
                          styles.selectChip,
                          { backgroundColor: isSelected ? colors.accent + '20' : colors.background, borderColor: isSelected ? colors.accent : colors.border },
                        ]}
                        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onChange(field.key, val === opt ? '' : opt); }}
                        accessibilityRole="button"
                        accessibilityLabel={`${field.label}: ${opt}`}
                        accessibilityState={{ selected: isSelected }}
                      >
                        <Text style={[styles.selectChipText, { color: isSelected ? colors.accent : colors.text }]}>{opt}</Text>
                      </AnimatedPressable>
                    );
                  })}
                </View>
              </View>
            );
          }

          return (
            <View key={field.key} style={styles.fieldBlock}>
              <Text style={[styles.fieldLabel, { color: colors.text }]}>{field.label}</Text>
              <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                <Ionicons
                  name={(field.icon ?? 'text-outline') as keyof typeof Ionicons.glyphMap}
                  size={16}
                  color={colors.muted}
                  style={styles.inputIcon}
                />
                <TextInput
                  value={typeof val === 'string' ? val : ''}
                  onChangeText={(text) => onChange(field.key, text)}
                  placeholder={field.placeholder ?? ''}
                  placeholderTextColor={colors.muted}
                  style={[styles.input, { color: colors.text }]}
                  accessibilityLabel={field.label}
                  returnKeyType="next"
                />
              </View>
            </View>
          );
        })}
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
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  selectChip: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8, borderWidth: 1 },
  selectChipText: { fontSize: 12, fontWeight: '500' },
  booleanRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  booleanLeft: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  toggleTrack: { width: 44, height: 24, borderRadius: 12, justifyContent: 'center', paddingHorizontal: 2 },
  toggleThumb: { width: 20, height: 20, borderRadius: 10, backgroundColor: '#FFFFFF' },
  toggleThumbOn: { alignSelf: 'flex-end' },
});
