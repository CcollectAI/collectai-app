#!/usr/bin/env bash
set -euo pipefail

# 1) Create themed item card component
mkdir -p src/components
cp src/components/ThemedItemCard.tsx src/components/ThemedItemCard.tsx.bak-$(date +%s) 2>/dev/null || true

cat > src/components/ThemedItemCard.tsx <<'TS'
import React from 'react';
import { Text, View, TouchableOpacity, ViewStyle } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';

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

export const ThemedItemCard: React.FC<ThemedItemCardProps> = ({
  title,
  subtitle,
  valueLabel,
  deltaLabel,
  deltaPositive,
  badgeLabel,
  onPress,
  style,
}) => {
  const { colors, spacing, radii } = useAppTheme();

  const positive = deltaPositive == null ? null : deltaPositive;
  const deltaColor =
    positive == null
      ? colors.mutedText
      : positive
      ? colors.success ?? '#16a34a'
      : colors.error ?? '#B00020';

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
                color: colors.mutedText,
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
              borderRadius: radii.full,
              backgroundColor: colors.surface,
            }}
          >
            <Text
              style={{
                fontSize: 11,
                fontWeight: '600',
                color: colors.mutedText,
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
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={onPress}
      >
        {content}
      </TouchableOpacity>
    );
  }

  return content;
};

export default ThemedItemCard;
TS

# 2) Create demo screen to preview the card
cp app/item-card-demo.tsx app/item-card-demo.tsx.bak-$(date +%s) 2>/dev/null || true

cat > app/item-card-demo.tsx <<'TS'
import React from 'react';
import { ScrollView, Text, View } from 'react-native';
import { Stack } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import ThemedItemCard from '@/components/ThemedItemCard';

function formatCurrency(value: number): string {
  try {
    return new Intl.NumberFormat('de-DE', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${value.toFixed(0)} EUR`;
  }
}

export default function ItemCardDemoScreen() {
  const { colors, spacing } = useAppTheme();

  const sampleItems = [
    {
      id: '1',
      title: 'PSA 10 Charizard VMAX',
      subtitle: 'Pokémon · Modern · Slab',
      value: 12400,
      delta: '+14,2%',
      positive: true,
      badge: 'Pokémon',
    },
    {
      id: '2',
      title: 'HG Gundam – custom panel line',
      subtitle: 'Gunpla · Custom build',
      value: 240,
      delta: '+3,5%',
      positive: true,
      badge: 'Gunpla',
    },
    {
      id: '3',
      title: 'Warhammer squad – primed',
      subtitle: 'Warhammer · In progress',
      value: 180,
      delta: '-1,2%',
      positive: false,
      badge: 'Warhammer',
    },
  ];

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Item card demo',
        }}
      />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{
          paddingTop: spacing.lg * 1.5,
          paddingHorizontal: spacing.lg,
          paddingBottom: spacing.xl * 2,
          gap: spacing.md,
        }}
      >
        <View
          style={{
            padding: spacing.md,
            backgroundColor: colors.card,
          }}
        >
          <Text
            style={{
              fontSize: 18,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.xs,
            }}
          >
            Themed item card
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            This is a demo screen showing the investor-style item card that
            we can plug into your Items and Portfolio lists. White cards,
            square corners, Tiffany-blue accent colours, P/L colouring.
          </Text>
        </View>

        <View
          style={{
            gap: spacing.sm,
          }}
        >
          {sampleItems.map((item) => (
            <ThemedItemCard
              key={item.id}
              title={item.title}
              subtitle={item.subtitle}
              valueLabel={formatCurrency(item.value)}
              deltaLabel={item.delta}
              deltaPositive={item.positive}
              badgeLabel={item.badge}
            />
          ))}
        </View>
      </ScrollView>
    </>
  );
}
TS

echo "ThemedItemCard component and demo screen created."
