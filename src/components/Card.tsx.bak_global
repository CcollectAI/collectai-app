import { View, type ViewProps } from 'react-native';
import { theme } from '@/theme';
export default function Card(props: ViewProps) {
  return (
    <View
      {...props}
      style={[
        { backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.md },
        props.style,
      ]}
    />
  );
}
