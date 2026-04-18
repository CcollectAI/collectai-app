import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { logger } from "@/lib/logger";
import { SUPABASE_URL as URL, SUPABASE_ANON_KEY as KEY, SUPABASE_MODE as MODE } from "@/api/config";
import { secureStoreAdapter } from "@/lib/secureStoreAdapter";


function makeMock(): SupabaseClient<any, any, any> {
  logger.warn("[supabase] MOCK mode enabled");

  // Every filter/modifier chains back to the same builder object, so any
  // `.from(x).select(y).eq(z).order(...).limit(...).single()` keeps working.
  // The builder is thenable so `await` resolves to { data: null, error: null }
  // at any point in the chain.
  // Before R50l the mock only had top-level select/insert/... which made
  // useItemDetail + inbox crash the moment they called .eq() or .single().
  const mockResult = { data: null, error: null };

  function makeBuilder(): any {
    const builder: any = {};
    const chainableMethods = [
      "select", "insert", "update", "delete", "upsert",
      "eq", "neq", "gt", "gte", "lt", "lte",
      "like", "ilike", "is", "in", "contains", "containedBy",
      "rangeLt", "rangeGt", "rangeGte", "rangeLte", "rangeAdjacent",
      "overlaps", "textSearch", "match", "not", "or", "filter",
      "order", "limit", "range", "abortSignal", "returns",
    ];
    for (const m of chainableMethods) {
      builder[m] = () => builder;
    }
    // Terminal-ish: these still return thenable for .then() chains
    builder.single = () => builder;
    builder.maybeSingle = () => builder;
    builder.csv = () => builder;
    // Thenable so `await builder` resolves to mockResult
    builder.then = (onFulfilled: (v: typeof mockResult) => unknown) =>
      Promise.resolve(mockResult).then(onFulfilled);
    builder.catch = (onRejected: (e: unknown) => unknown) =>
      Promise.resolve(mockResult).catch(onRejected);
    return builder;
  }

  // Mock channel for Supabase Realtime — `supabase.channel('x').on(...).subscribe()`
  // Inbox + any other realtime-subscriber screen would crash if this was absent.
  const makeChannel = () => {
    const ch: any = {};
    ch.on = () => ch;
    ch.subscribe = () => ch;
    ch.unsubscribe = async () => ({ error: null });
    ch.send = async () => ({ status: "ok" });
    return ch;
  };

  return {
    auth: {
      getSession: async () => ({ data: { session: null }, error: null }),
      getUser: async () => ({ data: { user: null }, error: null }),

      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} }}, error: null } as any),

      signInWithOtp: async () => ({ error: null } as any),

      verifyOtp: async () => ({ error: null } as any),
      signOut: async () => ({ error: null } as any),
    },
    from: () => makeBuilder(),
    rpc: () => makeBuilder(),
    channel: () => makeChannel(),
    removeChannel: async () => ({ error: null }),
    removeAllChannels: async () => ({ error: null }),
    getChannels: () => [],
    storage: {
      from: () => ({
        upload: async () => ({ data: null, error: null }),
        download: async () => ({ data: null, error: null }),
        remove: async () => ({ data: null, error: null }),
        list: async () => ({ data: [], error: null }),
        getPublicUrl: () => ({ data: { publicUrl: "" } }),
        createSignedUrl: async () => ({ data: null, error: null }),
      }),
    },
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
