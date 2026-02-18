/**
 * Convenience hook for accessing the AuthProvider context.
 *
 * Usage:
 *   const { user, session, profile, loading, signOut } = useAuthContext();
 */

import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from './AuthProvider';

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuthContext must be used within <AuthProvider>');
  }
  return ctx;
}
