import React, { memo } from 'react';
import { Text, View, ViewStyle } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

export type ThemedItemCardProps = {
  title: string;
  subtitle?: string;
  valueLabel?: string;      // e.g. "€1.240"
  deltaLabel?: string;      // e.g. "+12.4%"
  deltaPositive?: boolean | null;
  badgeLabel?: string;      // e.g. "Pokémon", "Gunpla", "Slab"
  onPress?: () => void;
  style?: ViewStyle;
};

const ThemedItemCardInner: React.FC<ThemedItemCardProps> = ({
  title,
  subtitle,
  valueLabel,
  deltaLabel,
  deltaPositive,
  badgeLabel,
  onPress,
  style,
}) => {
  const { colors, spacing, radius } = useAppTheme();

  const positive = deltaPositive == null ? null : deltaPositive;
  const deltaColor =
    positive == null
      ? colors.muted
      : positive
      ? colors.success ?? '#16a34a'
      : colors.danger ?? '#B00020';

  const content = (
    <View
      style={[
        {
          borderRadius: 6, // square-ish corners per your preference
          borderWidth: 1,
          borderColor: colors.border,
          backgroundColor: colors.card,
          paddingHorizontal: spacing.md,
          paddingVertical: spacing.sm,
        },
        style,
      ]}
    >
      {/* Top row: title + value */}
      <View
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: spacing.xs,
        }}
      >
        <View style={{ flex: 1, paddingRight: spacing.sm }}>
          <Text
            style={{
              fontSize: 15,
              fontWeight: '700',
              color: colors.text,
            }}
            numberOfLines={1}
          >
            {title}
          </Text>
          {subtitle ? (
            <Text
              style={{
                fontSize: 12,
                color: colors.muted,
                marginTop: 2,
              }}
              numberOfLines={1}
            >
              {subtitle}
            </Text>
          ) : null}
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          {valueLabel ? (
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.text,
              }}
              numberOfLines={1}
            >
              {valueLabel}
            </Text>
          ) : null}
          {deltaLabel ? (
            <Text
              style={{
                fontSize: 12,
                color: deltaColor,
                marginTop: 2,
              }}
              numberOfLines={1}
            >
              {deltaLabel}
            </Text>
          ) : null}
        </View>
      </View>

      {/* Bottom row: badge / meta */}
      <View
        style={{
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: spacing.xs,
        }}
      >
        {badgeLabel ? (
          <View
            style={{
              paddingHorizontal: spacing.sm,
              paddingVertical: 4,
              borderRadius: radius.xl,
              backgroundColor: colors.card,
            }}
          >
            <Text
              style={{
                fontSize: 11,
                fontWeight: '600',
                color: colors.muted,
              }}
              numberOfLines={1}
            >
              {badgeLabel}
            </Text>
          </View>
        ) : (
          <View />
        )}
      </View>
    </View>
  );

  if (onPress) {
    return (
      <AnimatedPressable
        onPress={onPress}
      >
        {content}
      </AnimatedPressable>
    );
  }

  return content;
};

export const ThemedItemCard = memo(ThemedItemCardInner);
export default ThemedItemCard;
