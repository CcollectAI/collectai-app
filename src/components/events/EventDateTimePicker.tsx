/**
 * Date & Time section for the Create Event form.
 *
 * Renders date, time, and end date input fields.
 *
 * Extracted from app/create-event.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

interface FormFieldState {
  value: string;
  error: string | null;
  touched: boolean;
  onChange: (text: string) => void;
  onBlur: () => void;
}

interface EventDateTimePickerProps {
  dateField: FormFieldState;
  time: string;
  onTimeChange: (time: string) => void;
  endDate: string;
  onEndDateChange: (endDate: string) => void;
}

export const EventDateTimePicker = React.memo(function EventDateTimePicker({
  dateField,
  time,
  onTimeChange,
  endDate,
  onEndDateChange,
}: EventDateTimePickerProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="calendar-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Date & Time</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Date */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>
            Date <Text style={{ color: colors.accent }}>*</Text>
          </Text>
          <View style={[styles.inputWrap, { borderColor: dateField.touched && dateField.error ? '#EF4444' : colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={dateField.value}
              onChangeText={dateField.onChange}
              onBlur={dateField.onBlur}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Event date"
            />
          </View>
          {dateField.touched && dateField.error && <Text style={styles.fieldError}>{dateField.error}</Text>}
        </View>

        {/* Time */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>Time (optional)</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="time-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={time}
              onChangeText={onTimeChange}
              placeholder="19:30 CET"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Event time"
            />
          </View>
        </View>

        {/* End Date */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>End Date (optional, for multi-day)</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={endDate}
              onChangeText={onEndDateChange}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel="Event end date"
            />
          </View>
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
