import { SUPABASE_URL } from '@/api/config';

export type EdgeResult<T> = { ok: true; data: T } | { ok: false; error: string }

export async function callEdge<T = unknown>(fn: string, jwt: string, anonKey: string, body: unknown): Promise<EdgeResult<T>> {
  const base = SUPABASE_URL;
  if (!base) return { ok: false, error: 'Missing SUPABASE_URL' }
  try {
    const res = await fetch(`${base}/functions/v1/${fn}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwt}`,
        'apikey': anonKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body ?? {})
    })
    const json = await res.json().catch(() => ({}))
    if (!res.ok || json?.ok === false) {
      return { ok: false, error: json?.error || `HTTP ${res.status}` }
    }
    return { ok: true, data: json as T }
  } catch (e: unknown) {
    // best-effort: not swallowed — the error is returned to the caller as
    // { ok: false, error } and surfaced there.
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}
