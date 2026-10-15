/**
 * The Android half of `showActionSheet` (2026-10-15).
 *
 * Android's `Alert.alert` renders AT MOST THREE buttons and silently drops the
 * rest — including the Cancel the helper appends. Walked as a seller: the
 * carrier picker offered PostNL, DPD and GLS of the server's ten European
 * carriers, with no Cancel. The same helper backs the sell form's Category
 * (50+ options: only the first three were choosable), Condition, item-detail
 * Category / Set / Condition, `SelectField` and the photo-label picker.
 *
 * One host, mounted once in app/_layout.tsx, renders every Android sheet as a
 * scrollable list. `showActionSheet` keeps its signature, so no caller changed.
 */
import React, { useEffect, useState } from 'react';
import { Modal, View, Text, ScrollView, StyleSheet, TouchableOpacity } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';

export type ActionSheetRequest = {
  title: string;
  options: string[];
  onSelect: (index: number) => void;
  onCancel?: () => void;
};

type Listener = (req: ActionSheetRequest) => void;
let listener: Listener | null = null;

/** True when a host is mounted to show the request. */
export function presentActionSheet(req: ActionSheetRequest): boolean {
  if (!listener) return false;
  listener(req);
  return true;
}

export function ActionSheetHost() {
  const { colors } = useAppTheme();
  const [req, setReq] = useState<ActionSheetRequest | null>(null);

  useEffect(() => {
    listener = setReq;
    return () => { if (listener === setReq) listener = null; };
  }, []);

  const cancel = () => { const r = req; setReq(null); r?.onCancel?.(); };
  const pick = (i: number) => { const r = req; setReq(null); r?.onSelect(i); };

  return (
    <Modal visible={!!req} transparent animationType="fade" onRequestClose={cancel}>
      <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={cancel} accessibilityRole="button" accessibilityLabel="Cancel">
        <TouchableOpacity activeOpacity={1} style={[styles.sheet, { backgroundColor: colors.card }]}>
          <Text style={[styles.title, { color: colors.text }]}>{req?.title}</Text>
          <ScrollView style={styles.list}>
            {(req?.options ?? []).map((label, i) => (
              <TouchableOpacity
                key={`${i}-${label}`}
                onPress={() => pick(i)}
                style={[styles.row, { borderTopColor: colors.border }]}
                accessibilityRole="button"
                accessibilityLabel={label}
              >
                <Text style={[styles.rowText, { color: colors.text }]}>{label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
          <TouchableOpacity onPress={cancel} style={[styles.row, styles.cancelRow, { borderTopColor: colors.border }]} accessibilityRole="button">
            <Text style={[styles.rowText, styles.cancelText, { color: colors.accent }]}>Cancel</Text>
          </TouchableOpacity>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', paddingHorizontal: 24 },
  sheet: { borderRadius: 16, maxHeight: '80%', overflow: 'hidden' },
  title: { fontSize: 17, fontWeight: '600', paddingHorizontal: 20, paddingTop: 18, paddingBottom: 12 },
  list: { flexGrow: 0 },
  row: { minHeight: 48, justifyContent: 'center', paddingHorizontal: 20, borderTopWidth: StyleSheet.hairlineWidth },
  rowText: { fontSize: 15 },
  cancelRow: { alignItems: 'flex-end' },
  cancelText: { fontWeight: '600' },
});
