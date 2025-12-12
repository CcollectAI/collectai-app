import { callEdge } from './api'

export type MarketHit = { id: string; title: string; price_eur: number; url: string; image: string; ts: string }

export async function searchEbay(jwt: string, anonKey: string, query: string, opts?: { category?: string; limit?: number }) {
  return callEdge<{ ok: true; provider: string; hits: MarketHit[] }>(
    'market-search-ebay',
    jwt,
    anonKey,
    { query, category: opts?.category, limit: opts?.limit ?? 8 }
  )
}
