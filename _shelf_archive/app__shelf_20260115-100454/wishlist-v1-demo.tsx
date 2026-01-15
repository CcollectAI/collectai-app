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

export default function WishlistV1DemoScreen() {
  const { colors, spacing, radii } = useAppTheme();

  const items = [
    {
      id: 'w1',
      title: 'Trophy Pikachu',
      subtitle: 'Pokémon · Grail',
      estValue: 65000,
      priority: 1,
      note: 'Lifetime grail, trade-only.',
    },
    {
      id: 'w2',
      title: 'SDCC Exclusive Funko Pop',
      subtitle: 'Funko · Convention',
      estValue: 420,
      priority: 2,
      note: 'Would buy at the right price.',
    },
    {
      id: 'w3',
      title: 'Warhammer army starter',
      subtitle: 'Warhammer · Army project',
      estValue: 320,
      priority: 3,
      note: 'For future campaign.',
    },
  ];

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Wishlist (v1 demo)',
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
        {/* Intro */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
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
            Wishlist
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            Items you don&apos;t own yet, but want to track as future pickups,
            grails or gift ideas.
          </Text>
        </View>

        {/* Items */}
        <View style={{ gap: spacing.sm }}>
          {items.map((item) => (
            <View key={item.id}>
              <ThemedItemCard
                title={item.title}
                subtitle={item.subtitle}
                valueLabel={formatCurrency(item.estValue)}
                // Wishlist has no P/L yet, so we skip delta labels
                deltaLabel={undefined}
                deltaPositive={null}
                badgeLabel={`Priority ${item.priority}`}
              />
              <Text
                style={{
                  fontSize: 11,
                  color: colors.mutedText,
                  marginTop: 4,
                  marginLeft: 4,
                }}
                numberOfLines={2}
              >
                {item.note}
              </Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </>
  );
}
