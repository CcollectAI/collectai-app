/**
 * Subscription screen — shows current plan and upgrade options.
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { QuickNavBar } from '@/components/QuickNavBar';
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useAppTheme } from '@/hooks/useAppTheme';
import {
  getBillingStatus,
  createCheckoutSession,
  createPortalSession,
  type BillingStatus,
} from '@/api/collectorsApi';
import { useToast } from '@/components/Toast';

const SUCCESS = '#10B981';
const WARNING = '#F59E0B';

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
      <View style={styles.featureList} accessibilityRole="list" accessibilityLabel="Plan features">
        {features.map((f) => (
          <View key={f} style={styles.featureRow} accessibilityLabel={f}>
            <Ionicons name="checkmark-circle" size={18} color={current ? colors.brand.dark : colors.muted} />
            <Text style={[styles.featureText, { color: colors.text }]}>{f}</Text>
          </View>
        ))}
      </View>
      {current ? (
        <View style={[styles.currentBadge, { backgroundColor: SUCCESS + '15' }]}>
          <Text style={[styles.currentBadgeText, { color: SUCCESS }]}>Current Plan</Text>
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

function SubscriptionScreen() {
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);

  useEffect(() => {
    getBillingStatus()
      .then(setBilling)
      .catch(() => {
        showToast({ message: 'Could not load subscription info. Please try again later.', type: 'error' });
      })
      .finally(() => setLoading(false));
  }, []);

  function isValidUrl(url: unknown): url is string {
    if (typeof url !== 'string' || !url) return false;
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:';
    } catch {
      return false;
    }
  }

  async function handleUpgrade(plan: 'pro' | 'premium') {
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setUpgrading(plan);
    try {
      const { url } = await createCheckoutSession(plan);
      if (!isValidUrl(url)) {
        showToast({ message: 'Invalid checkout URL received.', type: 'error' });
        return;
      }
      await WebBrowser.openBrowserAsync(url);
      // Refresh status after returning from Stripe
      const updated = await getBillingStatus();
      setBilling(updated);
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Upgrade failed. Please try again.', type: 'error' });
    } finally {
      setUpgrading(null);
    }
  }

  async function handleManage() {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      const { url } = await createPortalSession();
      if (!isValidUrl(url)) {
        showToast({ message: 'Invalid portal URL received.', type: 'error' });
        return;
      }
      await WebBrowser.openBrowserAsync(url);
      const updated = await getBillingStatus();
      setBilling(updated);
    } catch (e: unknown) {
      showToast({ message: e instanceof Error ? e.message : 'Could not open billing portal.', type: 'error' });
    }
  }

  const currentPlan = billing?.plan ?? 'free';

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[styles.title, { color: colors.text }]}>Subscription</Text>

        {billing?.status === 'past_due' && (
          <View style={[styles.warningBanner, { backgroundColor: WARNING + '15' }]}>
            <Ionicons name="warning" size={18} color={WARNING} />
            <Text style={[styles.warningText, { color: colors.text }]}>Payment past due. Update your payment method to avoid interruption.</Text>
          </View>
        )}

        {billing?.cancel_at_period_end && (
          <View style={[styles.warningBanner, { backgroundColor: WARNING + '15' }]}>
            <Ionicons name="information-circle" size={18} color={colors.muted} />
            <Text style={[styles.warningText, { color: colors.text }]}>Your plan will be downgraded at the end of the current period.</Text>
          </View>
        )}

        {loading ? (
          <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
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
              name="Pro"
              price={`${settings.currency} 4.99/mo`}
              features={[
                '10 purchase mandates',
                'Deal discovery',
                'Dossier PDF export',
                'Priority support',
              ]}
              current={currentPlan === 'pro'}
              recommended={currentPlan === 'free'}
              onSelect={() => handleUpgrade('pro')}
              loading={upgrading === 'pro'}
              colors={colors}
            />
            <PlanCard
              name="Premium"
              price={`${settings.currency} 9.99/mo`}
              features={[
                '50 purchase mandates',
                'Deal discovery',
                'Dossier PDF export',
                'Advanced analytics',
                'Priority support',
              ]}
              current={currentPlan === 'premium'}
              recommended={currentPlan === 'pro'}
              onSelect={() => handleUpgrade('premium')}
              loading={upgrading === 'premium'}
              colors={colors}
            />
          </View>
        )}

        {billing && currentPlan !== 'free' && (
          <AnimatedPressable
            style={[styles.manageBtn, { borderColor: colors.border }]}
            onPress={handleManage}
            accessibilityRole="button"
            accessibilityLabel="Manage subscription"
          >
            <Text style={[styles.manageBtnText, { color: colors.brand.dark }]}>Manage Subscription</Text>
          </AnimatedPressable>
        )}
      </ScrollView>
      <QuickNavBar />
    </SafeAreaView>
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
  manageBtn: {
    marginTop: 24,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  manageBtnText: {
    fontSize: 15,
    fontWeight: '600',
  },
});
