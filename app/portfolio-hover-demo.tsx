import React, { useMemo, useState } from 'react';
import { ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { Stack } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import PortfolioHoverChart, {
  type PortfolioPoint,
  type HoverPoint,
} from '@/components/PortfolioHoverChart';

type RangeKey = '1D' | '7D' | '30D';

type RangeDef = {
  key: RangeKey;
  label: string;
  days: number;
};

const RANGES: RangeDef[] = [
  { key: '1D', label: '1D', days: 1 },
  { key: '7D', label: '7D', days: 7 },
  { key: '30D', label: '30D', days: 30 },
];

function generateDemoPoints(days: number): PortfolioPoint[] {
  const now = Date.now();
  const totalPoints = Math.max(days * 8, 24); // 8 points/day or at least 24
  const points: PortfolioPoint[] = [];
  let current = 20000;

  for (let i = totalPoints - 1; i >= 0; i--) {
    const t =
      now - ((days * 24 * 60 * 60 * 1000) / totalPoints) * i;
    // Random walk for demo
    const delta = (Math.random() - 0.5) * (days > 7 ? 300 : 150);
    current = Math.max(5000, current + delta);
    points.push({ t, value: current });
  }

  return points;
}

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

function formatShortDate(ts: number): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '';
  try {
    return new Intl.DateTimeFormat('de-DE', {
      day: '2-digit',
      month: '2-digit',
    }).format(d);
  } catch {
    return d.toISOString().slice(5, 10);
  }
}

export default function PortfolioHoverDemoScreen() {
  const { colors, spacing, radii } = useAppTheme();
  const [rangeKey, setRangeKey] = useState<RangeKey>('7D');
  const [hoverPoint, setHoverPoint] = useState<HoverPoint | null>(
    null,
  );

  const rangeDef = useMemo(
    () => RANGES.find((r) => r.key === rangeKey) ?? RANGES[1],
    [rangeKey],
  );

  const points = useMemo(
    () => generateDemoPoints(rangeDef.days),
    [rangeDef],
  );

  const latestValue =
    points.length > 0 ? points[points.length - 1].value : 0;

  const displayValue =
    hoverPoint?.value ?? latestValue;

  const displayLabel = hoverPoint
    ? formatShortDate(hoverPoint.t)
    : `Last ${rangeDef.label}`;

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Portfolio hover demo',
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
            Robinhood-style hover chart
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
              marginBottom: spacing.md,
            }}
          >
            Demo view showing how the portfolio graph can react to touch,
            updating the value and date as you drag across the chart.
          </Text>

          {/* Value header that reacts to hover */}
          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'flex-end',
              marginBottom: spacing.sm,
            }}
          >
            <View>
              <Text
                style={{
                  fontSize: 24,
                  fontWeight: '700',
                  color: colors.text,
                }}
              >
                {formatCurrency(displayValue)}
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginTop: 2,
                }}
              >
                {displayLabel}
              </Text>
            </View>
          </View>

          {/* Range buttons */}
          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              marginBottom: spacing.sm,
            }}
          >
            {RANGES.map((range) => {
              const active = range.key === rangeKey;
              return (
                <TouchableOpacity
                  key={range.key}
                  onPress={() => setRangeKey(range.key)}
                  style={{
                    flex: 1,
                    marginHorizontal:
                      range.key === '7D' ? spacing.xs : 0,
                    paddingVertical: 6,
                    borderRadius: 999,
                    alignItems: 'center',
                    backgroundColor: active
                      ? colors.primary
                      : colors.surface,
                  }}
                >
                  <Text
                    style={{
                      fontSize: 12,
                      fontWeight: '600',
                      color: active
                        ? colors.onPrimary
                        : colors.text,
                    }}
                  >
                    {range.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* The hover chart */}
          <PortfolioHoverChart
            points={points}
            onPointChange={setHoverPoint}
          />
        </View>

        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 14,
              fontWeight: '600',
              color: colors.text,
              marginBottom: spacing.xs,
            }}
          >
            How to use this in your real Portfolio tab
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            This screen is a safe demo. Once you&apos;re happy with the
            interaction, we can wire the same chart component into your main
            Portfolio screen using your real valuation history data instead of
            demo points.
          </Text>
        </View>
      </ScrollView>
    </>
  );
}
