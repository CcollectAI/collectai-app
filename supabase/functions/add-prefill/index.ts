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
    // Category-based heuristics for prefill defaults
    // Future: call external model API for image-based predictions
    let guess = { title: null as string|null, attrs: {} as Record<string, any>, guess_confidence: 0.25 }
    const cat = body.category.toLowerCase()

    if (cat.includes('pokemon')) {
      guess = { title: null, attrs: { condition: 'NM', predicted_value_eur: 39.99, rarity_tier: 'holo' }, guess_confidence: 0.35 }
    } else if (cat.includes('mtg') || cat.includes('magic')) {
      guess = { title: null, attrs: { condition: 'NM', predicted_value_eur: 15.00, format: 'modern' }, guess_confidence: 0.30 }
    } else if (cat.includes('funko')) {
      guess = { title: null, attrs: { condition: 'Boxed', predicted_value_eur: 24.99, exclusive: false }, guess_confidence: 0.30 }
    } else if (cat.includes('lorcana')) {
      guess = { title: null, attrs: { condition: 'NM', predicted_value_eur: 8.00, foil: false }, guess_confidence: 0.30 }
    } else if (cat.includes('warhammer') || cat.includes('40k')) {
      guess = { title: null, attrs: { condition: 'New on Sprue', predicted_value_eur: 45.00, painted: false }, guess_confidence: 0.25 }
    } else if (cat.includes('gunpla') || cat.includes('gundam')) {
      guess = { title: null, attrs: { condition: 'NIB', predicted_value_eur: 35.00, grade: 'HG' }, guess_confidence: 0.25 }
    } else if (cat.includes('diecast') || cat.includes('hotwheels')) {
      guess = { title: null, attrs: { condition: 'Carded', predicted_value_eur: 5.00, chase: false }, guess_confidence: 0.30 }
    } else if (cat.includes('lego')) {
      guess = { title: null, attrs: { condition: 'Sealed', predicted_value_eur: 50.00, complete: true }, guess_confidence: 0.25 }
    }

    return new Response(JSON.stringify({ ok: true, prefill: { category: body.category, ...guess } }), { status: 200 })
  } catch (e: any) {
    if (e?.issues) return new Response(JSON.stringify({ ok:false, error:'Invalid payload', issues: e.issues }), { status: 400 })
    return new Response(JSON.stringify({ ok:false, error:String(e?.message || e) }), { status: 400 })
  }
}
Deno.serve(handler)
