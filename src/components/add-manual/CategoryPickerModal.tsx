import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  View, Text, StyleSheet, Modal, FlatList, TouchableOpacity, TextInput, Platform, Keyboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { CATEGORIES as ALL_CATS } from '@/constants/categories';

const CATEGORY_OPTIONS = ALL_CATS.map((c) => ({ label: c.name, slug: c.slug }));

/** Sentinel value passed to onSelect when user taps "Other (custom)". */
export const CUSTOM_CATEGORY_SENTINEL = '__custom__';

interface Props {
  visible: boolean;
  selectedCategory: string;
  onSelect: (label: string) => void;
  onClear: () => void;
  onClose: () => void;
  onSuggestNew: () => void;
}

export const CategoryPickerModal = React.memo(function CategoryPickerModal({
  visible, selectedCategory, onSelect, onClear, onClose, onSuggestNew,
}: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return CATEGORY_OPTIONS;
    return CATEGORY_OPTIONS.filter((c) => c.label.toLowerCase().includes(q));
  }, [search]);

  const handleClose = () => { setSearch(''); onClose(); };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={handleClose}>
      <View style={styles.overlay}>
        <View style={[styles.sheet, { backgroundColor: colors.card }]}>
          <View style={[styles.header, { borderBottomColor: colors.border }]}>
            <Text style={[styles.title, { color: colors.text }]}>{t('category_picker.title')}</Text>
            <TouchableOpacity onPress={handleClose} hitSlop={12}>
              <Ionicons name="close" size={22} color={colors.muted} />
            </TouchableOpacity>
          </View>
          <View style={[styles.searchWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="search-outline" size={16} color={colors.muted} style={styles.searchIcon} />
            <TextInput
              value={search}
              onChangeText={setSearch}
              placeholder={t('category_picker.search_placeholder')}
              placeholderTextColor={colors.muted}
              style={[styles.searchInput, { color: colors.text }]}
              autoFocus
              accessibilityLabel={t('category_picker.search_a11y')}
            />
            {search.length > 0 && (
              <TouchableOpacity onPress={() => setSearch('')} hitSlop={8}>
                <Ionicons name="close-circle" size={16} color={colors.muted} />
              </TouchableOpacity>
            )}
          </View>
          <FlatList
            data={filtered}
            keyExtractor={(item) => item.slug}
            keyboardShouldPersistTaps="handled"
            style={styles.list}
            ListHeaderComponent={
              selectedCategory && !search ? (
                <TouchableOpacity
                  activeOpacity={0.6}
                  onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onClear(); handleClose(); }}
                  style={[styles.row, { borderBottomColor: colors.border }]}
                >
                  <Ionicons name="close-circle-outline" size={18} color={colors.muted} style={{ marginRight: 12 }} />
                  <Text style={[styles.rowText, { color: colors.muted, fontStyle: 'italic' }]}>{t('category_picker.none')}</Text>
                </TouchableOpacity>
              ) : null
            }
            renderItem={({ item }) => {
              const isSelected = selectedCategory === item.label;
              return (
                <TouchableOpacity
                  activeOpacity={0.6}
                  onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onSelect(item.label); handleClose(); }}
                  style={[styles.row, { borderBottomColor: colors.border }, isSelected && { backgroundColor: colors.accent + '12' }]}
                >
                  <Text style={[styles.rowText, { color: isSelected ? colors.accent : colors.text }]}>{item.label}</Text>
                  {isSelected && <Ionicons name="checkmark" size={18} color={colors.accent} />}
                </TouchableOpacity>
              );
            }}
            ListEmptyComponent={
              <View style={styles.empty}>
                <Text style={[styles.emptyText, { color: colors.muted }]}>No categories match "{search}"</Text>
              </View>
            }
            ListFooterComponent={
              <View>
                {/* Custom category — lets the user type any category name */}
                <TouchableOpacity
                  activeOpacity={0.6}
                  onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onSelect(CUSTOM_CATEGORY_SENTINEL); handleClose(); }}
                  style={[styles.row, { borderBottomColor: colors.border }]}
                >
                  <Ionicons name="create-outline" size={18} color={colors.accent} style={{ marginRight: 12 }} />
                  <Text style={[styles.rowText, { color: colors.accent, fontWeight: '600' }]}>{t('category_picker.other')}</Text>
                </TouchableOpacity>
                {/* Suggest new category for us to add official support */}
                <TouchableOpacity
                  activeOpacity={0.6}
                  onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); handleClose(); onSuggestNew(); }}
                  style={[styles.row, { borderBottomColor: colors.border }]}
                >
                  <Ionicons name="add-circle-outline" size={18} color={colors.muted} style={{ marginRight: 12 }} />
                  <Text style={[styles.rowText, { color: colors.muted }]}>{t('category_picker.suggest_new')}</Text>
                </TouchableOpacity>
              </View>
            }
          />
        </View>
      </View>
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
  searchWrap: {
    flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 10,
    paddingHorizontal: 12, height: 40, marginHorizontal: 16, marginVertical: 12,
  },
  searchIcon: { marginRight: 8 },
  searchInput: { flex: 1, fontSize: 14, paddingVertical: 0 },
  list: { flexGrow: 0 },
  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 14, paddingHorizontal: 20, borderBottomWidth: StyleSheet.hairlineWidth,
  },
  rowText: { flex: 1, fontSize: 15, fontWeight: '500' },
  empty: { paddingVertical: 32, alignItems: 'center' },
  emptyText: { fontSize: 14 },
});
