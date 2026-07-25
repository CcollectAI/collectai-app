/**
 * SellerAgeGate — global, one-time "I am 18+" confirmation gate for any
 * seller-side action.
 *
 * Wired into httpClient: any /marketplace/listings/* mutating endpoint that
 * returns 412 with `detail.error === 'seller_age_verification_required'`
 * pops this modal automatically. On confirm, the client calls
 * POST /marketplace/listings/age-verify, then retries the original request.
 *
 * Replaces the onboarding-time age checkbox (2026-05-18 onboarding rework).
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Modal, View, Text, StyleSheet, Pressable, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { verifySellerAge } from '@/api/marketplaceApi';
import { registerSellerAgeGate } from '@/api/sellerAgeGate';
import { fonts } from '@/theme/tokens';
import { logger } from '@/lib/logger';

type Pending = {
  resolve: (ok: boolean) => void;
};

export function SellerAgeGateProvider({ children }: { children: React.ReactNode }) {
  const { colors, isDark } = useAppTheme();
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const pendingRef = useRef<Pending | null>(null);

  // Register the popGate callback with the httpClient on mount.
  useEffect(() => {
    registerSellerAgeGate(() => {
      return new Promise<boolean>((resolve) => {
        pendingRef.current = { resolve };
        setVisible(true);
      });
    });
    return () => registerSellerAgeGate(null);
  }, []);

  const finish = useCallback((ok: boolean) => {
    setVisible(false);
    setBusy(false);
    const p = pendingRef.current;
    pendingRef.current = null;
    p?.resolve(ok);
  }, []);

  const onConfirm = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      await verifySellerAge();
      finish(true);
    } catch (e) {
      logger.error('[silent-catch] SellerAgeGate.tsx:56:', e);
      // If the verify call itself fails (network etc.) treat as cancel so
      // the caller doesn't retry against a still-gated backend.
      finish(false);
    }
  }, [busy, finish]);

  const onCancel = useCallback(() => finish(false), [finish]);

  return (
    <>
      {children}
      <Modal
        visible={visible}
        animationType="fade"
        transparent
        onRequestClose={onCancel}
      >
        <View style={s.backdrop}>
          <View style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={[s.iconWrap, { backgroundColor: colors.brand.base + '20' }]}>
              <Ionicons name="shield-checkmark-outline" size={28} color={colors.brand.dark} />
            </View>
            <Text style={[s.title, { color: colors.text, fontFamily: fonts.bold }]}>
              Confirm your age
            </Text>
            <Text style={[s.body, { color: colors.muted }]}>
              To sell items, list on marketplaces, or connect a seller account,
              please confirm you are of legal age in your region (18 or the
              local age of majority).
            </Text>

            <Pressable
              onPress={onConfirm}
              disabled={busy}
              style={[
                s.primary,
                { backgroundColor: colors.brand.dark, opacity: busy ? 0.6 : 1 },
              ]}
              accessibilityRole="button"
              accessibilityLabel="I'm 18 or older"
            >
              <Text style={s.primaryText}>{busy ? 'Saving…' : "I'm 18 or older"}</Text>
            </Pressable>

            <Pressable
              onPress={onCancel}
              disabled={busy}
              style={s.secondary}
              accessibilityRole="button"
              accessibilityLabel="Cancel"
            >
              <Text style={[s.secondaryText, { color: colors.muted }]}>Not now</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  card: {
    width: '100%',
    maxWidth: 380,
    borderRadius: 20,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 24,
    alignItems: 'center',
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOpacity: 0.2,
        shadowRadius: 24,
        shadowOffset: { width: 0, height: 8 },
      },
      android: { elevation: 10 },
    }),
  },
  iconWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 8,
  },
  body: {
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
    marginBottom: 20,
  },
  primary: {
    width: '100%',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },
  secondary: {
    paddingVertical: 12,
    marginTop: 8,
  },
  secondaryText: {
    fontSize: 14,
    fontWeight: '600',
  },
});
