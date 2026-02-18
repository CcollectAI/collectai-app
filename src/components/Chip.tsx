import React, { memo, useCallback } from 'react';
import { Pressable, Text } from 'react-native';
import { theme } from '@/theme';
import { fireHaptic, HapticIntent } from '@/haptics';

function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
}) {
  const handlePress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    onPress?.();
  }, [onPress]);

  return (
    <Pressable
      onPress={handlePress}
      accessibilityRole="button"
      accessibilityLabel={`${label}${selected ? ', selected' : ''}`}
      style={{
        borderWidth: 1,
        borderColor: selected ? theme.colors.navy : theme.colors.border,
        backgroundColor: selected ? '#FFFFFF' : theme.colors.card,
        paddingVertical: theme.spacing.xs,
        paddingHorizontal: theme.spacing.md,
      }}
    >
      <Text style={{ color: selected ? theme.colors.navy : theme.colors.subtext, fontWeight: selected ? '700' : '500' }}>
        {label}
      </Text>
    </Pressable>
  );
}

export default memo(Chip);
