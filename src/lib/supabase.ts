import { createClient, processLock, type SupabaseClient } from "@supabase/supabase-js";
import { logger } from "@/lib/logger";
import { SUPABASE_URL as URL, SUPABASE_ANON_KEY as KEY, SUPABASE_MODE as MODE } from "@/api/config";
import { secureStoreAdapter } from "@/lib/secureStoreAdapter";

// ── Client-wide request timeout ────────────────────────────────────────────
// supabase-js ships NO per-request timeout. A query fired while the auth
// session is hydrating does not fail fast — it STALLS behind the auth lock.
// Any such await sitting between a spinner going up and coming down pins that
// spinner forever: nothing saved, no error, nothing logged. That shipped three
// separate times (items skeleton, home skeleton, add-manual "Saving…"), each
// found only after a user hit it.
//
// Bounding each call site by hand does not converge: `scripts/check-unbounded-
// awaits.mjs` found 90 of them, and any new one reintroduces the bug. So the
// bound lives on the client — every .from() and .rpc() is timed out by
// construction, including code not yet written.
//
// On timeout we RESOLVE with `{ data: null, error }` rather than reject. That
// is the shape every caller already destructures and checks, so a timeout takes
// the path they already handle. Rejecting would convert today's silent hangs
// into unhandled throws — a different bug, not a fix.
//
// auth.* is deliberately NOT wrapped. withTimeout is Promise.race, which
// abandons rather than cancels; a second concurrent auth op can trip Supabase's
// refresh-token reuse detection and REVOKE the session (see the `lock` comment
// below and docs/AUTH_AND_WEB_DEPLOY.md).
//
// Backstop only — screens that gate a skeleton should still set their own,
// tighter timeout (listItems uses 8s). This stops "forever", not "slow".
const PGRST_TIMEOUT_MS = 15_000;

type PostgrestLike = { data: null; error: { message: string; code: string; details: string; hint: string } };

function timeoutResult(label: string): PostgrestLike {
  // logger.error, NOT warn — info/warn are STRIPPED in release builds, which is
  // exactly where these hangs were invisible.
  logger.error(`[supabase] request timed out after ${PGRST_TIMEOUT_MS}ms (${label})`);
  return {
    data: null,
    error: {
      message: `Request timed out after ${PGRST_TIMEOUT_MS}ms`,
      code: "TIMEOUT",
      details: label,
      hint: "Check your connection and try again.",
    },
  };
}

/**
 * Proxies a PostgREST builder so awaiting it anywhere in the chain is bounded.
 * Filter/modifier methods return the builder itself, so results are re-wrapped
 * to keep the bound across `.select().eq().order().single()`.
 */
function boundBuilder<T extends object>(builder: T, label: string): T {
  return new Proxy(builder, {
    get(target, prop) {
      if (prop === "then") {
        // Read the raw `then` off the target, never the proxy, or this recurses.
        const rawThen = Reflect.get(target, "then", target) as unknown;
        if (typeof rawThen !== "function") return rawThen;
        return (onFulfilled?: (v: unknown) => unknown, onRejected?: (e: unknown) => unknown) => {
          const inner = new Promise((resolve, reject) =>
            (rawThen as (r: unknown, j: unknown) => void).call(target, resolve, reject),
          );
          let timer: ReturnType<typeof setTimeout>;
          return new Promise((resolve) => {
            timer = setTimeout(() => resolve(timeoutResult(label)), PGRST_TIMEOUT_MS);
            inner.then(
              (v) => { clearTimeout(timer); resolve(v); },
              (e) => { clearTimeout(timer); resolve({ data: null, error: e }); },
            );
          }).then(onFulfilled, onRejected);
        };
      }
      // Bind methods to the raw target: supabase-js builders touch private
      // fields, which throw if `this` is the proxy.
      const value = Reflect.get(target, prop, target) as unknown;
      if (typeof value === "function") {
        return (...args: unknown[]) => {
          const result = (value as (...a: unknown[]) => unknown).apply(target, args);
          const chained =
            result === target ||
            (typeof result === "object" && result !== null && typeof (result as { then?: unknown }).then === "function");
          return chained ? boundBuilder(result as object, label) : result;
        };
      }
      return value;
    },
  });
}

/** Wraps .from()/.rpc() so every PostgREST call is bounded. Leaves auth alone. */
// Exported for __tests__/lib/supabaseTimeout.test.ts — the bound is the whole
// point of this module, so it is pinned rather than trusted.
export function installRequestTimeouts(client: SupabaseClient): SupabaseClient {
  const rawFrom = client.from.bind(client);
  const rawRpc = client.rpc.bind(client);
  const c = client as unknown as Record<string, unknown>;
  c.from = (table: string, ...rest: unknown[]) =>
    boundBuilder((rawFrom as (...a: unknown[]) => object)(table, ...rest), `from:${table}`);
  c.rpc = (fn: string, ...rest: unknown[]) =>
    boundBuilder((rawRpc as (...a: unknown[]) => object)(fn, ...rest), `rpc:${fn}`);
  return client;
}


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
  // 2026-04-28: presence API methods (track/untrack/presenceState) added after
  // chat thread crash on `presenceChannelRef.current.track is not a function`
  // when the app fell back to mock mode. Keep this in sync with the real
  // RealtimeChannel surface that any screen actually calls.
  const makeChannel = () => {
    const ch: any = {};
    ch.on = () => ch;
    ch.subscribe = () => ch;
    ch.unsubscribe = async () => ({ error: null });
    ch.send = async () => ({ status: "ok" });
    ch.track = async () => ({ status: "ok" });
    ch.untrack = async () => ({ status: "ok" });
    ch.presenceState = () => ({});
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
      startAutoRefresh: async () => {},
      stopAutoRefresh: () => {},
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
  return installRequestTimeouts(createClient(URL, KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storage: secureStoreAdapter,
      // CRITICAL for React Native: without an explicit lock, GoTrueClient falls
      // back to `lockNoOp` (no locking) because `navigator.locks` only exists on
      // web. Unserialized auth ops then race — autoRefreshToken + the AppState
      // startAutoRefresh + getSession()/refreshSession() can fire TWO concurrent
      // refreshes on one rotating refresh-token, tripping Supabase's reuse
      // detection, which REVOKES the session. Result: every authenticated write
      // 401s and re-login doesn't help (the fresh session is re-revoked by the
      // same race). processLock serializes all auth ops in-process and fixes it.
      lock: processLock,
    },
  }));
})();
