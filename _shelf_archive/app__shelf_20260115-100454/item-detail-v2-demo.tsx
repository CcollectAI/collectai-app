import React, { useState } from 'react';
import {
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Stack } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';

function formatCurrency(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
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

export default function ItemDetailV2DemoScreen() {
  const { colors, spacing, radii } = useAppTheme();

  // Demo state for toggles
  const [owned, setOwned] = useState(true);
  const [inWatchlist, setInWatchlist] = useState(true);
  const [inWishlist, setInWishlist] = useState(false);

  const demoItem = {
    name: 'PSA 10 Charizard VMAX',
    category: 'Pokémon · Modern · Slab',
    currentValue: 12400,
    purchasePrice: 8200,
    lastValuationAt: '2025-01-12T10:30:00Z',
  };

  const { currentValue, purchasePrice } = demoItem;
  const pl =
    currentValue != null && purchasePrice != null
      ? currentValue - purchasePrice
      : null;
  const plPct =
    pl != null && purchasePrice && purchasePrice > 0
      ? (pl / purchasePrice) * 100
      : null;

  const plColor =
    pl == null
      ? colors.mutedText
      : pl > 0
      ? colors.success ?? '#16a34a'
      : pl < 0
      ? colors.error ?? '#B00020'
      : colors.text;

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Item detail (v2 demo)',
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
        {/* Header: image placeholder + title/category */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <View
            style={{
              flexDirection: 'row',
              gap: spacing.md,
              alignItems: 'center',
            }}
          >
            {/* Image placeholder */}
            <View
              style={{
                width: 64,
                height: 64,
                borderRadius: 8,
                backgroundColor: colors.surface,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Text
                style={{
                  fontSize: 24,
                  fontWeight: '700',
                  color: colors.mutedText,
                }}
              >
                C
              </Text>
            </View>

            <View style={{ flex: 1 }}>
              <Text
                style={{
                  fontSize: 17,
                  fontWeight: '700',
                  color: colors.text,
                }}
                numberOfLines={2}
              >
                {demoItem.name}
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginTop: 2,
                }}
                numberOfLines={1}
              >
                {demoItem.category}
              </Text>

              {/* Ownership/segment pill */}
              <View
                style={{
                  flexDirection: 'row',
                  marginTop: spacing.xs,
                }}
              >
                <View
                  style={{
                    paddingHorizontal: spacing.sm,
                    paddingVertical: 4,
                    borderRadius: radii.full,
                    backgroundColor: colors.surface,
                    marginRight: spacing.xs,
                  }}
                >
                  <Text
                    style={{
                      fontSize: 11,
                      fontWeight: '600',
                      color: colors.mutedText,
                    }}
                  >
                    {owned ? 'Owned' : 'Not owned'}
                  </Text>
                </View>
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
                  >
                    High-value grail
                  </Text>
                </View>
              </View>
            </View>
          </View>
        </View>

        {/* Value + P/L card */}
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
            Value & P/L
          </Text>

          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              marginBottom: spacing.sm,
            }}
          >
            <View style={{ flex: 1, paddingRight: spacing.sm }}>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginBottom: 2,
                }}
              >
                Current value
              </Text>
              <Text
                style={{
                  fontSize: 18,
                  fontWeight: '700',
                  color: colors.text,
                }}
              >
                {formatCurrency(currentValue)}
              </Text>
              <Text
                style={{
                  fontSize: 11,
                  color: colors.mutedText,
                  marginTop: 2,
                }}
              >
                Last valuation: 12.01 (demo)
              </Text>
            </View>

            <View style={{ flex: 1 }}>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginBottom: 2,
                }}
              >
                Purchase price
              </Text>
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.text,
                }}
              >
                {purchasePrice != null
                  ? formatCurrency(purchasePrice)
                  : 'Not set'}
              </Text>

              <View
                style={{
                  marginTop: spacing.xs,
                }}
              >
                <Text
                  style={{
                    fontSize: 12,
                    color: colors.mutedText,
                    marginBottom: 2,
                  }}
                >
                  Unrealized P/L
                </Text>
                {pl != null && plPct != null ? (
                  <Text
                    style={{
                      fontSize: 14,
                      fontWeight: '600',
                      color: plColor,
                    }}
                  >
                    {formatCurrency(pl)} (
                    {plPct > 0 ? '+' : ''}
                    {plPct.toFixed(1)}%)
                  </Text>
                ) : (
                  <Text
                    style={{
                      fontSize: 12,
                      color: colors.mutedText,
                    }}
                  >
                    P/L unavailable — set purchase price to enable.
                  </Text>
                )}
              </View>
            </View>
          </View>
        </View>

        {/* Actions: cost basis, alerts, lists */}
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
            Actions
          </Text>

          {/* Set purchase price */}
          <TouchableOpacity
            activeOpacity={0.9}
            style={{
              paddingVertical: spacing.sm,
              borderBottomWidth: 1,
              borderBottomColor: colors.border,
            }}
            onPress={() => {
              // Later this opens an edit cost-basis dialog / screen
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.text,
              }}
            >
              Set / edit purchase price
            </Text>
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
                marginTop: 2,
              }}
            >
              Cost basis is used to calculate P/L for this item and your
              portfolio.
            </Text>
          </TouchableOpacity>

          {/* Set alert */}
          <TouchableOpacity
            activeOpacity={0.9}
            style={{
              paddingVertical: spacing.sm,
              borderBottomWidth: 1,
              borderBottomColor: colors.border,
            }}
            onPress={() => {
              // Later: open alert configuration (target price / %)
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.text,
              }}
            >
              Set price alert
            </Text>
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
                marginTop: 2,
              }}
            >
              Get notified when this item crosses a target price or % change.
            </Text>
          </TouchableOpacity>

          {/* Watchlist toggle */}
          <TouchableOpacity
            activeOpacity={0.9}
            style={{
              paddingVertical: spacing.sm,
              borderBottomWidth: 1,
              borderBottomColor: colors.border,
            }}
            onPress={() => {
              setInWatchlist((prev) => !prev);
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.text,
              }}
            >
              {inWatchlist
                ? 'Remove from watchlist'
                : 'Add to watchlist'}
            </Text>
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
                marginTop: 2,
              }}
            >
              Track this item&apos;s price as an investor, whether or not you
              own it.
            </Text>
          </TouchableOpacity>

          {/* Wishlist toggle */}
          <TouchableOpacity
            activeOpacity={0.9}
            style={{
              paddingVertical: spacing.sm,
            }}
            onPress={() => {
              setInWishlist((prev) => !prev);
              if (!owned && !inWishlist) {
                // Demo: if user wishes it, mark as not owned
                setOwned(false);
              }
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.text,
              }}
            >
              {inWishlist
                ? 'Remove from wishlist'
                : 'Add to wishlist'}
            </Text>
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
                marginTop: 2,
              }}
            >
              Wishlist is for items you don&apos;t own but want to track as
              grails or gift ideas.
            </Text>
          </TouchableOpacity>
        </View>

        {/* Build/paint projects section (demo copy only) */}
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
            Build & paint projects
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
              marginBottom: spacing.sm,
            }}
          >
            For buildable categories like Gunpla, Warhammer or model kits,
            you&apos;ll be able to track this as a long-running project with
            progress updates and time spent.
          </Text>
          <TouchableOpacity
            activeOpacity={0.9}
            style={{
              alignSelf: 'flex-start',
              paddingHorizontal: spacing.md,
              paddingVertical: 8,
              borderRadius: radii.full,
              backgroundColor: colors.surface,
            }}
            onPress={() => {
              // Later: create or open linked project for this item
            }}
          >
            <Text
              style={{
                fontSize: 13,
                fontWeight: '600',
                color: colors.text,
              }}
            >
              Track as project (demo)
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </>
  );
}
