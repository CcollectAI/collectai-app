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
