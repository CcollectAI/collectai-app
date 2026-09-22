// ---------------------------------------------------------------------------
// Supabase client – lazy singleton, SSR-safe, reads from admin.config.ts
// ---------------------------------------------------------------------------

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { APP_CONFIG } from "../../admin.config";

const SUPABASE_URL: string = APP_CONFIG.supabase.url;
const SUPABASE_ANON_KEY: string = APP_CONFIG.supabase.anonKey;

let _client: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return (
    SUPABASE_URL !== "REPLACE_WITH_SUPABASE_URL" &&
    SUPABASE_ANON_KEY !== "REPLACE_WITH_SUPABASE_ANON_KEY" &&
    SUPABASE_URL.startsWith("https://")
  );
}

export function getSupabase(): SupabaseClient | null {
  if (typeof window === "undefined") return null;
  if (!isSupabaseConfigured()) return null;

  if (!_client) {
    // Every query goes to our own /api/admin/sb route, never to Supabase
    // directly: the route checks the admin session cookie and forwards with
    // the service-role key, and the admin tables deny the anon key. The key
    // passed here is only a placeholder header the route discards.
    // supabase-js builds `${base}/rest/v1/<table>`, which is the route's path.
    _client = createClient(`${window.location.origin}/api/admin/sb`, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
        detectSessionInUrl: false,
      },
    });
  }

  return _client;
}
