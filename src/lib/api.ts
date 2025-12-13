export type EdgeResult<T> = { ok: true; data: T } | { ok: false; error: string }

export async function callEdge<T = any>(fn: string, jwt: string, anonKey: string, body: any): Promise<EdgeResult<T>> {
  const base = process.env.EXPO_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL;
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
  } catch (e: any) {
    return { ok: false, error: String(e?.message || e) }
  }
}
