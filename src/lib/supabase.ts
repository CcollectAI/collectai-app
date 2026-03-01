import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { logger } from "@/lib/logger";
import { SUPABASE_URL as URL, SUPABASE_ANON_KEY as KEY, SUPABASE_MODE as MODE } from "@/api/config";
import { secureStoreAdapter } from "@/lib/secureStoreAdapter";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function makeMock(): SupabaseClient<any, any, any> {
  logger.warn("[supabase] MOCK mode enabled");
  const noop = async () => ({ data: null, error: null });
  // The mock intentionally provides partial implementations of the Supabase client.
  // Using type assertions here is unavoidable since we're mocking a complex third-party interface.
  return {
    auth: {
      getSession: async () => ({ data: { session: null }, error: null }),
      getUser: async () => ({ data: { user: null }, error: null }),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} }}, error: null } as any),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      signInWithOtp: async () => ({ error: null } as any),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      verifyOtp: async () => ({ error: null } as any),
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    from: () => ({ select: noop, insert: noop, update: noop, delete: noop, upsert: noop } as any),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any;
}

export const supabase: SupabaseClient = (() => {
  if (MODE === "off") return makeMock();
  if (!URL || !KEY) {
    if (MODE === "strict") throw new Error("Supabase strict mode: missing EXPO_PUBLIC_SUPABASE_URL/ANON_KEY");
    return makeMock();
  }
  return createClient(URL, KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storage: secureStoreAdapter,
    },
  });
})();
