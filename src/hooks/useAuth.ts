import { useEffect, useState } from "react";
import { Session, User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

/* ---------- Sentry (guarded so builds work before `npm i`) ---------- */
import type { SentryModule } from '@/../types/api';
let Sentry: SentryModule | null = null;
try {
  Sentry = require("@sentry/react-native");
} catch (_) {
  // @sentry/react-native not installed – skip silently
}

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
    } catch (e: unknown) {
      // Profile might not exist yet (e.g., user didn't finish sign-up flow)
      setProfile(null);
      setError(e instanceof Error ? e.message : "Failed to load profile");
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
        if (Sentry?.setUser) {
          Sentry.setUser(data.session?.user ? { id: data.session.user.id } : null);
        }
        await loadProfile(data.session?.user ?? null);
      } catch (e: unknown) {
        if (on) setError(e instanceof Error ? e.message : "Failed to get session");
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
      if (Sentry?.setUser) {
        Sentry.setUser(newSession?.user ? { id: newSession.user.id } : null);
      }
      await loadProfile(newSession?.user ?? null);
    });

    return () => {
      on = false;
      subscription.unsubscribe();
    };
  }, []);

  return { session, user, profile, loading, error };
}
