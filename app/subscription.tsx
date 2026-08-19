/**
 * Subscription screen — shows current plan and upgrade options.
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
  ScrollView,
  Linking,
  Platform,
  Animated,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable, useEnterReveal } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useAuthContext } from '@/providers/useAuthContext';
import { logger } from '@/lib/logger';
import {
  getOfferings,
  purchasePackage,
  restorePurchases,
  planFromCustomerInfo,
  purchasesStatus,
} from '@/lib/purchases';
import { useBillingLimits } from '@/hooks/useBillingLimits';
import type { PurchasesPackage } from 'react-native-purchases';
import { useToast } from '@/components/Toast';
import { track } from '@/analytics/track';

// Removed static SUCCESS/WARNING — use colors.success / colors.warning from theme

interface PlanCardProps {
  name: string;
  price: string;
  features: string[];
  current: boolean;
  recommended?: boolean;
  onSelect?: () => void;
  loading?: boolean;
  colors: ReturnType<typeof useAppTheme>['colors'];
}

function PlanCard({ name, price, features, current, recommended, onSelect, loading, colors }: PlanCardProps) {
  const { t } = useTranslation();
  return (
    <View
      style={[
        styles.planCard,
        { borderColor: colors.border },
        current && { borderColor: colors.accent, borderWidth: 2, backgroundColor: colors.accent + '08' },
        recommended && { borderColor: colors.brand.dark, borderWidth: 2 },
      ]}
      accessible={true}
      accessibilityRole="summary"
      accessibilityLabel={`${name} plan, ${price}${current ? ', current plan' : ''}${recommended ? ', recommended' : ''}`}
    >
      {recommended && (
        <View style={[styles.recommendedBadge, { backgroundColor: colors.brand.dark }]}>
          <Text style={[styles.recommendedText, { color: colors.accentText }]}>RECOMMENDED</Text>
        </View>
      )}
      <Text style={[styles.planName, { color: colors.text }]}>{name}</Text>
      <Text style={[styles.planPrice, { color: colors.muted }]}>{price}</Text>
      <View style={styles.featureList} accessibilityRole="list" accessibilityLabel={t('subscription.features_a11y')}>
        {features.map((f) => (
          <View key={f} style={styles.featureRow} accessibilityLabel={f}>
            <Ionicons name="checkmark-circle" size={18} color={current ? colors.brand.dark : colors.muted} />
            <Text style={[styles.featureText, { color: colors.text }]}>{f}</Text>
          </View>
        ))}
      </View>
      {current ? (
        <View style={[styles.currentBadge, { backgroundColor: colors.success + '15' }]}>
          <Text style={[styles.currentBadgeText, { color: colors.success }]}>{t('subscription.current_plan')}</Text>
        </View>
      ) : (
        <AnimatedPressable
          style={[
            styles.selectBtn,
            { backgroundColor: colors.brand.darker },
            recommended && { backgroundColor: colors.brand.dark },
          ]}
          onPress={onSelect}
          disabled={loading}
          accessibilityRole="button"
          accessibilityLabel={`Select ${name} plan`}
        >
          {loading ? (
            <ActivityIndicator size="small" color={colors.accentText} />
          ) : (
            <Text style={[styles.selectBtnText, { color: colors.accentText }]}>
              {name === 'Free' ? 'Downgrade' : 'Upgrade'}
            </Text>
          )}
        </AnimatedPressable>
      )}
    </View>
  );
}

type Offerings = Awaited<ReturnType<typeof getOfferings>>;

function SubscriptionScreen() {
  const { t } = useTranslation();
  const { settings } = useSettings();
  // Enter reveal, matching every other screen in the app (see the
  // Component Checklist in docs/ui-playbook.md). This screen was the
  // only one that appeared with no transition. Gated on
  // settings.animationsEnabled exactly as analytics.tsx does, so the
  // reduce-motion preference still wins.
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const { plan: currentPlan, loading: planLoading, isBetaUnlocked } = useBillingLimits();

  const [offerings, setOfferings] = useState<Offerings>(null);
  const [loading, setLoading] = useState(true);
  const [iapUnavailable, setIapUnavailable] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [upgrading, setUpgrading] = useState<'monthly' | 'yearly' | null>(null);
  const [restoring, setRestoring] = useState(false);
  const { profile } = useAuthContext();

  function fetchOfferings() {
    setLoading(true);
    setFetchError(null);
    setIapUnavailable(false);
    // Two very different failures rendered the SAME "coming soon" screen, so
    // "the paywall is empty" could not be triaged without a rebuild:
    //   no-key      → RevenueCat never configured (our bug: env var missing)
    //   no-offering → RC configured fine, but StoreKit returned no products,
    //                 so the SDK drops the offering. That is Apple's side:
    //                 Paid Applications Agreement not active, subscriptions
    //                 still in Missing Metadata, or running on the Simulator
    //                 (StoreKit serves no products there at all).
    // logger.error, not warn — info/warn are stripped in release builds, which
    // is exactly where this matters (docs/ui-playbook.md).
    const status = purchasesStatus();
    if (status !== 'ready') {
      // Was a single `reason=no-key` line for both of these. On 2026-08-17 the
      // screen was reported broken, that line was believed, and the hunt went
      // to EAS env vars and the Apple dashboards — when the truth was that the
      // app under test was a DEV-CLIENT build, whose eas.json `development`
      // profile carries no RevenueCat key at all. The paywall cannot work on
      // one, and no amount of App Store Connect configuration changes that.
      logger.error(
        status === 'configure-failed'
          ? '[subscription] iapUnavailable reason=configure-failed — a RevenueCat ' +
              'key IS present in this build but Purchases.configure() threw. Ours to ' +
              'fix; nothing to do with Apple.'
          : '[subscription] iapUnavailable reason=no-key — no RevenueCat key in this ' +
              'build. EXPECTED on a dev-client/simulator build (the eas.json ' +
              '"development" profile sets no EXPO_PUBLIC_REVENUECAT_IOS_KEY). On a ' +
              'store/TestFlight build it means the key is missing from the production ' +
              'EAS environment.',
      );
      setIapUnavailable(true);
      setLoading(false);
      return;
    }
    getOfferings()
      .then((data) => {
        if (!data?.current) {
          logger.error(
            '[subscription] iapUnavailable reason=no-offering — RevenueCat is ' +
              'configured but returned no current offering. StoreKit gave the SDK ' +
              'no products: check the Paid Applications Agreement is Active and ' +
              'that sparrow_pro_monthly/sparrow_pro_yearly are Ready to Submit. ' +
              'Always empty on the iOS Simulator.',
          );
          setIapUnavailable(true);
        } else {
          setOfferings(data);
        }
      })
      .catch((err: unknown) => {
        setFetchError(err instanceof Error ? err.message : 'Could not load plans.');
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    track({ name: 'subscription_screen_viewed' });
    fetchOfferings();
  }, []);

  const monthlyPkg: PurchasesPackage | undefined = offerings?.current?.monthly ?? undefined;
  const yearlyPkg: PurchasesPackage | undefined =
    offerings?.current?.annual ?? offerings?.current?.threeMonth ?? undefined;

  async function handlePurchase(period: 'monthly' | 'yearly') {
    const pkg = period === 'monthly' ? monthlyPkg : yearlyPkg;
    if (!pkg) {
      showToast({
        message: 'This plan is not available right now. Please try again later.',
        type: 'error',
      });
      return;
    }
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setUpgrading(period);
    try {
      const result = await purchasePackage(pkg);
      if (result.ok) {
        const newPlan = planFromCustomerInfo(result.customerInfo);
        track({
          name: 'subscription_upgrade_completed',
          properties: {
            plan: newPlan,
            period,
            // Credits the creator this user signed up under. The revenue join
            // still happens server-side off the RevenueCat webhook — this is
            // for funnel visibility in PostHog, not for payout maths.
            ...(profile?.referred_by_code ? { affiliate_code: profile.referred_by_code } : {}),
          },
        });
        showToast({ message: 'Welcome to Pro!', type: 'success' });
      } else if (result.cancelled) {
        // User cancelled — silent.
      } else {
        showToast({ message: result.message, type: 'error' });
      }
    } finally {
      setUpgrading(null);
    }
  }

  async function handleRestore() {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setRestoring(true);
    try {
      const info = await restorePurchases();
      if (!info) {
        showToast({ message: 'Restore unavailable. Please try again.', type: 'error' });
        return;
      }
      const restoredPlan = planFromCustomerInfo(info);
      if (restoredPlan === 'free') {
        showToast({ message: 'No previous purchases found.', type: 'info' });
      } else {
        showToast({ message: `Restored — you're on ${restoredPlan}.`, type: 'success' });
        track({ name: 'subscription_restored', properties: { plan: restoredPlan } });
      }
    } finally {
      setRestoring(false);
    }
  }

  function handleManage() {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const url =
      Platform.OS === 'ios'
        ? 'https://apps.apple.com/account/subscriptions'
        : 'https://play.google.com/store/account/subscriptions';
    Linking.openURL(url).catch(() => {
      showToast({ message: 'Could not open subscriptions page.', type: 'error' });
    });
  }

  const isPaid = currentPlan !== 'free';
  const screenLoading = loading || planLoading;

  /* Kept in step with FORCED_LIMITS.pro / DEFAULT_LIMITS in
     src/hooks/useBillingLimits.ts — this list is what the customer is paying
     for, so anything here has to be a limit the app actually enforces.
     Two real Pro benefits were missing (unlimited watchlist, unlimited daily
     alerts), so the page under-sold the tier, and "Priority support" was a
     support promise nothing implements — a written promise to a paying user is
     a spec, not copy. */
  const PRO_FEATURES = [
    '10 purchase mandates',
    'Unlimited watchlist',
    'Unlimited deal alerts',
    'Deal discovery',
    'Condition grading',
    'Set completion tracker',
    'Advanced analytics',
    'Dossier PDF export',
    'No ads',
  ];

  const FREE_FEATURES = [
    '25 watchlist items',
    '1 deal alert a day',
    '1 price alert a week',
    'Basic valuation',
    'Community access',
  ];

  // Named the three causes apart so the __DEV__ hint below can say which one
  // this is. Computed at render rather than stored, because `fetchOfferings`
  // can flip the status on a retry.
  const devDiagnostic =
    purchasesStatus() === 'no-key'
      ? 'DEV: no RevenueCat key in this build — the "development" eas.json profile ' +
        'sets none, so the paywall cannot load here. Build the "store" profile and ' +
        'test on a device via TestFlight.'
      : purchasesStatus() === 'configure-failed'
        ? 'DEV: a key is present but Purchases.configure() threw. This one is ours — ' +
          'see the [purchases] configure failed line in the log.'
        : fetchError
          ? `DEV: getOfferings() threw — ${fetchError}`
          : 'DEV: RevenueCat is configured, but StoreKit returned no products. Always ' +
            'true on the Simulator. On a device, check the Paid Applications Agreement ' +
            'is Active and both subscriptions are out of Missing Metadata.';

  const monthlyPriceLabel = monthlyPkg?.product.priceString ?? `${settings.currency} 4.99/mo`;
  const yearlyPriceLabel = yearlyPkg?.product.priceString ?? `${settings.currency} 39.99/yr`;

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Animated.View
        style={[{ flex: 1 }, settings.animationsEnabled ? animatedStyle : undefined]}
      >
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[styles.title, { color: colors.text }]}>Subscription</Text>

        {screenLoading ? (
          <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
        ) : isBetaUnlocked ? (
          <View style={styles.comingSoonSection}>
            <View style={[styles.comingSoonIcon, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="sparkles-outline" size={40} color={colors.accent} />
            </View>
            <Text style={[styles.comingSoonTitle, { color: colors.text }]}>
              You&apos;re in the Sparrow beta
            </Text>
            <Text style={[styles.comingSoonText, { color: colors.muted }]}>
              Every Pro feature is unlocked for free while we&apos;re testing.
              Pricing arrives after the beta — you&apos;ll get a heads-up before
              anything changes.
            </Text>
          </View>
        ) : iapUnavailable || fetchError ? (
          /* This used to say "Coming soon — we're finishing the Pro tier
             setup". That is a pre-launch message on a screen that ships to the
             App Store: an Apple reviewer opening it reads the product as
             unfinished, and a real customer whose plans failed to load once is
             told the feature does not exist yet rather than to try again.
             Both failures behind it (no offering from StoreKit, or a thrown
             fetch) are things a RETRY can resolve, so they share one honest
             state. The specific cause is in the logs, not in the copy — see
             the logger.error calls in fetchOfferings and docs/MONETIZATION.md.
             Restore Purchases renders below this branch, so someone who has
             already paid is never stranded here. */
          <View style={styles.comingSoonSection}>
            <View style={[styles.comingSoonIcon, { backgroundColor: colors.warning + '15' }]}>
              <Ionicons name="cloud-offline-outline" size={40} color={colors.warning} />
            </View>
            <Text style={[styles.comingSoonTitle, { color: colors.text }]}>
              Plans couldn&apos;t load
            </Text>
            <Text style={[styles.comingSoonText, { color: colors.muted }]}>
              We couldn&apos;t reach the App Store for the subscription options.
              Check your connection and try again. Already subscribed? Use
              Restore Purchases below.
            </Text>
            <AnimatedPressable
              onPress={fetchOfferings}
              style={[styles.retryBtn, { backgroundColor: colors.accent }]}
              accessibilityRole="button"
              accessibilityLabel="Try loading the plans again"
            >
              <Text style={[styles.retryBtnText, { color: colors.accentText }]}>
                Try again
              </Text>
            </AnimatedPressable>
            {/* __DEV__ only, so no customer and no App Store reviewer ever sees
                it. "Check your connection and try again" is the right thing to
                tell a customer and the WRONG thing to tell whoever is building
                the app: on a dev-client or Simulator run this screen cannot
                work, and retrying forever is the trap it set. Says which of the
                three causes it is, in the place the person who needs it is
                already looking. */}
            {__DEV__ ? (
              <Text style={[styles.devHint, { color: colors.muted }]}>
                {devDiagnostic}
              </Text>
            ) : null}
          </View>
        ) : (
          <View style={styles.plans}>
            <PlanCard
              name="Free"
              price={`${settings.currency} 0/mo`}
              features={FREE_FEATURES}
              current={currentPlan === 'free'}
              colors={colors}
            />
            <PlanCard
              name="Pro Monthly"
              price={monthlyPriceLabel}
              features={PRO_FEATURES}
              current={isPaid}
              recommended={false}
              onSelect={() => handlePurchase('monthly')}
              loading={upgrading === 'monthly'}
              colors={colors}
            />
            <PlanCard
              name="Pro Yearly"
              price={`${yearlyPriceLabel} · save ~33%`}
              features={PRO_FEATURES}
              current={false}
              recommended={!isPaid}
              onSelect={() => handlePurchase('yearly')}
              loading={upgrading === 'yearly'}
              colors={colors}
            />
          </View>
        )}

        {!isBetaUnlocked && (
          <View style={styles.actionsRow}>
            <AnimatedPressable
              style={[
                styles.secondaryBtn,
                {
                  borderColor: colors.brand.dark,
                  backgroundColor: colors.brand.base + '18',
                },
              ]}
              onPress={handleRestore}
              accessibilityRole="button"
              accessibilityLabel="Restore previous purchases"
            >
              {restoring ? (
                <ActivityIndicator size="small" color={colors.brand.dark} />
              ) : (
                <Text style={[styles.secondaryBtnText, { color: colors.brand.dark }]}>
                  Restore Purchases
                </Text>
              )}
            </AnimatedPressable>

            {isPaid && (
              <AnimatedPressable
                style={[
                  styles.secondaryBtn,
                  {
                    borderColor: colors.brand.dark,
                    backgroundColor: colors.brand.base + '18',
                  },
                ]}
                onPress={handleManage}
                accessibilityRole="button"
                accessibilityLabel={t('subscription.manage_a11y')}
              >
                <Text style={[styles.secondaryBtnText, { color: colors.brand.dark }]}>
                  {t('subscription.manage')}
                </Text>
              </AnimatedPressable>
            )}
          </View>
        )}

        {!isBetaUnlocked && (
        <Text style={[styles.legalText, { color: colors.muted }]}>
          Subscriptions auto-renew until cancelled. Cancel any time in your{' '}
          {Platform.OS === 'ios' ? 'Apple ID' : 'Google Play'} subscriptions. Payment is
          charged to your{' '}
          {Platform.OS === 'ios' ? 'Apple ID' : 'Google Play'} account on confirmation. By
          subscribing you agree to our{' '}
          <Text
            style={{ color: colors.accent }}
            onPress={() => Linking.openURL('https://sparrowcollect.com/terms.html')}
          >
            Terms
          </Text>{' '}
          and{' '}
          <Text
            style={{ color: colors.accent }}
            onPress={() => Linking.openURL('https://sparrowcollect.com/privacy.html')}
          >
            Privacy Policy
          </Text>
          .
        </Text>
        )}
      </ScrollView>
      </Animated.View>
      <QuickNavBar />
    </View>
  );
}

