/**
 * DevForcePlanSection — dev-only toggle to preview paid-tier views without
 * wiring a real Stripe subscription. Writes to AsyncStorage (native) and
 * localStorage (web) so a reload lands on the selected tier.
 *
 * Paired with useBillingLimits resolver which picks up the override on mount.
 * Production builds hide this section entirely (gated on __DEV__).
 *
 * Added 2026-04-19 when the analytics paywall blocked preview with no
 * accessible way through in web dev mode.
 */

import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { logger } from '@/lib/logger';

const STORAGE_KEY = '@collectai/force_plan';
const WEB_KEY = 'COLLECTAI_FORCE_PLAN';

type Plan = 'free' | 'pro' | 'premium';

const PLANS: Plan[] = ['free', 'pro', 'premium'];

export const DevForcePlanSection: React.FC = () => {
  const { colors } = useAppTheme();
  const [current, setCurrent] = useState<Plan | null>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(STORAGE_KEY)
      .then((v) => {
        if (cancelled) return;
        const s = (v || '').toLowerCase();
        if (s === 'pro' || s === 'premium' || s === 'free') setCurrent(s as Plan);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Hide in production builds
  if (typeof __DEV__ !== 'undefined' && !__DEV__) return null;

  const setPlan = async (plan: Plan) => {
    setCurrent(plan);
    try {
      await AsyncStorage.setItem(STORAGE_KEY, plan);
    } catch (e) {
      logger.error('[silent-catch] DevForcePlanSection.tsx:49:', e);
      // no-op
    }
    if (typeof window !== 'undefined' && window.localStorage) {
      try {
        window.localStorage.setItem(WEB_KEY, plan);
      } catch (e) {
        logger.error('[silent-catch] DevForcePlanSection.tsx:55:', e);
        // no-op
      }
    }
    // Encourage reload so useBillingLimits picks up the new value
    if (typeof window !== 'undefined' && window.location) {
      window.location.reload();
    }
  };

  const clearOverride = async () => {
    setCurrent(null);
    try {
      await AsyncStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      logger.error('[silent-catch] DevForcePlanSection.tsx:69:', e);
      // no-op
    }
    if (typeof window !== 'undefined' && window.localStorage) {
      try {
        window.localStorage.removeItem(WEB_KEY);
      } catch (e) {
        logger.error('[silent-catch] DevForcePlanSection.tsx:75:', e);
        // no-op
      }
    }
    if (typeof window !== 'undefined' && window.location) {
      window.location.reload();
    }
  };

  return (
    <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.header}>
        <Ionicons name="construct-outline" size={16} color={colors.warning} />
        <Text style={[styles.title, { color: colors.text }]}>Dev: Force Plan</Text>
        <View style={[styles.devBadge, { backgroundColor: colors.warning + '20' }]}>
          <Text style={[styles.devBadgeText, { color: colors.warning }]}>DEV ONLY</Text>
        </View>
      </View>
      <Text style={[styles.subtitle, { color: colors.muted }]}>
        Preview paid-tier views without a real subscription. Reloads on change.
      </Text>
      <View style={styles.row}>
        {PLANS.map((p) => {
          const isActive = current === p;
          return (
            <Pressable
              key={p}
              onPress={() => setPlan(p)}
              style={[
                styles.chip,
                { borderColor: colors.border },
                isActive && { backgroundColor: colors.accent, borderColor: colors.accent },
              ]}
              accessibilityRole="button"
              accessibilityLabel={`Set dev plan to ${p}`}
            >
              <Text
                style={[
                  styles.chipText,
                  { color: isActive ? colors.accentText : colors.text },
                ]}
              >
                {p.toUpperCase()}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {current && (
        <Pressable
          onPress={clearOverride}
          style={styles.clearBtn}
          accessibilityRole="button"
          accessibilityLabel="Clear dev plan override"
        >
          <Text style={[styles.clearText, { color: colors.muted }]}>
            Clear override (use real billing)
          </Text>
        </Pressable>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  section: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginTop: 12,
    marginBottom: 12,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  title: {
    fontSize: 14,
    fontWeight: '700',
    flex: 1,
  },
  devBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  devBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  subtitle: {
    fontSize: 11,
    marginBottom: 10,
  },
  row: {
    flexDirection: 'row',
    gap: 8,
  },
  chip: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  chipText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  clearBtn: {
    marginTop: 8,
    alignItems: 'center',
  },
  clearText: {
    fontSize: 11,
    textDecorationLine: 'underline',
  },
});
