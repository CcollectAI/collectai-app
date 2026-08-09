/**
 * Sales & tax reporting — what we count about your sales, and what it means.
 *
 * ── The stance this screen encodes ─────────────────────────────────────────
 * Sparrow does NOT do the member's compliance for them. It does not file, does
 * not advise, and deliberately holds no tax identification number, address or
 * bank details — there is no column for any of those anywhere in the schema, and
 * that is a decision, not a gap to fill later. What this screen does is make
 * sure a seller KNOWS the threshold is a legal obligation on marketplaces rather
 * than a Sparrow policy, and can see exactly where they stand against it.
 *
 * That is also why the copy avoids "we'll ask you for details": the terms and
 * the crossing notice used to promise exactly that, with no form behind it and
 * nowhere to put an answer. Kept in step with `app/legal/marketplace-terms.tsx`
 * §6 and the notice text in `_dac7_accrue` — the three say the same thing, and
 * if one changes all three change.
 *
 * ── Reading the numbers ───────────────────────────────────────────────────
 * Thresholds come from the SERVER (`sales_limit` / `gross_eur_limit`), never
 * hardcoded here: they are figures stated in writing in §6, and a client copy
 * would let the screen and the terms drift apart.
 *
 * `current_year: null` means no completed sale has been counted yet, which is a
 * different statement from "0 sales" — the empty state says so in words rather
 * than rendering a row of zeros that looks like data (docs/ui-playbook.md,
 * "Empty ≠ loading", and by the same argument empty ≠ zero).
 *
 * Playbook: SafeAreaView from safe-area-context, AnimatedPressable, theme
 * colours only, `useEnterReveal` wrapper, no iOS-only accessibilityRole.
 */
import React, { useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, Animated, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import ScreenHeader from '@/components/ScreenHeader';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useTabBarInset } from '@/hooks/useTabBarInset';
import { useAsync } from '@/hooks/useAsync';
import { useSettings } from '@/lib/settings';
import { collectorsApi } from '@/api/collectorsApi';
import { formatPrice } from '@/lib/format';
import { radius, text as textToken, fontWeight } from '@/theme/tokens';

function TaxReportingScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const bottomInset = useTabBarInset();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const { data, loading, error, retry } = useAsync(
    async () => collectorsApi.p2pDac7Status(),
    [],
  );

  const openTerms = useCallback(() => {
    router.push('/legal/marketplace-terms');
  }, [router]);

  const year = data?.current_year ?? null;
  // Gross figures are already EUR — the counter converts at accrual time, since
  // the threshold is denominated in EUR and a seller must not be able to sit
  // above the line indefinitely in a weaker currency.
  const eur = (n: number) => formatPrice(n, 'EUR', settings.numberLocale);

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <ScreenHeader title="Sales & tax reporting" />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: bottomInset }]}>
        <Animated.View style={animatedStyle}>

          {loading ? (
            <View style={styles.centered}>
              <ActivityIndicator color={colors.accent} />
            </View>
          ) : (error || !data) ? (
            // A failed read is NOT "you have no sales" — that would tell a seller
            // they are under the line when we simply could not check. `!data` is
            // in the same branch on purpose: a resolved-but-empty response is
            // indistinguishable from a failure for the purposes of what we may
            // truthfully tell the member, and it also narrows `data` for the
            // success branch below.
            <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Couldn&apos;t load your figures</Text>
              <Text style={[styles.body, { color: colors.muted }]}>
                This says nothing about where you stand — we just could not reach the
                server. The thresholds below still apply.
              </Text>
              <AnimatedPressable
                onPress={retry}
                style={[styles.retry, { borderColor: colors.accent }]}
                accessibilityRole="button"
                accessibilityLabel="Try loading your figures again"
              >
                <Text style={[styles.retryText, { color: colors.accent }]}>Try again</Text>
              </AnimatedPressable>
            </View>
          ) : (
            <>
              {/* Where you stand */}
              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {year === null ? (
                  <>
                    <Text style={[styles.cardTitle, { color: colors.text }]}>
                      No completed sales counted yet
                    </Text>
                    <Text style={[styles.body, { color: colors.muted }]}>
                      Counting starts when a trade completes — both you and the buyer
                      confirm the exchange. Nothing is counted while an offer is still
                      open.
                    </Text>
                  </>
                ) : (
                  <>
                    <View style={styles.statusRow}>
                      <Text style={[styles.cardTitle, { color: colors.text }]}>
                        Your {year.year} total
                      </Text>
                      <View
                        style={[
                          styles.pill,
                          year.reportable
                            ? { backgroundColor: colors.warning + '1E' }
                            : { backgroundColor: colors.accent + '1E' },
                        ]}
                      >
                        <Text
                          style={[
                            styles.pillText,
                            { color: year.reportable ? colors.warning : colors.accent },
                          ]}
                        >
                          {year.reportable ? 'Reportable' : 'Not reportable'}
                        </Text>
                      </View>
                    </View>

                    <View style={styles.figures}>
                      <View style={styles.figure}>
                        <Text style={[styles.figureValue, { color: colors.text }]}>
                          {year.sales_count}
                        </Text>
                        <Text style={[styles.figureLabel, { color: colors.muted }]}>
                          of {data.sales_limit} sales
                        </Text>
                      </View>
                      <View style={styles.figure}>
                        <Text style={[styles.figureValue, { color: colors.text }]}>
                          {eur(year.gross_eur)}
                        </Text>
                        <Text style={[styles.figureLabel, { color: colors.muted }]}>
                          of {eur(data.gross_eur_limit)}
                        </Text>
                      </View>
                    </View>

                    <Text style={[styles.body, { color: colors.muted }]}>
                      {year.reportable
                        ? 'You have passed one of the two limits, so a marketplace in our position is required to report sellers like you. We told you when it happened, and we will tell you before anything about you is sent.'
                        : `You are under both limits. ${year.sales_remaining ?? 0} more sale${(year.sales_remaining ?? 0) === 1 ? '' : 's'} or ${eur(year.gross_eur_remaining ?? 0)} more would cross the line.`}
                    </Text>
                  </>
                )}
              </View>

              {/* The rule, stated the same way §6 states it */}
              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Text style={[styles.cardTitle, { color: colors.text }]}>Where the line is</Text>
                <Text style={[styles.body, { color: colors.muted }]}>
                  Most members are never reported. A seller stays excluded while they
                  are under <Text style={{ color: colors.text }}>both</Text> limits in a
                  calendar year: fewer than {data.sales_limit} sales,{' '}
                  <Text style={{ color: colors.text }}>and</Text> no more than{' '}
                  {eur(data.gross_eur_limit)} in total. Passing{' '}
                  <Text style={{ color: colors.text }}>either one</Text> — not both —
                  makes a seller reportable.
                </Text>
              </View>

              {/* The point of the screen: it is required OF US, and yours to handle */}
              <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <Text style={[styles.cardTitle, { color: colors.text }]}>What that means for you</Text>
                <Text style={[styles.body, { color: colors.muted }]}>
                  Reporting above the threshold is a legal requirement on marketplaces,
                  not a Sparrow policy — the EU rules (DAC7) and the equivalent OECD
                  rules adopted by the UK, Canada, Australia, New Zealand, Japan and
                  others work the same way.{'\n\n'}
                  <Text style={{ color: colors.text }}>
                    Your tax position is yours to handle.
                  </Text>{' '}
                  We do not file anything on your behalf, do not give tax advice, and do
                  not hold your tax identification number or bank details. Passing a
                  limit is your signal to look at your own return.
                </Text>
                <AnimatedPressable
                  onPress={openTerms}
                  style={styles.link}
                  accessibilityRole="link"
                  accessibilityLabel="Read section 6 of the marketplace terms"
                >
                  <Text style={[styles.linkText, { color: colors.accent }]}>
                    Marketplace terms, section 6
                  </Text>
                  <Ionicons name="chevron-forward" size={14} color={colors.accent} />
                </AnimatedPressable>
              </View>

              {/* Earlier years, once there are any */}
              {data.years.filter((y) => y.year !== year?.year).length > 0 ? (
                <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
                  <Text style={[styles.cardTitle, { color: colors.text }]}>Earlier years</Text>
                  {data.years
                    .filter((y) => y.year !== year?.year)
                    .map((y) => (
                      <View key={y.year} style={styles.yearRow}>
                        <Text style={[styles.body, { color: colors.text }]}>{y.year}</Text>
                        <Text style={[styles.yearFigures, { color: colors.muted }]}>
                          {y.sales_count} sales · {eur(y.gross_eur)}
                          {y.reportable ? ' · reported' : ''}
                        </Text>
                      </View>
                    ))}
                </View>
              ) : null}
            </>
          )}

          <Text style={[styles.fine, { color: colors.muted }]}>
            Counted per calendar year, in euros, because that is the reporting period
            and the threshold is set in euros. Nothing here is tax advice.
          </Text>
        </Animated.View>
      </ScrollView>
      <QuickNavBar />
    </SafeAreaView>
  );
}

export default function TaxReportingScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Sales & tax reporting">
      <TaxReportingScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  // 16 is the app-wide screen gutter (docs/ui-playbook.md).
  content: { padding: 16, gap: 12 },
  centered: { paddingVertical: 48, alignItems: 'center' },
  card: {
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: 14,
    gap: 10,
    marginBottom: 12,
  },
  cardTitle: { fontSize: textToken.lg, fontWeight: fontWeight.semibold },
  body: { fontSize: textToken.md, lineHeight: 21 },
  statusRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  pill: { paddingHorizontal: 9, paddingVertical: 4, borderRadius: radius.xs },
  pillText: { fontSize: textToken.sm, fontWeight: fontWeight.bold },
  figures: { flexDirection: 'row', gap: 24 },
  figure: { gap: 2 },
  figureValue: { fontSize: textToken.xl, fontWeight: fontWeight.extrabold, letterSpacing: -0.3 },
  figureLabel: { fontSize: textToken.md },
  retry: { alignSelf: 'flex-start', borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 12, paddingVertical: 8 },
  retryText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  link: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  linkText: { fontSize: textToken.md, fontWeight: fontWeight.bold },
  yearRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  yearFigures: { fontSize: textToken.md },
  fine: { fontSize: textToken.sm, lineHeight: 18, marginTop: 4 },
});
