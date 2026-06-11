/**
 * AuthProvider — single source of truth for authentication state.
 *
 * Wraps the app and provides user/session/profile via React Context.
 * Internally listens to Supabase onAuthStateChange and loads the
 * user's profile row from the `profiles` table.
 */

import React, { createContext, useEffect, useState, useCallback } from 'react';
import * as Linking from 'expo-linking';
import { router, type Href } from 'expo-router';
import { Session, User } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import { logger } from '@/lib/logger';
import { setRecoveryPending } from '@/auth/recoveryState';

import { identifyUser, resetAnalytics, track } from '@/analytics/track';
import {
  initPurchases,
  identifyUser as identifyPurchasesUser,
} from '@/lib/purchases';

/* ---------- Sentry (guarded) ---------- */
import type { SentryModule } from '@/../types/api';
let Sentry: SentryModule | null = null;
try {
  Sentry = require('@sentry/react-native');
} catch (_) {
  // not installed
}

export type Profile = {
  id: string;
  username: string;
  created_at?: string;
};

export type AuthContextValue = {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
  signOut: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProfile = useCallback(async (u: User | null) => {
    if (!u) {
      setProfile(null);
      return;
    }
    try {
      const { data, error } = await supabase
        .from('profiles')
        .select('id, username, created_at')
        .eq('id', u.id)
        .single();
      if (error) throw error;
      setProfile(data as Profile);
    } catch {
      setProfile(null);
    }
  }, []);

  // Auth deep-link handler. When the app is opened via the email confirmation
  // (or magic) link, Supabase appends the session to the URL fragment, e.g.
  //   sparrow://#access_token=...&refresh_token=...&type=signup
  // React Native has no `detectSessionInUrl`, so parse it manually and hydrate
  // the session; the onAuthStateChange listener below then routes the now
  // signed-in user into the app. Added 2026-06-11 so tapping the confirm link
  // drops testers straight into the app instead of stranding them. The web
  // /auth/confirm page forwards its #fragment to sparrow:// for this handler.
  useEffect(() => {
    const handleAuthLink = async (url: string | null) => {
      if (!url) return;
      const hashIdx = url.indexOf('#');
      if (hashIdx === -1) return;
      const params: Record<string, string> = {};
      for (const kv of url.slice(hashIdx + 1).split('&')) {
        const eq = kv.indexOf('=');
        if (eq === -1) continue;
        params[kv.slice(0, eq)] = decodeURIComponent(kv.slice(eq + 1));
      }
      const access_token = params['access_token'];
      const refresh_token = params['refresh_token'];
      if (!access_token || !refresh_token) return;
      // Password-recovery links must land on the reset-password screen with the
      // session set — not log the user straight into the app. Flag it before
      // setSession so the root gate cooperates (see recoveryState).
      const isRecovery = params['type'] === 'recovery' || url.indexOf('reset-password') !== -1;
      if (isRecovery) setRecoveryPending(true);
      try {
        await supabase.auth.setSession({ access_token, refresh_token });
        if (isRecovery) router.replace('/(auth)/reset-password' as Href);
      } catch (e) {
        logger.warn('[AuthProvider] setSession from deep link failed:', e);
        if (isRecovery) setRecoveryPending(false);
      }
    };
    Linking.getInitialURL().then(handleAuthLink).catch(() => {});
    const sub = Linking.addEventListener('url', ({ url }) => { void handleAuthLink(url); });
    return () => sub.remove();
  }, []);

  useEffect(() => {
    let active = true;

    initPurchases();

    (async () => {
      try {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;
        if (!active) return;

        setSession(data.session ?? null);
        setUser(data.session?.user ?? null);
        if (Sentry?.setUser) {
          Sentry.setUser(data.session?.user ? { id: data.session.user.id } : null);
        }
        if (data.session?.user) {
          identifyUser(data.session.user.id);
          void identifyPurchasesUser(data.session.user.id);
        }
        await loadProfile(data.session?.user ?? null);
      } catch (e) {
        logger.warn('[AuthProvider] getSession error:', e);
      } finally {
        if (active) setLoading(false);
      }
    })();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, newSession) => {
      if (!active) return;
      setSession(newSession);
      setUser(newSession?.user ?? null);
      if (Sentry?.setUser) {
        Sentry.setUser(newSession?.user ? { id: newSession.user.id } : null);
      }
      if (newSession?.user) {
        identifyUser(newSession.user.id);
        void identifyPurchasesUser(newSession.user.id);
      } else {
        void identifyPurchasesUser(null);
      }
      await loadProfile(newSession?.user ?? null);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [loadProfile]);

  const signOut = useCallback(async () => {
    try {
      await supabase.auth.signOut();
      setSession(null);
      setUser(null);
      setProfile(null);
      if (Sentry?.setUser) Sentry.setUser(null);
      track({ name: 'user_logged_out' });
      resetAnalytics();
    } catch (e) {
      logger.warn('[AuthProvider] signOut error:', e);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, session, profile, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
