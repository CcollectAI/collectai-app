import React, { useMemo } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { Stack, Link } from 'expo-router';

import { useAppTheme } from '@/hooks/useAppTheme';
import { summarizePortfolioHealth } from '@/analytics/derivedPortfolioMetrics';
import {
  buildPortfolioDailySeries,
  type RawItemValuationRow,
} from '@/analytics/valuationHistory';

export default function NewFeatureSmoketestScreen() {
  const { colors, spacing, radii } = useAppTheme();

  // Dummy valuation history rows to exercise buildPortfolioDailySeries
  const dummyRows: RawItemValuationRow[] = useMemo(
    () => [
      {
        id: 'v1',
        user_id: 'u1',
        item_id: 'item1',
        as_of: '2025-12-01T10:00:00Z',
        estimated_value: 100,
        currency: 'EUR',
        source: 'dummy',
        confidence: 0.8,
        created_at: '2025-12-01T10:00:00Z',
      },
      {
        id: 'v2',
        user_id: 'u1',
        item_id: 'item1',
        as_of: '2025-12-02T10:00:00Z',
        estimated_value: 120,
        currency: 'EUR',
        source: 'dummy',
        confidence: 0.8,
        created_at: '2025-12-02T10:00:00Z',
      },
      {
        id: 'v3',
        user_id: 'u1',
        item_id: 'item2',
        as_of: '2025-12-02T11:00:00Z',
        estimated_value: 80,
        currency: 'EUR',
        source: 'dummy',
        confidence: 0.6,
        created_at: '2025-12-02T11:00:00Z',
      },
    ],
    [],
  );

  const portfolioSeries = buildPortfolioDailySeries(dummyRows);

  // Minimal synthetic snapshot for summarizePortfolioHealth
  const snapshot: any = useMemo(
    () => ({
      items: [
        {
          id: 'item1',
          name: 'Demo Charizard',
          category: 'Pokémon',
          currentValue: 120,
          purchasePrice: 90,
          change1dPct: 0.2,
        },
        {
          id: 'item2',
          name: 'Gunpla MG Barbatos',
          category: 'Gunpla',
          currentValue: 80,
          purchasePrice: 100,
          change1dPct: -0.1,
        },
      ],
      allocations: [
        { category: 'Pokémon', totalValue: 120 },
        { category: 'Gunpla', totalValue: 80 },
      ],
      pl: {
        currentValue: 200,
        deltaAbs: 10,
        deltaPct: 0.05,
      },
    }),
    [],
  );

  const health = summarizePortfolioHealth(snapshot);

  const totalValue = health?.totalValue ?? 0;
  const totalCostBasis = health?.totalCostBasis ?? 0;
  const unrealizedPl = health?.unrealizedPl ?? 0;
  const unrealizedPlPct = health?.unrealizedPlPct ?? 0;

  function fmtCurrency(n: number): string {
    try {
      return new Intl.NumberFormat('de-DE', {
        style: 'currency',
        currency: 'EUR',
        maximumFractionDigits: 0,
      }).format(n);
    } catch {
      return `${n.toFixed(0)} EUR`;
    }
  }

  function fmtPct(n: number | null | undefined): string {
    if (n == null || !Number.isFinite(n)) return '—';
    const pct = Math.round(n * 1000) / 10;
    return `${pct.toFixed(1)}%`;
  }

  return (
    <>
      <Stack.Screen
        options={{
          headerTitle: 'New Feature Smoketest',
        }}
      />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentContainerStyle={{
          padding: spacing.lg,
          paddingBottom: spacing.xl * 2,
          gap: spacing.md,
        }}
      >
        <View>
          <Text
            style={{
              fontSize: 18,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.xs,
            }}
          >
            Internal sanity check
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
            }}
          >
            This screen only uses dummy data. It proves that valuation
            history helpers, portfolio health metrics, and routing for
            the authenticity check screen all compile and render.
          </Text>
        </View>

        {/* Portfolio health summary */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 15,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            Portfolio health (dummy data)
          </Text>
          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
            }}
          >
            <View>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.mutedText,
                  marginBottom: 2,
                }}
              >
                Market value
              </Text>
              <Text
                style={{
                  fontSize: 16,
                  fontWeight: '700',
                  color: colors.text,
                }}
              >
                {fmtCurrency(totalValue)}
              </Text>
            </View>
            <View style={{ alignItems: 'flex-end' }}>
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
                  fontSize: 16,
                  fontWeight: '600',
                  color: colors.text,
                }}
              >
                {totalCostBasis > 0
                  ? fmtCurrency(totalCostBasis)
                  : '—'}
              </Text>
            </View>
          </View>
          <View
            style={{
              marginTop: spacing.sm,
              paddingTop: spacing.sm,
              borderTopWidth: 1,
              borderTopColor: colors.border,
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
                  unrealizedPl > 0
                    ? colors.success ?? '#16a34a'
                    : unrealizedPl < 0
                    ? colors.error ?? '#B00020'
                    : colors.text,
              }}
            >
              {fmtCurrency(unrealizedPl)} ({fmtPct(unrealizedPlPct)})
            </Text>
          </View>
        </View>

        {/* Valuation history / timeseries check */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
          }}
        >
          <Text
            style={{
              fontSize: 15,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            Valuation history helper
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
              marginBottom: spacing.xs,
            }}
          >
            Built series from {dummyRows.length} raw history rows:
          </Text>
          {portfolioSeries.map((p) => (
            <View
              key={p.date}
              style={{
                flexDirection: 'row',
                justifyContent: 'space-between',
                marginBottom: 2,
              }}
            >
              <Text
                style={{
                  fontSize: 12,
                  color: colors.text,
                }}
              >
                {p.date}
              </Text>
              <Text
                style={{
                  fontSize: 12,
                  color: colors.text,
                }}
              >
                {fmtCurrency(p.totalValue)}
              </Text>
            </View>
          ))}
          {!portfolioSeries.length && (
            <Text
              style={{
                fontSize: 12,
                color: colors.mutedText,
              }}
            >
              No series points produced. Something is wrong with
              valuationHistory helpers.
            </Text>
          )}
        </View>

        {/* Route check for authenticity screen */}
        <View
          style={{
            borderRadius: radii.lg,
            backgroundColor: colors.card,
            padding: spacing.md,
            marginBottom: spacing.lg,
          }}
        >
          <Text
            style={{
              fontSize: 15,
              fontWeight: '700',
              color: colors.text,
              marginBottom: spacing.sm,
            }}
          >
            Authenticity check route
          </Text>
          <Text
            style={{
              fontSize: 13,
              color: colors.mutedText,
              marginBottom: spacing.sm,
            }}
          >
            Tap below to navigate to the in-store authenticity check
            screen (if the file app/add-auth-check.tsx exists and
            compiled correctly).
          </Text>
          <Link
            href="/add-auth-check"
            style={{
              borderRadius: radii.full,
              paddingVertical: spacing.sm,
              paddingHorizontal: spacing.md,
              backgroundColor: colors.primary,
              alignSelf: 'flex-start',
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: colors.onPrimary,
              }}
            >
              Open authenticity check
            </Text>
          </Link>
        </View>
      </ScrollView>
    </>
  );
}
