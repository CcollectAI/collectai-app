import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3.23.8'

const BodySchema = z.object({
  query: z.string().min(2),
  category: z.string().optional(),
  limit: z.number().int().min(1).max(20).default(8),
  ttl_sec: z.number().int().min(10).max(3600).default(300),
})

async function getSub(supa:any) {
  try { const { data } = await supa.auth.getUser(); return data?.user?.id ?? 'anon' } catch { return 'anon' }
}

export const handler = async (req: Request) => {
  const apikey = req.headers.get('apikey') ?? ''
  const auth = req.headers.get('authorization') ?? ''
  const supabaseUrl = Deno.env.get('SUPABASE_URL')!
  const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? apikey
  const supa = createClient(supabaseUrl, supabaseKey, { global: { headers: { Authorization: auth, apikey } } })

  try {
    const raw = await req.json().catch(() => ({}))
    const body = BodySchema.parse(raw)
    const enabled = (Deno.env.get('EBAY_SEARCH_ENABLED') ?? 'off').toLowerCase() === 'on'
    const provider = enabled ? 'ebay' : 'mock'
    const sub = await getSub(supa)

    // Rate limit: max 20/min per subject
    const oneMinAgo = new Date(Date.now() - 60_000).toISOString()
    const { count } = await supa.from('rate_limits')
      .select('id', { count: 'exact', head: true })
      .gte('ts', oneMinAgo).eq('subject', sub).eq('resource','market-search')
    if ((count ?? 0) >= 20) {
      return new Response(JSON.stringify({ ok:false, error:'Rate limit exceeded' }), { status: 429 })
    }
    await supa.from('rate_limits').insert({ subject: sub, resource: 'market-search' })

    // Cache lookup
    const since = new Date(Date.now() - body.ttl_sec*1000).toISOString()
    const cached = await supa.from('market_cache')
      .select('hits, created_at').eq('provider', provider).eq('q', body.query).eq('category', body.category ?? null)
      .gte('created_at', since).order('created_at', { ascending:false }).limit(1).maybeSingle()
    if (cached.data?.hits) {
      let hits = cached.data.hits as any[]
      if (body.limit && hits.length > body.limit) hits = hits.slice(0, body.limit)
      return new Response(JSON.stringify({ ok:true, provider, hits, cached:true }), { status:200 })
    }

    // Real eBay (optional) or mock
    let hits: any[] = []
    if (!enabled) {
      hits = Array.from({ length: body.limit }).map((_, i) => ({
        id: `mock-${i+1}`, title: `${body.query} – Mock Hit #${i+1}`,
        price_eur: 19.99 + i, url: 'https://www.ebay.com/itm/mock', image: 'https://via.placeholder.com/200', ts: new Date().toISOString()
      }))
    } else {
      // Simple RapidAPI example; replace with official eBay Finding API if you prefer.
      const RAPID_KEY = Deno.env.get('RAPIDAPI_KEY')
      if (!RAPID_KEY) throw new Error('RAPIDAPI_KEY not set')
      const q = encodeURIComponent(body.query)
      const resp = await fetch(`https://ebay-data-scraper.p.rapidapi.com/find/items?q=${q}&limit=${body.limit}`, {
        headers: { 'X-RapidAPI-Key': RAPID_KEY, 'X-RapidAPI-Host': 'ebay-data-scraper.p.rapidapi.com' }
      })
      const j = await resp.json()
      hits = (j?.items ?? []).map((x:any, i:number) => ({
        id: x.itemId ?? `ebay-${i}`, title: x.title ?? body.query, price_eur: Number(x.price?.value ?? 0),
        url: x.itemWebUrl ?? 'https://www.ebay.com', image: x.image?.imageUrl ?? 'https://via.placeholder.com/200', ts: new Date().toISOString()
      }))
    }

    // Write cache
    await supa.from('market_cache').insert({ provider, q: body.query, category: body.category ?? null, hits })
    return new Response(JSON.stringify({ ok:true, provider, hits, cached:false }), { status:200 })
  } catch (e:any) {
    if (e?.issues) return new Response(JSON.stringify({ ok:false, error:'Invalid payload', issues:e.issues }), { status:400 })
    return new Response(JSON.stringify({ ok:false, error:String(e?.message || e) }), { status:400 })
  }
}
Deno.serve(handler)
