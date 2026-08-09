/**
 * BottomSheetModal Component
 * Reusable modal wrapper that provides the common bottom-sheet chrome:
 * Modal + KeyboardAvoidingView + overlay + SafeAreaView + header (close, title, optional action).
 *
 * Supports two presentation modes:
 *  - "bottomSheet" (default): transparent overlay with rounded container pinned to bottom.
 *  - "pageSheet": native page-sheet style (iOS) with full-height container.
 */

import React, { useEffect, useRef, type ReactNode } from 'react';
import {
  Modal,
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Pressable,
} from 'react-native';
// react-native's own SafeAreaView is iOS-only — it renders as a plain View on
// Android, so content sits under the status bar and gesture nav. Always take it
// from react-native-safe-area-context (see docs/ui-playbook.md).
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { fireHaptic, HapticIntent } from '@/haptics';

interface BottomSheetModalProps {
  visible: boolean;
  onClose: () => void;
  title: string;
  /** Optional right-side header action */
  headerRight?: ReactNode;
  children: ReactNode;
  colors: {
    background: string;
    text: string;
    border: string;
    [key: string]: unknown;
  };
  /**
   * "bottomSheet" (default) — transparent overlay, rounded top, pinned to bottom.
   * "pageSheet" — native iOS page sheet, full-height container.
   */
  mode?: 'bottomSheet' | 'pageSheet';
  /** Override maxHeight for bottomSheet mode (default '90%'). Ignored in pageSheet mode. */
  maxHeight?: `${number}%` | number;
}

export function BottomSheetModal({
  visible,
  onClose,
  title,
  headerRight,
  children,
  colors,
  mode = 'bottomSheet',
  maxHeight = '90%',
}: BottomSheetModalProps) {
  // Fire light haptic when modal opens
  const prevVisible = useRef(visible);
  useEffect(() => {
    if (visible && !prevVisible.current) {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    }
    prevVisible.current = visible;
  }, [visible]);

  if (mode === 'pageSheet') {
    return (
      <Modal
        visible={visible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={onClose}
      >
        <SafeAreaView style={[styles.pageContainer, { backgroundColor: colors.background }]} accessibilityViewIsModal={true}>
          <View style={[styles.header, { borderBottomColor: colors.border }]}>
            <Pressable onPress={onClose} hitSlop={8} style={styles.pageCloseBtn} accessibilityRole="button" accessibilityLabel={`Close ${title}`}>
              <Ionicons name="close" size={24} color={colors.text} />
            </Pressable>
            <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
              {title}
            </Text>
            {headerRight ?? <View style={styles.spacer} />}
          </View>
          {children}
        </SafeAreaView>
      </Modal>
    );
  }

  // Default: bottomSheet mode
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}
      >
        <View style={styles.overlay}>
          <SafeAreaView
            style={[styles.container, { backgroundColor: colors.background, maxHeight }]}
            accessibilityViewIsModal={true}
          >
            <View style={[styles.header, { borderBottomColor: colors.border }]}>
              <Pressable onPress={onClose} hitSlop={8} accessibilityRole="button" accessibilityLabel={`Close ${title}`}>
                <Ionicons name="close" size={24} color={colors.text} />
              </Pressable>
              <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
                {title}
              </Text>
              {headerRight ?? <View style={styles.spacer} />}
            </View>
            {children}
          </SafeAreaView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  container: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    overflow: 'hidden',
  },
  pageContainer: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
    marginHorizontal: 8,
  },
  spacer: { width: 24 },
  pageCloseBtn: {
    padding: 4,
  },
});

export default BottomSheetModal;
