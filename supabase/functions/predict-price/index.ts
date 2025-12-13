import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3.23.8'

const BodySchema = z.object({
  title: z.string().min(2),
  category: z.string().min(2),
  attrs: z.record(z.any()).optional(),
  ttl_sec: z.number().int().min(10).max(3600).default(180)
})

function keyHash(t:string, c:string, cond:string){ return crypto.createHash?.('sha1')?.update(`${t}|${c}|${cond}`).digest('hex') ?? btoa(`${t}|${c}|${cond}`) }

async function getSub(supa:any){ try{ const {data}=await supa.auth.getUser(); return data?.user?.id ?? 'anon' }catch{ return 'anon' } }

export const handler = async (req: Request) => {
  const apikey = req.headers.get('apikey') ?? ''
  const auth   = req.headers.get('authorization') ?? ''
  const supabaseUrl = Deno.env.get('SUPABASE_URL')!
  const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? apikey
  const supa = createClient(supabaseUrl, supabaseKey, { global: { headers: { Authorization: auth, apikey } } })

  const t0 = Date.now()
  try {
    const body = BodySchema.parse(await req.json().catch(() => ({})))
    const cond = String((body.attrs?.condition ?? 'NM')).toUpperCase()
    const sub  = await getSub(supa)
    const model = await supa.from('model_gate').select('*').eq('name','price').maybeSingle()
    const active = model.data?.active_version ?? 'heuristic'
    const candidate = model.data?.candidate_version
    const split = Number(model.data?.candidate_split ?? 0)

    // Rate limit: 60/min per subject
    const oneMinAgo = new Date(Date.now()-60_000).toISOString()
    const rl = await supa.from('rate_limits').select('id', {count:'exact', head:true})
      .gte('ts', oneMinAgo).eq('subject', sub).eq('resource', 'predict-price')
    if ((rl.count ?? 0) >= 60) {
      return new Response(JSON.stringify({ ok:false, error:'Rate limit exceeded' }), { status: 429 })
    }
    await supa.from('rate_limits').insert({ subject: sub, resource: 'predict-price' })

    // Cache
    const kh = keyHash(body.title, body.category, cond)
    const since = new Date(Date.now()-body.ttl_sec*1000).toISOString()
    const cached = await supa.from('price_cache').select('price_eur,created_at')
      .eq('keyhash', kh).gte('created_at', since).order('created_at', {ascending:false}).limit(1).maybeSingle()
    if (cached.data?.price_eur != null) {
      const price = Number(cached.data.price_eur)
      await supa.from('prediction_events').insert({
        session_id: null, model_name:'price', model_version: active,
        input: { title: body.title, category: body.category, attrs: body.attrs ?? {} },
        output: { price_eur: price, cached: true }, latency_ms: Date.now()-t0
      } as any)
      return new Response(JSON.stringify({ ok:true, price_eur: price, cached:true, model_version: active }), { status:200 })
    }

    // Route via gate
    const useCandidate = candidate && Math.random()*100 < split
    const targetVersion = useCandidate ? candidate! : active
    let price = 0

    const remote = Deno.env.get('PREDICT_URL') // optional endpoint supporting version
    if (remote && targetVersion !== 'heuristic') {
      const r = await fetch(remote, {
        method:'POST', headers: { 'Content-Type':'application/json' },
        body: JSON.stringify({ version: targetVersion, title: body.title, category: body.category, attrs: body.attrs ?? {} })
      })
      const j = await r.json().catch(()=> ({}))
      price = Number(j?.price_eur ?? 0)
    } else {
      // heuristic fallback
      const base = body.category.toLowerCase().includes('pokemon') ? 40 : 25
      const mul = cond==='NM'?1:cond==='LP'?0.8:0.6
      price = Math.round(base*mul*100)/100
    }

    await supa.from('price_cache').insert({ keyhash: kh, price_eur: price })
    await supa.from('prediction_events').insert({
      session_id: null, model_name:'price', model_version: targetVersion,
      input: { title: body.title, category: body.category, attrs: body.attrs ?? {} },
      output: { price_eur: price }, latency_ms: Date.now()-t0
    } as any)

    return new Response(JSON.stringify({ ok:true, price_eur: price, cached:false, model_version: targetVersion }), { status:200 })
  } catch (e:any) {
    if (e?.issues) return new Response(JSON.stringify({ ok:false, error:'Invalid payload', issues:e.issues }), { status:400 })
    return new Response(JSON.stringify({ ok:false, error:String(e?.message || e) }), { status:400 })
  }
}
Deno.serve(handler)
