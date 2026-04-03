import React, { memo } from 'react';
import { Text, ViewStyle, TextStyle } from 'react-native';
import { useRouter } from 'expo-router';
import { AnimatedPressable } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { CATEGORY_VISUAL, type CategoryId } from '@/data/categories';

type CategoryPillProps = {
  id?: string | null;
  label?: string | null;
  style?: ViewStyle;
  textStyle?: TextStyle;
};

/**
 * Small pill that navigates to /categories/[categoryId] when tapped.
 * Uses category-specific accent color when available, falls back to theme accent.
 */
const CategoryPillInner: React.FC<CategoryPillProps> = ({
  id,
  label,
  style,
  textStyle,
}) => {
  const router = useRouter();
  const { colors } = useAppTheme();

  if (!id && !label) {
    return null;
  }

  const visual = id ? CATEGORY_VISUAL[id as CategoryId] : undefined;
  const pillColor = visual?.accentColor ?? colors.accent;

  const handlePress = () => {
    if (!id) return;
    router.push(`/categories/${encodeURIComponent(id)}`);
  };

  return (
    <AnimatedPressable
      onPress={handlePress}
      accessibilityRole="button"
      accessibilityLabel={`View ${label ?? id} category`}
      style={[
        {
          paddingHorizontal: 10,
          paddingVertical: 5,
          borderRadius: 999,
          backgroundColor: pillColor,
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
            color: '#ffffff', // Button text on brand background
          },
          textStyle,
        ]}
        numberOfLines={1}
      >
        {label ?? id}
      </Text>
    </AnimatedPressable>
  );
};

export const CategoryPill = memo(CategoryPillInner);
export default CategoryPill;
