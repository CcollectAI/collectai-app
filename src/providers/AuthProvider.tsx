/**
 * AuthProvider — single source of truth for authentication state.
 *
 * Wraps the app and provides user/session/profile via React Context.
 * Internally listens to Supabase onAuthStateChange and loads the
 * user's profile row from the `profiles` table.
 */

import React, { createContext, useEffect, useState, useCallback } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import * as Linking from 'expo-linking';
import { router, type Href } from 'expo-router';
import { Session, User } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import { captureReferralFromUrl } from '@/lib/referral';
import { logger } from '@/lib/logger';
import { setRecoveryPending } from '@/auth/recoveryState';

import { identifyUser, resetAnalytics, track } from '@/analytics/track';
import {
  initPurchases,
  identifyUser as identifyPurchasesUser,
  setReferralAttribute,
} from '@/lib/purchases';

/* ---------- Sentry (guarded) ---------- */
import type { SentryModule } from '@/../types/api';
import { withTimeout } from '@/lib/withTimeout';

// `loading` gates the whole app: the router waits on it, and Home/Items now
// defer their first fetch until it clears. supabase-js has no per-request
// timeout, so if getSession() or the profile read stalls behind the auth lock
// `setLoading(false)` never runs and EVERY screen sits there — the worst
// version of the 2026-07-25 "stuck loading" class, because nothing downstream
// can recover from it.
//
// WHY THIS IS SAFE despite `lock: processLock` (see docs/AUTH_AND_WEB_DEPLOY.md
// and the 2026-07-11 401 saga): withTimeout is Promise.race, which ABANDONS the
// inner call without cancelling it. That is only dangerous when the timeout
// leads to a SECOND concurrent auth op — two refreshes on one rotating
// refresh-token trip Supabase's reuse detection and REVOKE the session. Neither
// call below retries, and neither refreshes: the profile read is a plain
// PostgREST select (not an auth op at all), and getSession() only reads the
// cached session. httpClient.readAccessToken already races getSession the same
// way for the same reason.
//
// On timeout we fall through to `finally { setLoading(false) }` with no session,
// and the onAuthStateChange listener below sets it unconditionally once the lock
// releases — so a slow session is a brief logged-out flash, never a logout.
const AUTH_INIT_TIMEOUT_MS = 8_000;
const PROFILE_READ_TIMEOUT_MS = 6_000;
let Sentry: SentryModule | null = null;
try {
  Sentry = require('@sentry/react-native');
} catch (_) {
  logger.error('[silent-catch] AuthProvider.tsx:55:', _);
  // not installed
}

