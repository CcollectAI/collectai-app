/**
 * The auth context object, alone — no provider, no Supabase, no caches.
 *
 * Split out of AuthProvider.tsx (2026-09-26) so a hook can READ the signed-in
 * user without importing the provider's whole module graph: useBillingLimits
 * started importing AuthProvider and every test that renders a billing
 * consumer then had to load offlineCache, the logger and Supabase. The type is
 * a type-only import, erased at runtime, so this adds no cycle.
 */
import { createContext } from 'react';
import type { AuthContextValue } from './AuthProvider';

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);
