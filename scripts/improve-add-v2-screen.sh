#!/usr/bin/env bash
set -euo pipefail

FILE="app/add-v2-demo.tsx"

if [ ! -f "$FILE" ]; then
  echo "Add v2 demo file not found at $FILE"
  exit 1
fi

cp "$FILE" "$FILE.bak.improved-$(date +%s)" || true

cat > "$FILE" <<'TS'
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
          headerTitle: 'Add to collection',
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
            Add a new item
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            Start by scanning a slab, searching the catalog or using a manual
            form. Later this pipe will feed directly into your portfolio,
            watchlist and authenticity checks.
          </Text>
        </View>

        {/* Primary actions: Scan + Search */}
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            gap: spacing.sm,
          }}
        >
          {/* Scan item */}
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
                Use your camera to scan a slab, booster, box or figure and run
                authenticity + value checks on the image.
              </Text>
            </TouchableOpacity>
          </Link>

          {/* Search catalog */}
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
              Look up known cards, sets and figures, then link them to your
              collection without scanning.
            </Text>
          </TouchableOpacity>
        </View>

        {/* Manual add (full width) */}
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
            Use this for edge cases: gifts, bequests, or items not yet covered
            by the catalog or scanner. Later this will open a full detail form.
          </Text>
        </TouchableOpacity>

        {/* How scanning works / anti-fraud explainer */}
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
            Authenticity & anti-fraud
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
              marginBottom: spacing.sm,
            }}
          >
            In the next phase this flow will compare your scan against known
            patterns: label layout, artwork alignment, print quality, holo
            pattern and common counterfeit tells for each category.
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            For now the scan result screen is a demo of what you&apos;ll see:
            a detected item, authenticity score, risk level and value range,
            with one-tap actions to add to collection, watchlist or wishlist.
          </Text>
        </View>

        {/* Recent additions (demo) */}
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
              name: 'HG Gundam – limited kit',
              status: 'Pending',
            },
            {
              name: 'Funko Pop – con exclusive',
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
            Later this list will show your actual latest additions with live
            authenticity status and estimated value.
          </Text>
        </View>
      </ScrollView>
    </>
  );
}
TS

echo "Improved Add v2 screen written to app/add-v2-demo.tsx (backup created)."
