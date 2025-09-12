import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const MODE = (process.env.EXPO_PUBLIC_SUPABASE_MODE ?? "strict").toLowerCase(); // 'strict' | 'mock' | 'off'
const URL  = process.env.EXPO_PUBLIC_SUPABASE_URL;
const KEY  = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

function makeMock(): SupabaseClient<any, any, any> {
  console.warn("[supabase] MOCK mode enabled");
  const noop = async () => ({ data: null, error: null });
  return {
    auth: {
      getSession: async () => ({ data: { session: null }, error: null }),
      getUser: async () => ({ data: { user: null }, error: null }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} }}, error: null } as any),
      signInWithOtp: async () => ({ error: null } as any),
      verifyOtp: async () => ({ error: null } as any),
    },
    from: () => ({ select: noop, insert: noop, update: noop, delete: noop, upsert: noop } as any),
  } as any;
}

export const supabase: SupabaseClient = (() => {
  if (MODE === "off") return makeMock();
  if (!URL || !KEY) {
    if (MODE === "strict") throw new Error("Supabase strict mode: missing EXPO_PUBLIC_SUPABASE_URL/ANON_KEY");
    return makeMock();
  }
  return createClient(URL, KEY, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } });
})();
