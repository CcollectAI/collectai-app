/**
 * AuthProvider — single source of truth for authentication state.
 *
 * Wraps the app and provides user/session/profile via React Context.
 * Internally listens to Supabase onAuthStateChange and loads the
 * user's profile row from the `profiles` table.
 */

import React, { createContext, useEffect, useState, useCallback } from 'react';
import { Session, User } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import { logger } from '@/lib/logger';

import { identifyUser, resetAnalytics, track } from '@/analytics/track';

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
  signInDemo: () => void;
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

  useEffect(() => {
    let active = true;

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

  const signInDemo = useCallback(() => {
    if (!__DEV__) {
      logger.warn('[AuthProvider] signInDemo blocked in production build');
      return;
    }

    const demoUser = {
      id: 'demo-user-00000000-0000-0000-0000-000000000000',
      email: 'demo@collectai.app',
      app_metadata: {},
      user_metadata: { username: 'DemoCollector' },
      aud: 'authenticated',
      created_at: new Date().toISOString(),
    } as unknown as User;

    setUser(demoUser);
    setSession(null);
    setProfile({
      id: demoUser.id,
      username: 'DemoCollector',
      created_at: new Date().toISOString(),
    });
    setLoading(false);
  }, []);

  return (
    <AuthContext.Provider value={{ user, session, profile, loading, signOut, signInDemo }}>
      {children}
    </AuthContext.Provider>
  );
}
