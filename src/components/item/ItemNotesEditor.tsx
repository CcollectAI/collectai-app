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
  onFocus,
}: ItemNotesEditorProps) {
  const { colors: theme } = useAppTheme();
  const notesInputRef = useRef<TextInput | null>(null);
  const blockRef = useRef<View | null>(null);
  const measureTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track last-saved text so the Save button can disable when there's
  // nothing to save. The button used to be keyboardVisible-gated, which never
  // fires on web, so a web user had no way to save at all. `keyboardVisible`
  // is no longer a prop at all now that the duplicate button is gone —
  // leaving it would have implied a behaviour that no longer exists.
  const [lastSaved, setLastSaved] = useState(notes);

  // Resync the baseline when a fresh notes value arrives from props — the
  // server round-trip lands AFTER mount, so the value this component was
  // constructed with is almost always the empty string.
  //
  // ⚠️ The dependency array used to be `[]` while the comment beside it said
  // "we intentionally depend on `notes` only". The comment described the
  // intent; the code ran once and never resynced. Consequence: `lastSaved`
  // stayed '' forever, so `hasChanges` was permanently true and the Save
  // button sat enabled on an item whose notes were untouched — inviting a
  // save that writes back exactly what is already stored.
  //
  // Depending on `notes` does NOT fight typing: onChangeNotes updates the
  // parent, the new value flows back down, and lastSaved follows it — which
  // is why hasChanges is computed against the last SAVED value written by
  // handleSave, not by this effect.
  const hydratedRef = useRef(false);
  useEffect(() => {
    // Only adopt while the user has not started editing, so a resync can never
    // overwrite a baseline the member's own save just set.
    if (hydratedRef.current) return;
    if (notes) {
      setLastSaved(notes);
      hydratedRef.current = true;
    }
  }, [notes]);

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
      {/* ONE save button, not two. There used to be a keyboard-gated "Save"
          here as well as the primary one below the textarea — two controls for
          one action, and the header one never appeared on web (no keyboard
          events). The primary button is kept because it works everywhere and
          shows STATE ("Save notes" vs "Saved"), which the header one did not.
          The keyboard fix in app/item/[id].tsx scrolls the whole notes block
          clear of the keyboard, so the remaining button stays reachable while
          typing. */}
      <View style={styles.notesHeaderRow}>
        <Text style={[styles.label, { color: theme.muted }]}>
          Notes
        </Text>
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
  // SMALLER, 2026-08-26. It opened at 100pt of empty box and could grow to
  // 220 — the largest single element on a screen whose subject is the item's
  // VALUE, for a field most items never fill in. Notes are "my own record" in
  // the screen's hierarchy of need (playbook, "The money was in the middle"),
  // i.e. reference, and reference does not get the biggest box.
  //
  // 64 is three lines at `lineHeight: 18` plus the 8pt vertical padding, so a
  // short note still fits without scrolling and an empty one stops reserving a
  // hole. 132 is six lines — `multiline` keeps growing to that, and the field
  // scrolls internally beyond it, so nothing is truncated or unreachable.
  //
  // The LABEL is deliberately unchanged at `text.md`: every other label on this
  // screen (ItemDetailsCard.label) is text.md, and shrinking this one alone
  // would break the row rhythm it currently matches. "Smaller" here is the box,
  // not the heading.
  notesInput: {
    marginTop: 8,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: text.md,
    lineHeight: 18,
    minHeight: 64,
    maxHeight: 132,
  },
  // The BOX shrank; the control did not. At `paddingVertical: 8` around a
  // text.md line this button measures ~30pt, and at the previous 10 it was
  // ~34 — both under the 44pt minimum touch target, on a full-width primary
  // action. Shrinking the section is not a licence to shrink its control, so
  // the height is now stated rather than left to fall out of the padding.
  primarySaveBtn: {
    marginTop: 8,
    paddingVertical: 10,
    minHeight: 44,
    justifyContent: 'center',
    borderRadius: radius.md,
    alignItems: 'center',
  },
  primarySaveBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
});
