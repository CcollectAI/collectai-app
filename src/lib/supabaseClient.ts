export const supabase = {
  from() { return { select(){return this}, insert(){return this}, update(){return this}, eq(){return this} }; },
  auth: { getUser: async () => ({ data: null }), onAuthStateChange: () => ({ data: null, subscription: { unsubscribe(){} }}) }
};
export default supabase;
