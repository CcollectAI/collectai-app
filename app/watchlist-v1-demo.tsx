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

export default function WatchlistV1DemoScreen() {
  const { colors, spacing, radii } = useAppTheme();

  const items = [
    {
      id: '1',
      title: 'PSA 10 Charizard VMAX',
      subtitle: 'Pokémon · Modern · Slab',
      value: 12400,
      plPct: 0.142,
      badge: 'Pokémon',
      alert: 'Alert at €13.500',
    },
    {
      id: '2',
      title: 'Lugia Neo Genesis (raw NM)',
      subtitle: 'Pokémon · Vintage',
      value: 2800,
      plPct: -0.018,
      badge: 'Pokémon',
      alert: 'No alert set',
    },
    {
      id: '3',
      title: 'HG Gundam – P-Bandai kit',
      subtitle: 'Gunpla · Unbuilt',
      value: 260,
      plPct: 0.032,
      badge: 'Gunpla',
      alert: 'Alert at €300',
    },
  ];

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Watchlist (v1 demo)',
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
            Watchlist
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            Items you&apos;re tracking as an investor. Some may be owned, some
            not — they all show up here for price moves and alerts.
          </Text>
        </View>

        {/* Items */}
        <View style={{ gap: spacing.sm }}>
          {items.map((item) => {
            const pct = item.plPct ?? 0;
            const pctValue = Math.round(pct * 1000) / 10; // 0.142 -> 14.2
            const deltaLabel =
              pct === 0
                ? '0.0%'
                : `${pctValue > 0 ? '+' : ''}${pctValue.toFixed(1)}%`;

            return (
              <View key={item.id}>
                <ThemedItemCard
                  title={item.title}
                  subtitle={item.subtitle}
                  valueLabel={formatCurrency(item.value)}
                  deltaLabel={deltaLabel}
                  deltaPositive={
                    pctValue > 0 ? true : pctValue < 0 ? false : null
                  }
                  badgeLabel={item.badge}
                />
                <Text
                  style={{
                    fontSize: 11,
                    color: colors.mutedText,
                    marginTop: 4,
                    marginLeft: 4,
                  }}
                  numberOfLines={1}
                >
                  {item.alert}
                </Text>
              </View>
            );
          })}
        </View>
      </ScrollView>
    </>
  );
}
