import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  View, Text, StyleSheet, Modal, FlatList, TouchableOpacity, TextInput, Platform, Keyboard,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { CATEGORIES as ALL_CATS } from '@/constants/categories';
import { useFollowedCategories } from '@/hooks/useFollowedCategories';

const CATEGORY_OPTIONS = ALL_CATS.map((c) => ({ label: c.name, slug: c.slug }));

type Row =
  | { kind: 'category'; label: string; slug: string }
  | { kind: 'header'; key: string; text: string };

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
  const { followed } = useFollowedCategories();

  // When searching, flatten with no headers (search across the full list).
  // When idle, surface followed categories on top with a "Your collections"
  // header so the picks the user made during onboarding are one tap away.
  const rows = useMemo<Row[]>(() => {
    const q = search.toLowerCase().trim();
    if (q) {
      return CATEGORY_OPTIONS
        .filter((c) => c.label.toLowerCase().includes(q))
        .map<Row>((c) => ({ kind: 'category', ...c }));
    }
    const followedRows: Row[] = CATEGORY_OPTIONS
      .filter((c) => followed.has(c.slug))
      .map<Row>((c) => ({ kind: 'category', ...c }));
    const restRows: Row[] = CATEGORY_OPTIONS
      .filter((c) => !followed.has(c.slug))
      .map<Row>((c) => ({ kind: 'category', ...c }));
    if (followedRows.length === 0) return restRows;
    return [
      { kind: 'header', key: 'h-followed', text: t('category_picker.your_collections', { defaultValue: 'Your collections' }) },
      ...followedRows,
      { kind: 'header', key: 'h-all', text: t('category_picker.all_categories', { defaultValue: 'All categories' }) },
      ...restRows,
    ];
  }, [search, followed, t]);

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
            data={rows}
            keyExtractor={(item) => item.kind === 'header' ? item.key : item.slug}
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
              if (item.kind === 'header') {
                return (
                  <View style={[styles.sectionHeader, { backgroundColor: colors.background }]}>
                    <Text style={[styles.sectionHeaderText, { color: colors.muted }]}>{item.text}</Text>
                  </View>
                );
              }
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
  sectionHeader: {
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  sectionHeaderText: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  empty: { paddingVertical: 32, alignItems: 'center' },
  emptyText: { fontSize: 14 },
});
