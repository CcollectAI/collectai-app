import { View, ViewProps } from 'react-native';
import { theme } from '@/theme';

export default function Card({ style, ...props }: ViewProps) {
  return (
    <View
      style={[{
        backgroundColor: theme.colors.card,
        padding: theme.spacing.lg,
        borderColor: theme.colors.border,
        borderWidth: 1,
      }, style]}
      {...props}
    />
  );
}