export type Profile = {
  id: string;
  username: string;
  created_at?: string;
  /** Creator affiliate_code this user signed up under, if any. */
  referred_by_code?: string | null;
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

  const loadProfile = useCallback(async (u: User | null, source: string = 'unknown') => {
    if (!u) {
      setProfile(null);
      return;
    }

    let referredCode: string | null = null;
    const startedAt = Date.now();
    try {
      const { data, error } = await withTimeout(
        supabase
          .from('profiles')
          .select('id, username, created_at, referred_by_code')
          .eq('id', u.id)
          .single(),
        PROFILE_READ_TIMEOUT_MS,
        `AuthProvider.loadProfile(${source})`,
      );
      if (error) throw error;
      const loaded = data as Profile;
      setProfile(loaded);
      referredCode = loaded.referred_by_code ?? null;
    } catch (e) {
      logger.error(
        `[silent-fallback] auth: profile hydrate failed after ${Date.now() - startedAt}ms via ${source}:`,
        e,
      );
      setProfile(null);
    }

    // Deliberately OUTSIDE the try above. Inside it, anything this threw —
    // including a synchronous throw before a promise exists — was caught by
    // that `catch` and turned into setProfile(null), wiping a profile that had
    // already loaded successfully. Attribution is best-effort and must never
    // be able to destroy auth state.
    if (referredCode) {
      try {
        await setReferralAttribute(referredCode);
      } catch (e) {
        logger.error('[AuthProvider] referral attribution failed:', e);
      }
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

      // Creator referral capture, BEFORE the fragment check below. That check
      // bails on any URL without a '#', which silently discarded every
      // query-string link — including https://sparrowcollect.com/r/LUNA10 and
      // sparrow://?ref=LUNA10, i.e. every link a creator would ever post.
      // Awaited so an app opened cold by a creator link has the code stored
      // before the register screen mounts and reads it.
      await captureReferralFromUrl(url);

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
        logger.error('[AuthProvider] setSession from deep link failed:', e);
        if (isRecovery) setRecoveryPending(false);
      }
    };
    Linking.getInitialURL().then(handleAuthLink).catch(() => {});
    const sub = Linking.addEventListener('url', ({ url }) => { void handleAuthLink(url); });
    return () => sub.remove();
  }, []);

  // Supabase-RN gotcha: `autoRefreshToken: true` alone does NOT resume the
  // refresh ticker after the app has been backgrounded past the access-token
  // lifetime (~1h). So getSession() keeps handing back an EXPIRED token, which
  // the API rejects with 401 "Authentication required" — every authenticated
  // write (Follow a category, Add to watchlist) silently fails until relaunch.
  // The documented fix is to drive start/stopAutoRefresh from AppState so the
  // token is force-refreshed whenever the app returns to the foreground.
  useEffect(() => {
    const sync = (state: AppStateStatus) => {
      if (state === 'active') {
        void supabase.auth.startAutoRefresh();
        // startAutoRefresh only (re)starts the ticker — it does NOT force-refresh
        // an already-expired access token. After the app is idle past the ~1h
        // token lifetime, getSession()/getAuthHeaders() keep handing back a
        // stale/absent token on the next cold foreground, so the first screen's
        // requests either 401 or block on httpClient's 2s+8s auth-header wait —
        // the ~10s blank Items page and "Add to watchlist does nothing" hang.
        // A single forced refreshSession() (serialized by processLock, so it
        // can't refresh-storm and trip reuse detection) makes a fresh token
        // available within ~1-2s of foreground. No-ops harmlessly when logged out.
        void supabase.auth.refreshSession().catch(() => {});
      } else {
        void supabase.auth.stopAutoRefresh();
      }
    };
    sync(AppState.currentState);
    const sub = AppState.addEventListener('change', sync);
    return () => sub.remove();
  }, []);

  useEffect(() => {
    let active = true;

    initPurchases();

    (async () => {
      try {
        const { data, error } = await withTimeout(
          supabase.auth.getSession(),
          AUTH_INIT_TIMEOUT_MS,
          'AuthProvider.getSession',
        );
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
        await loadProfile(data.session?.user ?? null, 'getSession');
      } catch (e) {
        logger.error('[AuthProvider] getSession error:', e);
      } finally {
        if (active) setLoading(false);
      }
    })();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
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

      // DEFERRED, and the callback is no longer `async`. Both matter.
      //
      // GoTrueClient invokes onAuthStateChange callbacks from INSIDE
      // `_acquireLock`, and with `lock: processLock` (see supabase.ts, where it
      // is load-bearing) that lock is held for the whole callback. Every
      // `supabase.from(...)` needs a session, so it calls `_useSession`, which
      // queues on the SAME lock — the callback ends up waiting on a lock it is
      // itself holding. Nothing breaks the cycle except the 6s timeout.
      //
      // Measured on device before this change: EVERY cold start logged
      //   "profile hydrate failed after 6011ms via onAuthStateChange"
      // while the identical read via `getSession` succeeded, and the query
      // itself returns in ~90-125ms against prod. So this was never a slow
      // query or an RLS problem — it was self-inflicted lock contention.
      //
      // Worse than a stall: getSession loads the profile successfully first,
      // then this copy times out 6s later and runs setProfile(null), WIPING a
      // profile that was already there. That is why the app showed a
      // signed-in user with no profile.
      //
      // setTimeout(0) lets the callback return, releasing the lock, before the
      // read starts. This is supabase-js's own documented guidance for calling
      // Supabase functions from this callback.
      //
      // NOT a `withTimeout`-on-an-auth-call change: the profile read is a plain
      // PostgREST select, and nothing here refreshes or retries a token — so
      // the refresh-token reuse hazard behind the 2026-07-11 401 saga does not
      // apply (same reasoning as the header comment on AUTH_INIT_TIMEOUT_MS).
      const userForProfile = newSession?.user ?? null;
      setTimeout(() => {
        if (!active) return;
        void loadProfile(userForProfile, 'onAuthStateChange');
      }, 0);
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
      logger.error('[AuthProvider] signOut error:', e);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, session, profile, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