export default function SubscriptionScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Subscription">
      <SubscriptionScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  scroll: {
    // 16, not 20 — this is the app-wide screen gutter (analytics.tsx,
    // (tabs)/index.tsx, purchase/index.tsx and the template in
    // docs/ui-playbook.md all use 16). At 20 the Restore / Manage buttons sat
    // 4pt narrower on each side than every other screen's content, which is
    // visible when navigating between them. The buttons are flex:1 inside
    // actionsRow, so this gutter is what sets their outer edges.
    paddingHorizontal: 16,
    paddingVertical: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    marginBottom: 20,
  },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
  },
  warningText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 19,
  },
  plans: {
    gap: 16,
  },
  planCard: {
    borderWidth: 1,
    borderRadius: 16,
    padding: 20,
  },
  recommendedBadge: {
    position: 'absolute',
    top: -10,
    right: 16,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  recommendedText: {
    fontSize: 10,
    fontWeight: '800',
    // colour comes from colors.accentText at the call site — see selectBtnText.
    letterSpacing: 0.5,
  },
  planName: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 4,
  },
  planPrice: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 16,
  },
  featureList: {
    gap: 8,
    marginBottom: 16,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  featureText: {
    fontSize: 14,
  },
  currentBadge: {
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  currentBadgeText: {
    fontSize: 14,
    fontWeight: '700',
  },
  selectBtn: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  selectBtnText: {
    // NOT hardcoded white. These buttons are painted with colors.brand.darker /
    // brand.dark, and in the high-contrast DARK palette brand.darker is
    // '#FFFFFF' (src/theme/highContrast.ts) — so a fixed white label rendered
    // white-on-white and the primary CTA was invisible. colors.accentText
    // resolves per palette: #000000 (HC dark), #0b1120 (dark), #ffffff (light),
    // #FFFFFF (HC light). 43 other files already use this token.
    fontSize: 15,
    fontWeight: '700',
  },
  actionsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    marginTop: 24,
  },
  secondaryBtn: {
    flex: 1,
    borderWidth: 1.5,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryBtnText: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  legalText: {
    fontSize: 11,
    lineHeight: 16,
    marginTop: 20,
    textAlign: 'center',
  },
  retryBtn: {
    marginTop: 20,
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: 12,
  },
  retryBtnText: {
    fontSize: 15,
    fontWeight: '700',
  },
  devHint: {
    marginTop: 20,
    fontSize: 12,
    lineHeight: 17,
    textAlign: 'center',
    fontStyle: 'italic',
  },
  comingSoonSection: {
    alignItems: 'center',
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  comingSoonIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  comingSoonTitle: {
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 10,
  },
  comingSoonText: {
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
});
