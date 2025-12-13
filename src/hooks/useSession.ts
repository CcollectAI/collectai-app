/**
 * useSession (debug stub)
 *
 * This is a safe default so screens that expect an authenticated user
 * can run without crashing during development.
 *
 * Later, you can replace this with a real auth-backed implementation
 * (Supabase, Clerk, etc.). For now, we expose a stable "debug-user"
 * so features like watchlist, alerts, and analytics have a user_id.
 */

import { useMemo } from 'react';

export type SessionUser = {
  id: string;
  email?: string | null;
};

export type UseSessionResult = {
  user: SessionUser | null;
  isLoading: boolean;
  signOut: () => Promise<void>;
};

/**
 * Debug implementation:
 * - Always returns a non-null user with id "debug-user".
 * - isLoading is always false.
 */
export function useSession(): UseSessionResult {
  const user = useMemo<SessionUser>(
    () => ({
      id: 'debug-user',
      email: null,
    }),
    [],
  );

  async function signOut(): Promise<void> {
    // No-op in debug mode. Replace with real auth sign-out later.
    return;
  }

  return {
    user,
    isLoading: false,
    signOut,
  };
}

export default useSession;
