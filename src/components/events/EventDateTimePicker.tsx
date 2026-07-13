/**
 * Date & Time section for the Create Event form.
 *
 * Date + End Date use a native tap-to-pick calendar
 * (@react-native-community/datetimepicker). The value is STORED as ISO
 * `YYYY-MM-DD` (so the form validator, buildEventInput, and the server contract
 * are unchanged) but DISPLAYED as `DD-MM-YYYY`. Time stays a free-text field.
 *
 * Extracted from app/create-event.tsx to reduce file size.
 */
import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { View, Text, TextInput, StyleSheet, Platform, Modal, Pressable } from 'react-native';
import DateTimePicker, { type DateTimePickerEvent } from '@react-native-community/datetimepicker';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { parseIso, toIso, formatDMY } from '@/lib/eventDate';

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
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const [picker, setPicker] = useState<null | 'date' | 'end'>(null);

  const currentIso = picker === 'end' ? endDate : dateField.value;
  const pickerValue = parseIso(currentIso) ?? new Date();

  const applyDate = useCallback(
    (which: 'date' | 'end', d: Date) => {
      const iso = toIso(d);
      if (which === 'end') {
        onEndDateChange(iso);
      } else {
        dateField.onChange(iso);
        dateField.onBlur();
      }
    },
    [dateField, onEndDateChange],
  );

  const onChange = useCallback(
    (event: DateTimePickerEvent, selected?: Date) => {
      const which = picker;
      if (which === null) return;
      if (Platform.OS === 'android') {
        setPicker(null);
        if (event.type === 'set' && selected) applyDate(which, selected);
        return;
      }
      // iOS: inline picker updates live as the user scrolls; stays open until Done.
      if (selected) applyDate(which, selected);
    },
    [picker, applyDate],
  );

  const dateDisplay = formatDMY(dateField.value);
  const endDisplay = formatDMY(endDate);
  const dateHasError = dateField.touched && !!dateField.error;

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Ionicons name="calendar-outline" size={16} color={colors.accent} />
        <Text style={[styles.sectionTitle, { color: colors.text }]}>{t('event_datetime.title')}</Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {/* Date */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>
            Date <Text style={{ color: colors.accent }}>*</Text>
          </Text>
          <AnimatedPressable
            onPress={() => setPicker('date')}
            style={[styles.inputWrap, { borderColor: dateHasError ? colors.danger : colors.border, backgroundColor: colors.background }]}
            accessibilityRole="button"
            accessibilityLabel={t('event_datetime.date_a11y')}
          >
            <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <Text style={[styles.inputText, { color: dateDisplay ? colors.text : colors.muted }]}>
              {dateDisplay || 'DD-MM-YYYY'}
            </Text>
          </AnimatedPressable>
          {dateHasError && <Text style={[styles.fieldError, { color: colors.danger }]}>{dateField.error}</Text>}
        </View>

        {/* Time */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>{t('event_datetime.time_optional')}</Text>
          <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}>
            <Ionicons name="time-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <TextInput
              value={time}
              onChangeText={onTimeChange}
              placeholder="19:30 CET"
              placeholderTextColor={colors.muted}
              style={[styles.input, { color: colors.text }]}
              accessibilityLabel={t('event_datetime.time_a11y')}
              returnKeyType="next"
            />
          </View>
        </View>

        {/* End Date */}
        <View style={styles.fieldBlock}>
          <Text style={[styles.fieldLabel, { color: colors.text }]}>{t('event_datetime.end_date_optional')}</Text>
          <AnimatedPressable
            onPress={() => setPicker('end')}
            style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.background }]}
            accessibilityRole="button"
            accessibilityLabel={t('event_datetime.end_date_a11y')}
          >
            <Ionicons name="calendar-outline" size={16} color={colors.muted} style={styles.inputIcon} />
            <Text style={[styles.inputText, { color: endDisplay ? colors.text : colors.muted }]}>
              {endDisplay || 'DD-MM-YYYY'}
            </Text>
            {endDisplay ? (
              <AnimatedPressable
                onPress={() => onEndDateChange('')}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel="Clear end date"
              >
                <Ionicons name="close-circle" size={16} color={colors.muted} />
              </AnimatedPressable>
            ) : null}
          </AnimatedPressable>
        </View>
      </View>

      {/* Android renders the picker as a dialog; iOS inside a bottom sheet with Done. */}
      {Platform.OS === 'ios' ? (
        <Modal visible={picker !== null} transparent animationType="slide" onRequestClose={() => setPicker(null)}>
          <Pressable style={styles.modalBackdrop} onPress={() => setPicker(null)}>
            <Pressable style={[styles.modalSheet, { backgroundColor: colors.card }]} onPress={() => {}}>
              <View style={styles.modalHeader}>
                <Text style={[styles.modalTitle, { color: colors.text }]}>
                  {picker === 'end' ? t('event_datetime.end_date_optional') : 'Date'}
                </Text>
                <AnimatedPressable onPress={() => setPicker(null)} accessibilityRole="button" accessibilityLabel="Done">
                  <Text style={[styles.modalDone, { color: colors.accent }]}>Done</Text>
                </AnimatedPressable>
              </View>
              <DateTimePicker
                value={pickerValue}
                mode="date"
                display="inline"
                onChange={onChange}
              />
            </Pressable>
          </Pressable>
        </Modal>
      ) : (
        picker !== null && (
          <DateTimePicker value={pickerValue} mode="date" display="default" onChange={onChange} />
        )
      )}
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
  inputText: {
    flex: 1,
    fontSize: 14,
  },
  fieldError: {
    fontSize: 12,
    marginTop: 4,
    marginLeft: 4,
  },
  modalBackdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  modalSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 12,
    paddingBottom: 24,
    paddingTop: 8,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 8,
    paddingVertical: 10,
  },
  modalTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  modalDone: {
    fontSize: 16,
    fontWeight: '600',
  },
});
