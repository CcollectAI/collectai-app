/**
 * ItemNotesEditor — Editable notes block for item detail screen.
 */

import React, { useRef, useCallback } from 'react';
import { View, Text, TextInput, Pressable, Keyboard, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { radius, text, fontWeight } from '@/theme/tokens';

interface ItemNotesEditorProps {
  notes: string;
  onChangeNotes: (text: string) => void;
  onSaveNotes: () => void;
  keyboardVisible: boolean;
  onLayout: (y: number) => void;
  onFocus: () => void;
}

export const ItemNotesEditor = React.memo(function ItemNotesEditor({
  notes,
  onChangeNotes,
  onSaveNotes,
  keyboardVisible,
  onLayout,
  onFocus,
}: ItemNotesEditorProps) {
  const { colors: theme } = useAppTheme();
  const notesInputRef = useRef<TextInput | null>(null);

  const handleSave = useCallback(() => {
    onSaveNotes();
    Keyboard.dismiss();
  }, [onSaveNotes]);

  return (
    <View
      style={styles.notesBlock}
      onLayout={(e) => { onLayout(e.nativeEvent.layout.y); }}
    >
      <View style={styles.notesHeaderRow}>
        <Text style={[styles.label, { color: theme.muted }]}>
          Notes
        </Text>
        {keyboardVisible && (
          <Pressable
            onPress={handleSave}
            style={[styles.notesDoneBtn, { backgroundColor: theme.accent }]}
            accessibilityRole="button"
            accessibilityLabel="Save notes"
          >
            <Text style={[styles.notesDoneBtnText, { color: theme.accentText }]}>Save</Text>
          </Pressable>
        )}
      </View>

      <TextInput
        ref={notesInputRef}
        style={[
          styles.notesInput,
          {
            color: theme.text,
            borderColor: theme.border,
            backgroundColor: theme.background,
          },
        ]}
        placeholder="Add your notes about condition, origin, where you bought it, etc."
        placeholderTextColor={theme.muted}
        multiline
        value={notes}
        onChangeText={onChangeNotes}
        onFocus={onFocus}
        textAlignVertical="top"
        blurOnSubmit={false}
        accessibilityLabel="Item notes"
      />
    </View>
  );
});

const styles = StyleSheet.create({
  notesBlock: {
    marginTop: 16,
  },
  notesHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  label: {
    fontSize: text.md,
  },
  notesDoneBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: radius.xs,
  },
  notesDoneBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  notesInput: {
    marginTop: 8,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: text.md,
    lineHeight: 18,
    minHeight: 100,
    maxHeight: 220,
  },
});
