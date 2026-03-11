/**
 * Basic Information section for the Create Event form.
 *
 * Renders title input, kind dropdown, and category dropdown.
 *
 * Extracted from app/create-event.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { CATEGORIES } from '@/constants/categories';
import CompactSelect from '@/components/CompactSelect';
import type { EventKind } from '@/data/events';

const EVENT_KINDS: { label: string; value: EventKind }[] = [
  { label: 'Meetup', value: 'meetup' },
  { label: 'Drop', value: 'collection_drop' },
  { label: 'Stream', value: 'stream' },
  { label: 'Convention', value: 'convention' },
  { label: 'Release', value: 'release' },
];

interface FormFieldState {
  value: string;
  error: string | null;
  touched: boolean;
  onChange: (text: string) => void;
  onBlur: () => void;
}

interface EventFormHeaderProps {
  titleField: FormFieldState;
  kind: EventKind;
  onKindChange: (kind: EventKind) => void;
  categoryId: string | undefined;
  onCategoryChange: (categoryId: string | undefined) => void;
}

export const EventFormHeader = React.memo(function EventFormHeader({
  titleField,
  kind,
  onKindChange,
  categoryId,
  onCategoryChange,
}: EventFormHeaderProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="information-circle-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Basic Information</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Title */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>
            Title <Text style={{ color: colors.accent }}>*</Text>
          </Text>
          <View style={[styles.inputWrap, { borderColor: titleField.touched && titleField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="text-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={titleField.value}
              onChangeText={titleField.onChange}
              onBlur={titleField.onBlur}
              placeholder="e.g. Rotterdam TCG Meetup"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Event title"
            />
          </View>
          {titleField.touched && titleField.error && <Text style={styles.fieldError}>{titleField.error}</Text>}
        </View>

        {/* Kind dropdown */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Kind</Text>
          <CompactSelect
            title="Kind"
            value={EVENT_KINDS.find((k) => k.value === kind)?.label}
            options={EVENT_KINDS.map((k) => k.label)}
            onChange={(label) => {
              const match = EVENT_KINDS.find((k) => k.label === label);
              if (match) onKindChange(match.value);
            }}
          />
        </View>

        {/* Category dropdown */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Category (optional)</Text>
          <CompactSelect
            title="Category"
            searchable
            value={categoryId ? CATEGORIES.find((c) => c.slug === categoryId)?.name ?? 'None' : 'None'}
            options={['None', ...CATEGORIES.map((c) => c.name)]}
            onChange={(name) => {
              if (name === 'None') {
                onCategoryChange(undefined);
              } else {
                const match = CATEGORIES.find((c) => c.name === name);
                if (match) onCategoryChange(match.slug);
              }
            }}
          />
        </View>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  fieldBlock: {
    marginBottom: 14,
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 6,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 44,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 0,
  },
  fieldError: {
    fontSize: 12,
    color: '#EF4444',
    marginTop: 4,
    marginLeft: 4,
  },
});
