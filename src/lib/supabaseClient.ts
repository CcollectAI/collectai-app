/**
 * Mock Supabase client for development mode.
 * Provides stub implementations that return empty data gracefully.
 */

// Mock query builder that returns empty results
const mockQueryBuilder = () => ({
  select: () => mockQueryBuilder(),
  insert: () => mockQueryBuilder(),
  update: () => mockQueryBuilder(),
  delete: () => mockQueryBuilder(),
  eq: () => mockQueryBuilder(),
  neq: () => mockQueryBuilder(),
  gt: () => mockQueryBuilder(),
  lt: () => mockQueryBuilder(),
  gte: () => mockQueryBuilder(),
  lte: () => mockQueryBuilder(),
  like: () => mockQueryBuilder(),
  ilike: () => mockQueryBuilder(),
  is: () => mockQueryBuilder(),
  in: () => mockQueryBuilder(),
  order: () => mockQueryBuilder(),
  limit: () => mockQueryBuilder(),
  single: () => Promise.resolve({ data: null, error: null }),
  maybeSingle: () => Promise.resolve({ data: null, error: null }),
  then: (resolve: any) => resolve({ data: [], error: null }),
});

export const supabase = {
  auth: {
    getSession: async () => ({ data: { session: null } }),
    getUser: async () => ({ data: { user: null } }),
    signInWithPassword: async () => ({ data: { user: null, session: null }, error: { message: 'Mock mode - auth disabled' } }),
    signOut: async () => ({ error: null }),
  },
  from: (table: string) => {
    console.log(`[MockSupabase] Query to table: ${table}`);
    return mockQueryBuilder();
  },
  rpc: async (fn: string, params?: any) => {
    console.log(`[MockSupabase] RPC call: ${fn}`, params);
    return { data: null, error: null };
  },
};

export default supabase;
