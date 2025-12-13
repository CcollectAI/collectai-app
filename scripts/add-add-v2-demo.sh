#!/usr/bin/env bash
set -euo pipefail

# --- 1) Add app/add-v2-demo.tsx (Add hub) ---

FILE1="app/add-v2-demo.tsx"
cp "$FILE1" "$FILE1.bak-$(date +%s)" 2>/dev/null || true

cat > "$FILE1" <<'TS'
import React from 'react';
import {
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Stack, Link } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';

export default function AddV2DemoScreen() {
  const { colors, spacing, radii } = useAppTheme();

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Add item (v2 demo)',
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
            Add to your collection
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            This is the intake hub for new items. Scan for authenticity,
            search the catalog, or add manually when needed.
          </Text>
        </View>

        {/* Three primary actions */}
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            gap: spacing.sm,
          }}
        >
          {/* Scan */}
          <Link href="/add/scan-result-demo" asChild>
            <TouchableOpacity
              activeOpacity={0.9}
              style={{
                flex: 1,
                borderRadius: radii.lg,
                padding: spacing.md,
                backgroundColor: colors.card,
              }}
            >
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '700',
                  color: colors.text,
                  marginBottom: 4,
                }}
              >
                Scan item
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                }}
              >
                Use camera to scan a slab, booster, box or figure and run
                authenticity checks.
              </Text>
            </TouchableOpacity>
          </Link>

          {/* Search */}
          <TouchableOpacity
            activeOpacity={0.9}
            style={{
              flex: 1,
              borderRadius: radii.lg,
              padding: spacing.md,
              backgroundColor: colors.card,
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '700',
                color: colors.text,
                marginBottom: 4,
              }}
            >
              Search catalog
            </Text>
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
              }}
            >
              Look up cards, sets and figures from the catalog and link them
              to your collection.
            </Text>
          </TouchableOpacity>
        </View>

        {/* Manual add (full-width) */}
        <TouchableOpacity
          activeOpacity={0.9}
          style={{
            borderRadius: radii.lg,
            padding: spacing.md,
            backgroundColor: colors.card,
          }}
        >
          <Text
            style={{
              fontSize: 14,
              fontWeight: '700',
              color: colors.text,
              marginBottom: 4,
            }}
          >
            Add manually
          </Text>
          <Text
            style={{
              fontSize: 12,
              color: colors.mutedText,
            }}
          >
            For edge cases: gifts, bequests or items not yet in the catalog.
          </Text>
        </TouchableOpacity>

        {/* Recent additions section (demo) */}
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
            Recent additions (demo)
          </Text>

          {[
            {
              name: 'PSA 9 Lugia Neo Genesis',
              status: 'Verified',
            },
            {
              name: 'HG Gundam – limited edition kit',
              status: 'Pending',
            },
            {
              name: 'Funko Pop – convention exclusive',
              status: 'Flagged',
            },
          ].map((row) => (
            <View
              key={row.name}
              style={{
                paddingVertical: spacing.xs,
                flexDirection: 'row',
                justifyContent: 'space-between',
              }}
            >
              <Text
                style={{
                  fontSize: 13,
                  color: colors.text,
                }}
                numberOfLines={1}
              >
                {row.name}
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color:
                    row.status === 'Verified'
                      ? colors.success ?? '#16a34a'
                      : row.status === 'Flagged'
                      ? colors.error ?? '#B00020'
                      : colors.mutedText,
                }}
              >
                {row.status}
              </Text>
            </View>
          ))}

          <Text
            style={{
              fontSize: 12,
              color: colors.mutedText,
              marginTop: spacing.sm,
            }}
          >
            Later this will show your latest real additions including authenticity
            state and estimated value.
          </Text>
        </View>
      </ScrollView>
    </>
  );
}
TS

# --- 2) Add app/add/scan-result-demo.tsx (scan result UX) ---

mkdir -p app/add
FILE2="app/add/scan-result-demo.tsx"
cp "$FILE2" "$FILE2.bak-$(date +%s)" 2>/dev/null || true

cat > "$FILE2" <<'TS'
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

export default function ScanResultDemoScreen() {
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
TS

echo "Created Add v2 demo screens: app/add-v2-demo.tsx and app/add/scan-result-demo.tsx."
