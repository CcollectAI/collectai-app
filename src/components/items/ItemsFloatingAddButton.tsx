/**
 * ItemsFloatingAddButton — Floating action button that appears on scroll.
 */

import React from 'react';
import { Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { useTranslation } from 'react-i18next';

interface ItemsFloatingAddButtonProps {
  onPress: () => void;
}

export const ItemsFloatingAddButton = React.memo(function ItemsFloatingAddButton({
  onPress,
}: ItemsFloatingAddButtonProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <AnimatedPressable
      style={[styles.floatingAddBtn, { backgroundColor: colors.accent }]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={t('items.add_new_a11y', { defaultValue: 'Add new item' })}
    >
      <Ionicons name="add" size={22} color={colors.accentText}/>
      <Text style={styles.floatingAddText}>Add Item</Text>
    </AnimatedPressable>
  );
});

const styles = StyleSheet.create({
  floatingAddBtn: {
    position: 'absolute',
    bottom: 24,
    left: 24,
    right: 24,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 6,
  },
  floatingAddText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
});
