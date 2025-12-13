import React from 'react';
import { TouchableOpacity, Text, ViewStyle, TextStyle } from 'react-native';
import { useRouter } from 'expo-router';

type CategoryPillProps = {
  id?: string | null;
  label?: string | null;
  style?: ViewStyle;
  textStyle?: TextStyle;
};

/**
 * Small pill that navigates to /categories/[categoryId]
 * when tapped. Does NOT depend on your custom theme to avoid crashes.
 */
export const CategoryPill: React.FC<CategoryPillProps> = ({
  id,
  label,
  style,
  textStyle,
}) => {
  const router = useRouter();

  if (!id && !label) {
    return null;
  }

  const handlePress = () => {
    if (!id) return;
    router.push(`/categories/${encodeURIComponent(id)}`);
  };

  return (
    <TouchableOpacity
      onPress={handlePress}
      activeOpacity={0.85}
      style={[
        {
          paddingHorizontal: 10,
          paddingVertical: 5,
          borderRadius: 999,
          backgroundColor: '#0ea5e9', // Tiffany-ish blue
          alignSelf: 'flex-start',
        },
        style,
      ]}
    >
      <Text
        style={[
          {
            fontSize: 11,
            fontWeight: '600',
            color: '#ffffff',
          },
          textStyle,
        ]}
        numberOfLines={1}
      >
        {label ?? id}
      </Text>
    </TouchableOpacity>
  );
};

export default CategoryPill;
