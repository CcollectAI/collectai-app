import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3.23.8'

const BodySchema = z.object({
  session_id: z.string().uuid(),
  output: z.record(z.any()).default({}),
  image_url: z.string().url().nullable().optional(),
  source: z.string().default('collectai'),
  version: z.string().default('v1'),
  idem_key: z.string().optional()
})

export const handler = async (req: Request) => {
  try {
    const apikey = req.headers.get('apikey') ?? ''
    const auth = req.headers.get('authorization') ?? ''
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? apikey
    const supa = createClient(supabaseUrl, supabaseKey, { global: { headers: { Authorization: auth, apikey } } })

    const body = BodySchema.parse(await req.json().catch(() => ({})))
    const idem_key = body.idem_key || crypto.randomUUID()

    const { error: upErr } = await supa.from('predict_sessions')
      .update({ output: body.output, image_url: body.image_url ?? null, version: body.version })
      .eq('id', body.session_id)
    if (upErr) throw upErr

    // seed training_items (idempotent via idem_key)
    await supa.from('training_items').upsert({
      idem_key, source: body.source, version: body.version,
      image_url: body.image_url ?? null,
      title: (body.output as any)?.title ?? null,
      attributes: body.output ?? {}
    } as any, { onConflict: 'idem_key' })

    return new Response(JSON.stringify({ ok:true, session_id: body.session_id, idem_key }), { status:200 })
  } catch (e:any) {
    if (e?.issues) return new Response(JSON.stringify({ ok:false, error:'Invalid payload', issues:e.issues }), { status:400 })
    return new Response(JSON.stringify({ ok:false, error:String(e?.message || e) }), { status:400 })
  }
}
Deno.serve(handler)
