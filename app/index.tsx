import { Redirect } from "expo-router";
import { useEffect, useState } from "react";
import { supabase } from "../lib/supabaseClient";
import type { Session } from "@supabase/supabase-js";

export default function Index() {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null);
      setReady(true);
    });
  }, []);

  if (!ready) return null;
  return <Redirect href={session ? "/(tabs)" : "/(auth)"} />;
}
