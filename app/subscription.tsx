/**
 * Subscription screen — shows current plan and upgrade options.
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  Alert,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import {
  getBillingStatus,
  createCheckoutSession,
  createPortalSession,
  type BillingStatus,
} from '@/api/collectorsApi';

const TIFFANY = '#81D8D0';
const TIFFANY_DARK = '#5FBFB6';
const NAVY = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';
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
}

function PlanCard({ name, price, features, current, recommended, onSelect, loading }: PlanCardProps) {
  return (
    <View style={[styles.planCard, current && styles.planCardCurrent, recommended && styles.planCardRecommended]}>
      {recommended && (
        <View style={styles.recommendedBadge}>
          <Text style={styles.recommendedText}>RECOMMENDED</Text>
        </View>
      )}
      <Text style={styles.planName}>{name}</Text>
      <Text style={styles.planPrice}>{price}</Text>
      <View style={styles.featureList}>
        {features.map((f) => (
          <View key={f} style={styles.featureRow}>
            <Ionicons name="checkmark-circle" size={18} color={current ? TIFFANY_DARK : MUTED} />
            <Text style={styles.featureText}>{f}</Text>
          </View>
        ))}
      </View>
      {current ? (
        <View style={styles.currentBadge}>
          <Text style={styles.currentBadgeText}>Current Plan</Text>
        </View>
      ) : (
        <AnimatedPressable
          style={[styles.selectBtn, recommended && styles.selectBtnRecommended]}
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

export default function SubscriptionScreen() {
  const router = useRouter();
  const { settings } = useSettings();
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);

  useEffect(() => {
    getBillingStatus()
      .then(setBilling)
      .catch(() => {})
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
        Alert.alert('Error', 'Invalid checkout URL received.');
        return;
      }
      await WebBrowser.openBrowserAsync(url);
      // Refresh status after returning from Stripe
      const updated = await getBillingStatus();
      setBilling(updated);
    } catch (e: unknown) {
      Alert.alert('Upgrade failed', e instanceof Error ? e.message : 'Please try again.');
    } finally {
      setUpgrading(null);
    }
  }

  async function handleManage() {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      const { url } = await createPortalSession();
      if (!isValidUrl(url)) {
        Alert.alert('Error', 'Invalid portal URL received.');
        return;
      }
      await WebBrowser.openBrowserAsync(url);
      const updated = await getBillingStatus();
      setBilling(updated);
    } catch (e: unknown) {
      Alert.alert('Error', e instanceof Error ? e.message : 'Could not open billing portal.');
    }
  }

  const currentPlan = billing?.plan ?? 'free';

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>Subscription</Text>

        {billing?.status === 'past_due' && (
          <View style={styles.warningBanner}>
            <Ionicons name="warning" size={18} color={WARNING} />
            <Text style={styles.warningText}>Payment past due. Update your payment method to avoid interruption.</Text>
          </View>
        )}

        {billing?.cancel_at_period_end && (
          <View style={styles.warningBanner}>
            <Ionicons name="information-circle" size={18} color={MUTED} />
            <Text style={styles.warningText}>Your plan will be downgraded at the end of the current period.</Text>
          </View>
        )}

        {loading ? (
          <ActivityIndicator size="large" color={TIFFANY} style={{ marginTop: 40 }} />
        ) : (
          <View style={styles.plans}>
            <PlanCard
              name="Free"
              price="EUR 0/mo"
              features={['3 purchase mandates', 'Basic valuation', 'Community access']}
              current={currentPlan === 'free'}
            />
            <PlanCard
              name="Pro"
              price="EUR 4.99/mo"
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
            />
            <PlanCard
              name="Premium"
              price="EUR 9.99/mo"
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
            />
          </View>
        )}

        {billing && currentPlan !== 'free' && (
          <AnimatedPressable
            style={styles.manageBtn}
            onPress={handleManage}
            accessibilityRole="button"
            accessibilityLabel="Manage subscription"
          >
            <Text style={styles.manageBtnText}>Manage Subscription</Text>
          </AnimatedPressable>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  scroll: {
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: NAVY,
    marginBottom: 20,
  },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: WARNING + '15',
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
  },
  warningText: {
    flex: 1,
    fontSize: 13,
    color: NAVY,
    lineHeight: 19,
  },
  plans: {
    gap: 16,
  },
  planCard: {
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 16,
    padding: 20,
  },
  planCardCurrent: {
    borderColor: TIFFANY,
    borderWidth: 2,
    backgroundColor: TIFFANY + '08',
  },
  planCardRecommended: {
    borderColor: TIFFANY_DARK,
    borderWidth: 2,
  },
  recommendedBadge: {
    position: 'absolute',
    top: -10,
    right: 16,
    backgroundColor: TIFFANY_DARK,
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
    color: NAVY,
    marginBottom: 4,
  },
  planPrice: {
    fontSize: 16,
    fontWeight: '600',
    color: MUTED,
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
    color: NAVY,
  },
  currentBadge: {
    backgroundColor: SUCCESS + '15',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  currentBadgeText: {
    fontSize: 14,
    fontWeight: '700',
    color: SUCCESS,
  },
  selectBtn: {
    backgroundColor: NAVY,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  selectBtnRecommended: {
    backgroundColor: TIFFANY_DARK,
  },
  selectBtnText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
  manageBtn: {
    marginTop: 24,
    borderWidth: 1,
    borderColor: BORDER,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  manageBtnText: {
    fontSize: 15,
    fontWeight: '600',
    color: TIFFANY_DARK,
  },
});
