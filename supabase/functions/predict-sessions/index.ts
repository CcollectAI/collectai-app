import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3.23.8'

const BodySchema = z.object({
  source: z.string().default('collectai'),
  version: z.string().default('v1'),
  category: z.string().min(2),
  idem_key: z.string().optional(),
  meta: z.record(z.any()).optional()
})

export const handler = async (req: Request) => {
  try {
    const url = new URL(req.url)
    const apikey = req.headers.get('apikey') ?? ''
    const auth = req.headers.get('authorization') ?? ''
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? apikey
    const supa = createClient(supabaseUrl, supabaseKey, {
      global: { headers: { Authorization: auth, apikey } }
    })

    const parsed = BodySchema.parse(await req.json().catch(() => ({})))
    const idem_key = parsed.idem_key || crypto.randomUUID()

    const { data, error } = await supa.from('predict_sessions').insert({
      source: parsed.source,
      version: parsed.version,
      category: parsed.category,
      idem_key,
      meta: parsed.meta ?? {}
    }).select().single()

    if (error) throw error
    return new Response(JSON.stringify({ ok: true, session: data }), { status: 200 })
  } catch (e: any) {
    if (e?.issues) {
      return new Response(JSON.stringify({ ok: false, error: 'Invalid payload', issues: e.issues }), { status: 400 })
    }
    return new Response(JSON.stringify({ ok: false, error: String(e?.message || e) }), { status: 400 })
  }
}
Deno.serve(handler)
