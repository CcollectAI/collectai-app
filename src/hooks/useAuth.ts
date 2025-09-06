import { useEffect, useState } from "react";
import { Session, User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabaseClient";

type Profile = {
  id: string;
  username: string;
  created_at?: string;
};

export default function useAuth() {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadProfile(u: User | null) {
    if (!u) {
      setProfile(null);
      return;
    }
    try {
      const { data, error } = await supabase
        .from("profiles")
        .select("id, username, created_at")
        .eq("id", u.id)
        .single();
      if (error) throw error;
      setProfile(data as Profile);
    } catch (e: any) {
      // Profile might not exist yet (e.g., user didn’t finish sign-up flow)
      setProfile(null);
      setError(e?.message ?? "Failed to load profile");
    }
  }

  useEffect(() => {
    let on = true;

    (async () => {
      try {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;
        if (!on) return;

        setSession(data.session ?? null);
        setUser(data.session?.user ?? null);
        await loadProfile(data.session?.user ?? null);
      } catch (e: any) {
        if (on) setError(e?.message ?? "Failed to get session");
      } finally {
        if (on) setLoading(false);
      }
    })();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, newSession) => {
      if (!on) return;
      setSession(newSession);
      setUser(newSession?.user ?? null);
      await loadProfile(newSession?.user ?? null);
    });

    return () => {
      on = false;
      subscription.unsubscribe();
    };
  }, []);

  return { session, user, profile, loading, error };
}
