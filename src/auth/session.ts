import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';

export type SessionState = { ready: boolean; signedIn: boolean };

export function useSession(): SessionState {
  const [state, setState] = useState<SessionState>({ ready: false, signedIn: false });

  useEffect(() => {
    // Check initial session
    supabase.auth.getSession().then(({ data }) => {
      setState({ ready: true, signedIn: !!data?.session });
    }).catch(() => {
      setState({ ready: true, signedIn: false });
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setState({ ready: true, signedIn: !!session });
    });

    return () => subscription.unsubscribe();
  }, []);

  return state;
}
