import React, { createContext, useEffect, useState, useContext } from 'react';
import { supabase } from '../../lib/supabase';

type Ctx = { user: any | null; loading: boolean; signOut: () => Promise<void>; };
const AuthCtx = createContext<Ctx>({ user:null, loading:true, signOut: async()=>{} });
export const useAuth = () => useContext(AuthCtx);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any|null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await supabase.auth.getUser();
      setUser(data.user ?? null); setLoading(false);
    })();
    const { data: sub } = supabase.auth.onAuthStateChange((_evt, sess) => {
      setUser(sess?.user ?? null);
    });
    return () => { sub.subscription.unsubscribe(); };
  }, []);

  return (
    <AuthCtx.Provider value={{ user, loading, signOut: ()=>supabase.auth.signOut() }}>
      {children}
    </AuthCtx.Provider>
  );
}
