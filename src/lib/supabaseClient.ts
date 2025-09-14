export const supabase = {
  auth: {
    signInWithOtp: async (_: { email: string }) => ({ data: null, error: null }),
    signOut: async () => ({ error: null }),
  },
  from: (_table: string) => ({
    select: async () => ({ data: [], error: null }),
    insert: async () => ({ data: [], error: null }),
    update: async () => ({ data: [], error: null }),
    delete: async () => ({ data: [], error: null }),
  }),
};
export default supabase;
