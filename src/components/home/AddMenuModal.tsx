/**
 * AddMenuModal — Bottom-sheet menu for adding items (QuickScan, Barcode, Manual).
 */

import React from 'react';
import { View, Text, StyleSheet, Modal, TouchableOpacity, Platform } from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

interface AddMenuModalProps {
  visible: boolean;
  onClose: () => void;
}

const MENU_ITEMS = [
  { route: '/quickscan', icon: 'camera-outline' as const, title: 'QuickScan AI', subtitle: 'Snap a photo, get instant valuation' },
  { route: '/barcode-scan', icon: 'barcode-outline' as const, title: 'Scan Barcode', subtitle: 'ISBN, EAN, or UPC' },
  { route: '/add-manual', icon: 'create-outline' as const, title: 'Add Manually', subtitle: 'Enter item details' },
] as const;

export const AddMenuModal = React.memo(function AddMenuModal({ visible, onClose }: AddMenuModalProps) {
  const { colors } = useAppTheme();

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <TouchableOpacity
        activeOpacity={1}
        onPress={onClose}
        style={styles.overlay}
        accessibilityRole="button"
        accessibilityLabel="Close add item menu"
      >
        <View
          style={[styles.sheet, { backgroundColor: colors.card, borderColor: colors.border }]}
          accessibilityViewIsModal={true}
          accessibilityRole="menu"
          accessibilityLabel="Add item menu"
        >
          <View style={[styles.handle, { backgroundColor: colors.muted }]} />
          {MENU_ITEMS.map((item, idx) => (
            <React.Fragment key={item.route}>
              {idx > 0 && <View style={[styles.divider, { backgroundColor: colors.border }]} />}
              <TouchableOpacity
                onPress={() => { onClose(); router.push(item.route); }}
                style={styles.menuItem}
                accessibilityRole="button"
                accessibilityLabel={item.title}
              >
                <View style={[styles.iconCircle, { backgroundColor: colors.accent + '15' }]}>
                  <Ionicons name={item.icon} size={20} color={colors.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.title, { color: colors.text }]}>{item.title}</Text>
                  <Text style={[styles.subtitle, { color: colors.muted }]}>{item.subtitle}</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.muted} />
              </TouchableOpacity>
            </React.Fragment>
          ))}
        </View>
      </TouchableOpacity>
    </Modal>
  );
});

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  sheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    borderBottomWidth: 0,
    paddingBottom: Platform.OS === 'ios' ? 34 : 20,
    paddingTop: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 10,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 16,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  subtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  divider: {
    height: 1,
    marginHorizontal: 20,
  },
});
