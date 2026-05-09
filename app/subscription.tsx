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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useAppTheme } from '@/hooks/useAppTheme';
import {
  getOfferings,
  purchasePackage,
  restorePurchases,
  planFromCustomerInfo,
  isPurchasesAvailable,
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
          <Text style={styles.recommendedText}>RECOMMENDED</Text>
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
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <Text style={styles.selectBtnText}>
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
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const { plan: currentPlan, loading: planLoading } = useBillingLimits();

  const [offerings, setOfferings] = useState<Offerings>(null);
  const [loading, setLoading] = useState(true);
  const [iapUnavailable, setIapUnavailable] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [upgrading, setUpgrading] = useState<'monthly' | 'yearly' | null>(null);
  const [restoring, setRestoring] = useState(false);

  function fetchOfferings() {
    setLoading(true);
    setFetchError(null);
    setIapUnavailable(false);
    if (!isPurchasesAvailable()) {
      setIapUnavailable(true);
      setLoading(false);
      return;
    }
    getOfferings()
      .then((data) => {
        if (!data?.current) {
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
          properties: { plan: newPlan, period },
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

  const PRO_FEATURES = [
    '10 purchase mandates',
    'Deal discovery',
    'Dossier PDF export',
    'Condition grading',
    'Set completion tracker',
    'Advanced analytics',
    'No ads',
    'Priority support',
  ];

  const monthlyPriceLabel = monthlyPkg?.product.priceString ?? `${settings.currency} 4.99/mo`;
  const yearlyPriceLabel = yearlyPkg?.product.priceString ?? `${settings.currency} 39.99/yr`;

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[styles.title, { color: colors.text }]}>Subscription</Text>

        {screenLoading ? (
          <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
        ) : iapUnavailable ? (
          <View style={styles.comingSoonSection}>
            <View style={[styles.comingSoonIcon, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="rocket-outline" size={40} color={colors.accent} />
            </View>
            <Text style={[styles.comingSoonTitle, { color: colors.text }]}>
              {t('subscription.coming_soon')}
            </Text>
            <Text style={[styles.comingSoonText, { color: colors.muted }]}>
              We're finishing the Pro tier setup. Check back shortly!
            </Text>
          </View>
        ) : fetchError ? (
          <>
            <View style={[styles.warningBanner, { backgroundColor: colors.warning + '15' }]}>
              <Ionicons name="warning-outline" size={18} color={colors.warning} />
              <Text style={[styles.warningText, { color: colors.text }]}>
                Couldn't load plans.{' '}
                <Text style={{ color: colors.accent }} onPress={fetchOfferings}>
                  Retry
                </Text>
              </Text>
            </View>
          </>
        ) : (
          <View style={styles.plans}>
            <PlanCard
              name="Free"
              price={`${settings.currency} 0/mo`}
              features={['3 purchase mandates', 'Basic valuation', 'Community access']}
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

        <View style={styles.actionsRow}>
          <AnimatedPressable
            style={[styles.secondaryBtn, { borderColor: colors.border }]}
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
              style={[styles.secondaryBtn, { borderColor: colors.border }]}
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
      </ScrollView>
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
    paddingHorizontal: 20,
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
    color: '#FFFFFF',
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
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
  },
  secondaryBtn: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  secondaryBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
  legalText: {
    fontSize: 11,
    lineHeight: 16,
    marginTop: 20,
    textAlign: 'center',
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
