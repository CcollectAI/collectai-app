import { useCallback, useState } from "react";
import { supabase } from "@/lib/supabase";
const FN_URL = process.env.EXPO_PUBLIC_SUPABASE_FUNCTIONS_URL;

export function usePredictionSession() {
  const [session, setSession] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState<string | null>(null);

  const authHeader = async () => {
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      return token ? { Authorization: `Bearer ${token}` } : {};
    } catch { return {}; }
  };

  const createSession = useCallback(async (category: "pokemon"|"funko"|"diecast") => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${FN_URL}/predict-sessions`, {
        method: "POST",
        headers: { "Content-Type":"application/json", ...(await authHeader()) },
        body: JSON.stringify({ category })
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to create session");
      setSession(json.session);
      return json.session;
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); throw e; }
    finally { setLoading(false); }
  }, []);

  const complete = useCallback(async (session_id: string, seed?: number) => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${FN_URL}/predict-complete`, {
        method: "POST",
        headers: { "Content-Type":"application/json", ...(await authHeader()) },
        body: JSON.stringify({ session_id, mock_seed: seed })
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to complete prediction");
      setSession(json.session);
      return json.session;
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); throw e; }
    finally { setLoading(false); }
  }, []);

  const label = useCallback(async (payload: {
    session_id: string; corrected_title?: string; corrected_variant?: string;
    corrected_condition?: string; corrected_price_eur?: number; notes?: string;
  }) => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${FN_URL}/predict-label`, {
        method: "POST",
        headers: { "Content-Type":"application/json", ...(await authHeader()) },
        body: JSON.stringify(payload)
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Failed to save label");
      return json.label;
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); throw e; }
    finally { setLoading(false); }
  }, []);

  return { session, loading, error, createSession, complete, label };
}
