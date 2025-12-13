import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3.23.8'

const BodySchema = z.object({
  category: z.string().min(2),
  image_url: z.string().url().optional()
})

export const handler = async (req: Request) => {
  const apikey = req.headers.get('apikey') ?? ''
  const auth = req.headers.get('authorization') ?? ''
  const supabaseUrl = Deno.env.get('SUPABASE_URL')!
  const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? apikey
  const supa = createClient(supabaseUrl, supabaseKey, { global: { headers: { Authorization: auth, apikey } } })

  try {
    const body = BodySchema.parse(await req.json().catch(() => ({})))
    // TODO: call model/heuristics. For now, provide lightweight defaults by category.
    let guess = { title: null as string|null, attrs: {} as Record<string, any>, guess_confidence: 0.25 }
    if (body.category.toLowerCase().includes('pokemon')) {
      guess = { title: null, attrs: { condition: 'NM', predicted_value_eur: 39.99 }, guess_confidence: 0.35 }
    }
    if (body.category.toLowerCase().includes('funko')) {
      guess = { title: null, attrs: { condition: 'Boxed', predicted_value_eur: 24.99 }, guess_confidence: 0.30 }
    }

    return new Response(JSON.stringify({ ok: true, prefill: { category: body.category, ...guess } }), { status: 200 })
  } catch (e: any) {
    if (e?.issues) return new Response(JSON.stringify({ ok:false, error:'Invalid payload', issues: e.issues }), { status: 400 })
    return new Response(JSON.stringify({ ok:false, error:String(e?.message || e) }), { status: 400 })
  }
}
Deno.serve(handler)
