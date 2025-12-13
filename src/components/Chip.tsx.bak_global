import { Pressable, Text } from 'react-native';
import { theme } from '@/theme';

export default function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
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
