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
    _client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }

  return _client;
}
