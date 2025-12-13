import { createClient } from 'jsr:@supabase/supabase-js@2'
export async function logMetric(supa: any, m: {
  fn: string; status: 'ok'|'error'; latency_ms?: number; idem_key?: string; session_id?: string; payload?: any;
}) {
  try { await supa.from('fn_metrics').insert({
    fn: m.fn, status: m.status, latency_ms: m.latency_ms ?? null,
    idem_key: m.idem_key ?? null, session_id: m.session_id ?? null, payload: m.payload ?? null
  }) } catch (_) {}
}
