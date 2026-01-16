// Minimal shim so legacy src/* imports resolve during precheck.
// Real Supabase wiring lives elsewhere in the app/services.
export const supabaseClient = null as any;
export default supabaseClient;
