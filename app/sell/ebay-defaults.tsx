/**
 * eBay Publish Defaults — required-once setup before any /publish call.
 *
 * eBay's Sell API requires four IDs on every listing:
 *   - categoryId (numeric, eBay's leaf category, e.g. 183454 for Pokemon Single Cards)
 *   - fulfillmentPolicyId (shipping policy)
 *   - paymentPolicyId
 *   - returnPolicyId
 *
 * Without these, /marketplace/listings/{id}/publish returns 412 with the
 * missing-fields list. Rather than ask the user to re-enter them on every
 * listing, we store them per-account in marketplace_account_defaults and
 * apply automatically.
 *
 * Where users find these in eBay:
 *   - Category ID: lookup at https://www.ebay.com/help/selling/listings/finding-category-id
 *   - Policies: eBay Seller Hub → Account → Business policies
 *
 * The optional location_key is for sellers using stored seller locations
 * (warehouses); most individual sellers leave it blank.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Stack, useRouter } from 'expo-router';
import { useAppTheme } from '@/hooks/useAppTheme';
import { useSettings } from '@/lib/settings';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import { getEbayDefaults, setEbayDefaults } from '@/api/marketplaceApi';
import { logger } from '@/lib/logger';
import { useToast } from '@/components/Toast';
import { SELLING_ENABLED } from '@/config/featureFlags';
import { SellingUnavailable } from '@/components/sell/SellingUnavailable';
import { safeGoBack } from '@/lib/goBack';

const FIELDS: Array<{
  key: 'ebay_category_id' | 'fulfillment_policy_id' | 'payment_policy_id' | 'return_policy_id' | 'location_key';
  label: string;
  hint: string;
  required: boolean;
  helpUrl?: string;
}> = [
  {
    key: 'ebay_category_id',
    label: 'Category ID',
    hint: 'eBay leaf category (e.g. 183454 for Pokemon Cards). Look up via the eBay category browser.',
    required: true,
    helpUrl: 'https://www.ebay.com/help/selling/listings/finding-category-id',
  },
  {
    key: 'fulfillment_policy_id',
    label: 'Fulfillment policy ID',
    hint: 'Your default shipping policy. Find in eBay Seller Hub → Account → Business policies.',
    required: true,
    helpUrl: 'https://www.bizpolicy.ebay.com/businesspolicy/manageshipping',
  },
  {
    key: 'payment_policy_id',
    label: 'Payment policy ID',
    hint: 'Your default payment policy.',
    required: true,
    helpUrl: 'https://www.bizpolicy.ebay.com/businesspolicy/managepayments',
  },
  {
    key: 'return_policy_id',
    label: 'Return policy ID',
    hint: 'Your default return policy.',
    required: true,
    helpUrl: 'https://www.bizpolicy.ebay.com/businesspolicy/managereturns',
  },
  {
    key: 'location_key',
    label: 'Location key (optional)',
    hint: 'Stored seller location key. Leave blank for individual sellers.',
    required: false,
  },
];

type FormState = {
  ebay_category_id: string;
  fulfillment_policy_id: string;
  payment_policy_id: string;
  return_policy_id: string;
  location_key: string;
};

export default function EbayDefaultsScreenWithBoundary() {
  if (!SELLING_ENABLED) return <SellingUnavailable title="eBay Defaults" />;
  return (
    <ScreenErrorBoundary screenName="eBay Defaults">
      <EbayDefaultsScreen />
    </ScreenErrorBoundary>
  );
}

function EbayDefaultsScreen() {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const router = useRouter();
  const { showToast } = useToast();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<FormState>({
    ebay_category_id: '',
    fulfillment_policy_id: '',
    payment_policy_id: '',
    return_policy_id: '',
    location_key: '',
  });

  const load = useCallback(async () => {
    try {
      const r = (await getEbayDefaults()) as Partial<FormState> | undefined;
      if (r) {
        setForm({
          ebay_category_id: r.ebay_category_id ?? '',
          fulfillment_policy_id: r.fulfillment_policy_id ?? '',
          payment_policy_id: r.payment_policy_id ?? '',
          return_policy_id: r.return_policy_id ?? '',
          location_key: r.location_key ?? '',
        });
      }
    } catch (e) {
      logger.error('get_ebay_defaults_failed', { error: String(e) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const requiredOk =
    form.ebay_category_id.trim() &&
    form.fulfillment_policy_id.trim() &&
    form.payment_policy_id.trim() &&
    form.return_policy_id.trim();

  const handleSave = async () => {
    if (!requiredOk) {
      Alert.alert(
        'Missing fields',
        'Category ID, fulfillment, payment, and return policy IDs are all required.',
      );
      return;
    }
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setSaving(true);
    try {
      await setEbayDefaults({
        ebay_category_id: form.ebay_category_id.trim(),
        fulfillment_policy_id: form.fulfillment_policy_id.trim(),
        payment_policy_id: form.payment_policy_id.trim(),
        return_policy_id: form.return_policy_id.trim(),
        location_key: form.location_key.trim() || undefined,
      });
      showToast({ message: 'Defaults saved', type: 'success' });
      safeGoBack(router);
    } catch (e) {
      logger.error('set_ebay_defaults_failed', { error: String(e) });
      Alert.alert(
        'Save failed',
        'Could not save eBay defaults. Check your values and try again.',
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ title: 'eBay defaults' }} />
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={['left', 'right']}>
      <Stack.Screen options={{ title: 'eBay defaults' }} />
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <Text style={[styles.heading, { color: colors.text }]}>Publish defaults</Text>
        <Text style={[styles.intro, { color: colors.muted }]}>
          eBay requires a category and three policy IDs on every listing.
          Set them once here and Sparrow will apply them automatically when
          you publish.
        </Text>

        {FIELDS.map((field) => (
          <View key={field.key} style={styles.fieldGroup}>
            <Text style={[styles.label, { color: colors.text }]}>
              {field.label}
              {field.required && <Text style={{ color: colors.danger }}> *</Text>}
            </Text>
            <TextInput
              style={[
                styles.input,
                { backgroundColor: colors.card, borderColor: colors.border, color: colors.text },
              ]}
              value={form[field.key]}
              onChangeText={(v) => setForm((prev) => ({ ...prev, [field.key]: v }))}
              placeholder={field.hint.split('.')[0]}
              placeholderTextColor={colors.muted}
              autoCapitalize="none"
              autoCorrect={false}
              editable={!saving}
            />
            <View style={styles.hintRow}>
              <Text style={[styles.hintText, { color: colors.muted }]}>{field.hint}</Text>
              {field.helpUrl && (
                <AnimatedPressable
                  onPress={() => Linking.openURL(field.helpUrl!).catch(() => {})}
                  accessibilityRole="link"
                  accessibilityLabel={`Open eBay help for ${field.label}`}
                >
                  <Text style={[styles.helpLink, { color: colors.accent }]}>Find this →</Text>
                </AnimatedPressable>
              )}
            </View>
          </View>
        ))}

        <AnimatedPressable
          style={[
            styles.saveBtn,
            { backgroundColor: requiredOk ? colors.accent : colors.muted },
          ]}
          onPress={handleSave}
          disabled={!requiredOk || saving}
          accessibilityRole="button"
          accessibilityLabel="Save eBay defaults"
          accessibilityState={{ disabled: !requiredOk || saving, busy: saving }}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <>
              <Ionicons name="checkmark-circle-outline" size={18} color="#fff" />
              <Text style={styles.saveBtnText}>Save defaults</Text>
            </>
          )}
        </AnimatedPressable>

        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  container: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 24 },
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  heading: { fontSize: 22, fontWeight: '800', marginBottom: 6 },
  intro: { fontSize: 13, lineHeight: 19, marginBottom: 20 },

  fieldGroup: { marginBottom: 16 },
  label: { fontSize: 13, fontWeight: '600', marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 15,
  },
  hintRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginTop: 6,
    gap: 8,
  },
  hintText: { flex: 1, fontSize: 11, lineHeight: 16 },
  helpLink: { fontSize: 12, fontWeight: '600' },

  saveBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderRadius: 12,
    marginTop: 8,
  },
  saveBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
