export const supabase = {
  auth: { getSession: async () => ({ data: { session: null } }) }
};
export default supabase;
