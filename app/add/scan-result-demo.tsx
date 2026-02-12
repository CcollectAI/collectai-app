import React from 'react';
import {
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Stack } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';

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

function NotAvailableScreen() {
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ fontSize: 16, color: '#666' }}>Not available</Text>
    </View>
  );
}

function ScanResultDemoScreen() {
  const { colors, spacing, radii } = useAppTheme();

  const demoItem = {
    name: 'PSA 10 Charizard VMAX',
    category: 'Pokémon · Modern · Slab',
    authenticityScore: 0.92,
    risk: 'Low',
    estimatedMin: 11000,
    estimatedMax: 13500,
  };

  const scorePct = Math.round(
    demoItem.authenticityScore * 100,
  );

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Scan result (demo)',
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
        {/* Detected item */}
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
            Detected item
          </Text>
          <Text
            style={{
              fontSize: 15,
              fontWeight: '600',
              color: colors.text,
            }}
          >
            {demoItem.name}
          </Text>
          <Text
            style={{
              fontSize: 12,
              color: colors.mutedText,
              marginTop: 2,
            }}
          >
            {demoItem.category}
          </Text>
        </View>

        {/* Authenticity block */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 16,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.xs,
            }}
          >
            Authenticity
          </Text>

          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: spacing.sm,
            }}
          >
            <View>
              <Text
                style={{
                  fontSize: 24,
                  fontWeight: '700',
                  color:
                    demoItem.risk === 'Low'
                      ? colors.success ?? '#16a34a'
                      : demoItem.risk === 'High'
                      ? colors.error ?? '#B00020'
                      : colors.text,
                }}
              >
                {scorePct}%
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                Likely genuine ({demoItem.risk} risk)
              </Text>
            </View>
          </View>

          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            This is a demo scan result. In the real flow, we&apos;ll show the
            signals used to reach this score: artwork match, label layout,
            holo pattern, print quality and known counterfeit patterns.
          </Text>
        </View>

        {/* Value band */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 16,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            Estimated value range
          </Text>
          <Text
            style={{
              fontSize: 15,
              fontWeight: '600',
              color: colors.text,
            }}
          >
            {formatCurrency(demoItem.estimatedMin)} –{' '}
            {formatCurrency(demoItem.estimatedMax)}
          </Text>
          <Text
            style={{
              fontSize: 12,
              color: colors.mutedText,
              marginTop: 4,
            }}
          >
            Based on recent slab sales and comparable condition.
          </Text>
        </View>

        {/* Actions: collection / watchlist / wishlist */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 16,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            What do you want to do?
          </Text>

          <View
            style={{
              gap: spacing.sm,
            }}
          >
            <TouchableOpacity
              activeOpacity={0.9}
              style={{
                borderRadius: radii.lg,
                padding: spacing.sm,
                backgroundColor: colors.surface,
              }}
              accessibilityRole="button"
              accessibilityLabel="Add to collection"
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.text,
                }}
              >
                Add to collection
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginTop: 2,
                }}
              >
                You own this item. It will appear in your portfolio and P/L.
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.9}
              style={{
                borderRadius: radii.lg,
                padding: spacing.sm,
                backgroundColor: colors.surface,
              }}
              accessibilityRole="button"
              accessibilityLabel="Add to watchlist"
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.text,
                }}
              >
                Add to watchlist
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginTop: 2,
                }}
              >
                Track price movements without marking it as owned.
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              activeOpacity={0.9}
              style={{
                borderRadius: radii.lg,
                padding: spacing.sm,
                backgroundColor: colors.surface,
              }}
              accessibilityRole="button"
              accessibilityLabel="Add to wishlist"
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.text,
                }}
              >
                Add to wishlist
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginTop: 2,
                }}
              >
                Mark this as a grail you want to buy later.
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </>
  );
}

export default __DEV__ ? ScanResultDemoScreen : NotAvailableScreen;
