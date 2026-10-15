/**
 * Bottom-sheet picker for a category field's fixed options (Language, Printing,
 * Edition, Rarity, Line, Box Condition…). 2026-10-15, Merle: "add manual should
 * have a dropdown menu, not just listed chips" — 125 select fields across the
 * category forms rendered every option as a chip, so a Pokémon form showed
 * nine language chips, four printing chips, and so on, stacked down the page.
 *
 * Same sheet as CategoryPickerModal (header, rows, checkmark, "None (clear
 * selection)") so the two pickers on one form look and behave alike. No search:
 * the longest option list is ~10 entries.
 */
import { ToastHost } from '@/components/Toast';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { View, Text, StyleSheet, Modal, FlatList, TouchableOpacity, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';

interface Props {
  visible: boolean;
  title: string;
  options: readonly string[];
  selected: string;
  onSelect: (value: string) => void;
  onClose: () => void;
}

export const OptionPickerModal = React.memo(function OptionPickerModal({
  visible, title, options, selected, onSelect, onClose,
}: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <TouchableOpacity
        activeOpacity={1}
        style={styles.overlay}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel={t('common.close')}
      >
        {/* Inner touchable swallows taps so only the dimmed area closes. */}
        <TouchableOpacity activeOpacity={1} style={[styles.sheet, { backgroundColor: colors.card }]}>
          <View style={[styles.header, { borderBottomColor: colors.border }]}>
            <Text style={[styles.title, { color: colors.text }]}>{title}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel={t('common.close')}>
              <Ionicons name="close" size={22} color={colors.muted} />
            </TouchableOpacity>
          </View>
          <FlatList
            data={options as string[]}
            keyExtractor={(item) => item}
            style={styles.list}
            ListHeaderComponent={
              selected ? (
                <TouchableOpacity
                  activeOpacity={0.6}
                  onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onSelect(''); onClose(); }}
                  style={[styles.row, { borderBottomColor: colors.border }]}
                  accessibilityRole="button"
                >
                  <Ionicons name="close-circle-outline" size={18} color={colors.muted} style={{ marginRight: 12 }} />
                  <Text style={[styles.rowText, { color: colors.muted, fontStyle: 'italic' }]}>{t('category_picker.none')}</Text>
                </TouchableOpacity>
              ) : null
            }
            renderItem={({ item }) => {
              const isSelected = selected === item;
              return (
                <TouchableOpacity
                  activeOpacity={0.6}
                  onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onSelect(item); onClose(); }}
                  style={[styles.row, { borderBottomColor: colors.border }, isSelected && { backgroundColor: colors.accent + '12' }]}
                  accessibilityRole="button"
                  accessibilityLabel={`${title}: ${item}`}
                  accessibilityState={{ selected: isSelected }}
                >
                  <Text style={[styles.rowText, { color: isSelected ? colors.accent : colors.text }]}>{item}</Text>
                  {isSelected && <Ionicons name="checkmark" size={18} color={colors.accent} />}
                </TouchableOpacity>
              );
            }}
          />
        </TouchableOpacity>
      </TouchableOpacity>
      <ToastHost />
    </Modal>
  );
});

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '70%', paddingBottom: Platform.OS === 'ios' ? 34 : 16 },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 16, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  title: { fontSize: 17, fontWeight: '600' },
  list: { flexGrow: 0 },
  row: {
    flexDirection: 'row', alignItems: 'center', minHeight: 48,
    paddingVertical: 14, paddingHorizontal: 20, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  rowText: { flex: 1, fontSize: 15, fontWeight: '500' },
});
