import React, { useMemo, useState } from 'react';
import {
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { Stack, Link } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import PortfolioHoverChart, {
  type PortfolioPoint,
  type HoverPoint,
} from '@/components/PortfolioHoverChart';

type RangeKey = '1D' | '7D' | '30D' | 'ALL';

type RangeDef = {
  key: RangeKey;
  label: string;
  days: number | 'all';
};

const RANGES: RangeDef[] = [
  { key: '1D', label: '1D', days: 1 },
  { key: '7D', label: '7D', days: 7 },
  { key: '30D', label: '30D', days: 30 },
  { key: 'ALL', label: 'ALL', days: 'all' },
];

function generateDemoSeries(days: number | 'all'): PortfolioPoint[] {
  const now = Date.now();
  const spanDays = days === 'all' ? 365 : days;
  const totalPoints = Math.max(spanDays * 4, 40);
  const points: PortfolioPoint[] = [];
  let current = 20000;

  for (let i = totalPoints - 1; i >= 0; i--) {
    const t =
      now -
      ((spanDays * 24 * 60 * 60 * 1000) / totalPoints) * i;
    const delta =
      (Math.random() - 0.5) *
      (spanDays > 30 ? 600 : spanDays > 7 ? 400 : 250);
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

export default function PortfolioV2DemoScreen() {
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
    () => generateDemoSeries(rangeDef.days),
    [rangeDef],
  );

  const latestValue =
    points.length > 0 ? points[points.length - 1].value : 0;
  const displayValue =
    hoverPoint?.value ?? latestValue;

  const displayLabel = hoverPoint
    ? formatShortDate(hoverPoint.t)
    : rangeKey === 'ALL'
    ? 'Last 12 months'
    : `Last ${rangeDef.label}`;

  // Demo summary numbers for now
  const demoCostBasis = 15500;
  const demoPL = latestValue - demoCostBasis;
  const demoPLPct =
    demoCostBasis > 0
      ? (demoPL / demoCostBasis) * 100
      : 0;

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'Portfolio (v2 demo)',
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
        {/* Top card: value + hover-aware label */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 12,
              fontWeight: '600',
              color: colors.mutedText,
              textTransform: 'uppercase',
              marginBottom: 2,
            }}
          >
            Collection value
          </Text>
          <Text
            style={{
              fontSize: 28,
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

        {/* Chart card: hover chart + non-bleeding range buttons */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          {/* Range buttons row */}
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
                      range.key === '7D' || range.key === '30D'
                        ? spacing.xs
                        : 0,
                    paddingVertical: 6,
                    borderRadius: 999,
                    alignItems: 'center',
                    backgroundColor: active
                      ? colors.primary
                      : colors.surface,
                  }}
                  activeOpacity={0.85}
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

          {/* Hover chart */}
          <PortfolioHoverChart
            points={points}
            onPointChange={setHoverPoint}
          />
        </View>

        {/* Snapshot + View analytics */}
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
            Snapshot
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
                Cost basis
              </Text>
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color: colors.text,
                }}
              >
                {formatCurrency(demoCostBasis)}
              </Text>
            </View>
            <View
              style={{
                flex: 1,
                alignItems: 'flex-end',
                paddingLeft: spacing.sm,
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
              <Text
                style={{
                  fontSize: 14,
                  fontWeight: '600',
                  color:
                    demoPL > 0
                      ? colors.success ?? '#16a34a'
                      : demoPL < 0
                      ? colors.error ?? '#B00020'
                      : colors.text,
                }}
              >
                {formatCurrency(demoPL)} (
                {demoPLPct > 0 ? '+' : ''}
                {demoPLPct.toFixed(1)}%)
              </Text>
            </View>
          </View>

          <View
            style={{
              marginTop: spacing.sm,
              flexDirection: 'row',
              justifyContent: 'flex-start',
            }}
          >
            <Link href="/analytics" asChild>
              <TouchableOpacity
                activeOpacity={0.85}
                style={{
                  paddingHorizontal: spacing.md,
                  paddingVertical: 8,
                  borderRadius: 999,
                  backgroundColor: colors.primary,
                }}
              >
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: '600',
                    color: colors.onPrimary,
                  }}
                >
                  View analytics
                </Text>
              </TouchableOpacity>
            </Link>
          </View>
        </View>

        {/* Info card */}
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
            What this demo shows
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            This screen is a high-fidelity portfolio home layout using demo
            data. The hover chart and range buttons are wired; later we&apos;ll
            swap the demo series for your real valuation history and plug this
            layout into the main Portfolio tab.
          </Text>
        </View>
      
        <View style={{ marginTop: spacing.sm }}>
          <Link href="/calendar-v1-demo">
            <Text>Events &amp; drops calendar (demo)</Text>
          </Link>
        </View>

    </ScrollView>
    </>
  );
}
