/**
 * ItemNotesEditor — Editable notes block for item detail screen.
 */

import React, { useRef, useCallback, useState, useEffect } from 'react';
import { View, Text, TextInput, Pressable, Keyboard, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { radius, text, fontWeight } from '@/theme/tokens';

interface ItemNotesEditorProps {
  notes: string;
  onChangeNotes: (text: string) => void;
  onSaveNotes: () => void;
  keyboardVisible: boolean;
  /**
   * Called on focus with this block's measured position **in window
   * coordinates**, once the keyboard frame has settled. Window coords, not an
   * `onLayout` y: this block is nested inside the detail card, so a layout y is
   * card-relative and useless for scrolling the parent ScrollView.
   */
  onFocus: (rect: { y: number; height: number }) => void;
}

/** ms to wait for the keyboard frame before measuring — matches the iOS
 *  keyboard show animation (~250ms) with a little slack. */
const KEYBOARD_SETTLE_MS = 300;

export const ItemNotesEditor = React.memo(function ItemNotesEditor({
  notes,
  onChangeNotes,
  onSaveNotes,
  keyboardVisible,
  onFocus,
}: ItemNotesEditorProps) {
  const { colors: theme } = useAppTheme();
  const notesInputRef = useRef<TextInput | null>(null);
  const blockRef = useRef<View | null>(null);
  const measureTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track last-saved text so the Save button can disable when there's
  // nothing to save. Pre-fix 2026-04-19: button was keyboardVisible-gated,
  // which never fires on web → user had no way to save their notes.
  const [lastSaved, setLastSaved] = useState(notes);

  // Resync baseline whenever a fresh notes value flows in from props (e.g.
  // after the server round-trip completes and the parent state updates).
  useEffect(() => {
    setLastSaved(notes);
    // Only resync when notes changes from the outside, not while user is
    // typing. We intentionally depend on `notes` only — React's concurrent
    // mode still gives us the post-save value eventually.

  }, []);

  const hasChanges = notes !== lastSaved;

  // Report where this block actually sits on screen so the parent can scroll
  // it clear of the keyboard. Measuring AFTER the keyboard has settled means
  // the rect already accounts for whatever the KeyboardAvoidingView did.
  const handleFocus = useCallback(() => {
    if (measureTimer.current) clearTimeout(measureTimer.current);
    measureTimer.current = setTimeout(() => {
      blockRef.current?.measureInWindow((_x, y, _w, height) => {
        if (typeof y === 'number' && typeof height === 'number' && height > 0) {
          onFocus({ y, height });
        }
      });
    }, KEYBOARD_SETTLE_MS);
  }, [onFocus]);

  useEffect(() => () => {
    if (measureTimer.current) clearTimeout(measureTimer.current);
  }, []);

  const handleSave = useCallback(() => {
    onSaveNotes();
    setLastSaved(notes);
    Keyboard.dismiss();
  }, [onSaveNotes, notes]);

  return (
    <View
      ref={blockRef}
      // Android collapses layout-only Views out of the native hierarchy, and a
      // collapsed view measures as 0 — which would silently disable the
      // scroll-into-view. Keep it in the tree.
      collapsable={false}
      style={styles.notesBlock}
    >
      <View style={styles.notesHeaderRow}>
        <Text style={[styles.label, { color: theme.muted }]}>
          Notes
        </Text>
        {keyboardVisible && hasChanges && (
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
        onFocus={handleFocus}
        textAlignVertical="top"
        blurOnSubmit={false}
        accessibilityLabel="Item notes"
      />

      {/* Always-visible Save button below the textarea. Works on web
          (no keyboard events), disabled when there's nothing to save. */}
      <Pressable
        onPress={handleSave}
        disabled={!hasChanges}
        style={[
          styles.primarySaveBtn,
          {
            backgroundColor: hasChanges ? theme.accent : theme.border + '60',
            opacity: hasChanges ? 1 : 0.7,
          },
        ]}
        accessibilityRole="button"
        accessibilityLabel={hasChanges ? 'Save notes' : 'No changes to save'}
        accessibilityState={{ disabled: !hasChanges }}
      >
        <Text
          style={[
            styles.primarySaveBtnText,
            { color: hasChanges ? theme.accentText : theme.muted },
          ]}
        >
          {hasChanges ? 'Save notes' : 'Saved'}
        </Text>
      </Pressable>
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
  primarySaveBtn: {
    marginTop: 10,
    paddingVertical: 10,
    borderRadius: radius.md,
    alignItems: 'center',
  },
  primarySaveBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
});
