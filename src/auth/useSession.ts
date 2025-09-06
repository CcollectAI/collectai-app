import { useEffect, useState } from "react";
import supabase from "../../lib/supabaseClient";

export function useSession() {
  const [ready, setReady] = useState(false);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!supabase) { setReady(true); setSignedIn(false); return; }
      const { data } = await supabase.auth.getSession();
      if (mounted) setSignedIn(!!data.session);
      setReady(true);
      supabase.auth.onAuthStateChange((_event, session) => {
        if (mounted) setSignedIn(!!session);
      });
    })();
    return () => { mounted = false; };
  }, []);

  return { ready, signedIn };
}
