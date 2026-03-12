import React, { useState } from 'react';
import {
  View, Text, StyleSheet, Modal, FlatList, TouchableOpacity, TextInput, Platform, Keyboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';

const CONDITION_CHIPS = [
  { label: 'Mint', short: 'M' },
  { label: 'Near Mint', short: 'NM' },
  { label: 'Excellent', short: 'EX' },
  { label: 'Good', short: 'G' },
  { label: 'PSA 10', short: '10' },
  { label: 'PSA 9', short: '9' },
  { label: 'Raw', short: 'Raw' },
];

interface FormField {
  value: string;
  touched: boolean;
  error: string | null;
  onChange: (text: string) => void;
  onBlur: () => void;
}

interface Props {
  conditionGrade: string;
  onConditionChange: (grade: string) => void;
  purchasePriceField: FormField;
  estimatedValueField: FormField;
  currencySymbol: string;
}

export const ConditionValueSection = React.memo(function ConditionValueSection({
  conditionGrade, onConditionChange, purchasePriceField, estimatedValueField, currencySymbol,
}: Props) {
  const { colors } = useAppTheme();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [customCondition, setCustomCondition] = useState('');

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="diamond-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Condition & Value</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Condition Dropdown */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Condition / Grade</Text>
          <TouchableOpacity
            activeOpacity={0.7}
            onPress={() => { Keyboard.dismiss(); fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setPickerOpen(true); }}
            style={[styles.dropdownTrigger, { borderColor: conditionGrade ? colors.accent : colors.border, backgroundColor: colors.background }]}
            accessibilityRole="button"
            accessibilityLabel={conditionGrade ? `Condition: ${conditionGrade}` : 'Select condition'}
          >
            <Text style={[styles.dropdownText, { color: conditionGrade ? colors.text : colors.muted }]} numberOfLines={1}>
              {conditionGrade || 'Select condition'}
            </Text>
            <Ionicons name="chevron-down" size={16} color={colors.muted} />
          </TouchableOpacity>
        </View>

        {/* Condition Picker Modal */}
        <Modal visible={pickerOpen} animationType="slide" transparent onRequestClose={() => setPickerOpen(false)}>
          <View style={styles.overlay}>
            <View style={[styles.sheet, { backgroundColor: colors.card }]}>
              <View style={[styles.header, { borderBottomColor: colors.border }]}>
                <Text style={[styles.title, { color: colors.text }]}>Select Condition</Text>
                <TouchableOpacity onPress={() => setPickerOpen(false)} hitSlop={12}>
                  <Ionicons name="close" size={22} color={colors.muted} />
                </TouchableOpacity>
              </View>
              <FlatList
                data={CONDITION_CHIPS}
                keyExtractor={(item) => item.label}
                keyboardShouldPersistTaps="handled"
                style={styles.list}
                ListHeaderComponent={
                  conditionGrade && !CONDITION_CHIPS.find(c => c.label === conditionGrade) ? null : (
                    conditionGrade ? (
                      <TouchableOpacity
                        activeOpacity={0.6}
                        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onConditionChange(''); setPickerOpen(false); }}
                        style={[styles.row, { borderBottomColor: colors.border }]}
                      >
                        <Text style={[styles.rowText, { color: colors.muted, fontStyle: 'italic' }]}>None (clear selection)</Text>
                      </TouchableOpacity>
                    ) : null
                  )
                }
                renderItem={({ item }) => {
                  const isSelected = conditionGrade === item.label;
                  return (
                    <TouchableOpacity
                      activeOpacity={0.6}
                      onPress={() => {
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                        onConditionChange(item.label);
                        setCustomCondition('');
                        setPickerOpen(false);
                      }}
                      style={[styles.row, { borderBottomColor: colors.border }, isSelected && { backgroundColor: colors.accent + '12' }]}
                    >
                      <Text style={[styles.rowText, { color: isSelected ? colors.accent : colors.text }]}>{item.label}</Text>
                      {isSelected && <Ionicons name="checkmark" size={18} color={colors.accent} />}
                    </TouchableOpacity>
                  );
                }}
                ListFooterComponent={
                  <View style={{ paddingHorizontal: 20, paddingVertical: 14 }}>
                    <Text style={[styles.fieldLabel, { color: colors.muted }]}>Custom</Text>
                    <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
                      <TextInput
                        value={customCondition}
                        onChangeText={setCustomCondition}
                        placeholder="Enter custom condition..."
                        placeholderTextColor={colors.muted}
                        style={[styles.input, { color: colors.text }]}
                        accessibilityLabel="Custom condition"
                        returnKeyType="done"
                        onSubmitEditing={() => {
                          if (customCondition.trim()) {
                            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                            onConditionChange(customCondition.trim());
                            setCustomCondition('');
                            setPickerOpen(false);
                          }
                        }}
                      />
                    </View>
                  </View>
                }
              />
            </View>
          </View>
        </Modal>

        {/* Prices */}
        <View style={styles.fieldRow}>
          <View style={[styles.fieldBlock, { flex: 1, marginRight: 8 }]}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>Purchase Price</Text>
            <View style={[styles.inputWrap, { borderColor: purchasePriceField.touched && purchasePriceField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
              <Text style={[styles.currencyPrefix, { color: colors.muted }]}>{currencySymbol}</Text>
              <TextInput
                value={purchasePriceField.value}
                onChangeText={purchasePriceField.onChange}
                onBlur={purchasePriceField.onBlur}
                keyboardType="decimal-pad"
                placeholder="0.00"
                placeholderTextColor={colors.muted}
                style={[styles.input, { color: colors.text }]}
                accessibilityLabel="Purchase price"
                returnKeyType="next"
              />
            </View>
            {purchasePriceField.touched && purchasePriceField.error && (
              <Text style={[styles.fieldError, { color: colors.danger }]}>{purchasePriceField.error}</Text>
            )}
          </View>
          <View style={[styles.fieldBlock, { flex: 1 }]}>
            <Text style={[styles.fieldLabel, { color: colors.text }]}>Estimated Value</Text>
            <View style={[styles.inputWrap, { borderColor: estimatedValueField.touched && estimatedValueField.error ? colors.danger : colors.border, backgroundColor: colors.background }]}>
              <Text style={[styles.currencyPrefix, { color: colors.muted }]}>{currencySymbol}</Text>
              <TextInput
                value={estimatedValueField.value}
                onChangeText={estimatedValueField.onChange}
                onBlur={estimatedValueField.onBlur}
                keyboardType="decimal-pad"
                placeholder="0.00"
                placeholderTextColor={colors.muted}
                style={[styles.input, { color: colors.text }]}
                accessibilityLabel="Estimated value"
                returnKeyType="done"
              />
            </View>
            {estimatedValueField.touched && estimatedValueField.error && (
              <Text style={[styles.fieldError, { color: colors.danger }]}>{estimatedValueField.error}</Text>
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
  fieldRow: { flexDirection: 'row' },
  fieldLabel: { fontSize: 13, fontWeight: '600', marginBottom: 6 },
  inputWrap: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, height: 44,
  },
  input: { flex: 1, fontSize: 14, paddingVertical: 0 },
  currencyPrefix: { fontSize: 14, fontWeight: '600', marginRight: 4 },
  fieldError: { fontSize: 12, marginTop: 4, marginLeft: 4 },
  dropdownTrigger: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, height: 44,
  },
  dropdownText: { flex: 1, fontSize: 14 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '70%', paddingBottom: Platform.OS === 'ios' ? 34 : 16 },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 16, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  title: { fontSize: 17, fontWeight: '600' },
  list: { flexGrow: 0 },
  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 14, paddingHorizontal: 20, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  rowText: { flex: 1, fontSize: 15, fontWeight: '500' },
});
