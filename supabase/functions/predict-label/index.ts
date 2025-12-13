import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'
import { z } from 'npm:zod@3.23.8'

const BodySchema = z.object({
  session_id: z.string().uuid(),
  corrections: z.record(z.any()).default({}),
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

    const { data: labelEvt, error: leErr } = await supa.from('label_events')
      .insert({
        session_id: body.session_id,
        payload: body.corrections,
        image_url: body.image_url ?? null,
        source: body.source,
        version: body.version
      }).select().single()
    if (leErr) throw leErr

    const upsertPayload: any = {
      source: body.source,
      version: body.version,
      image_url: body.image_url ?? null,
      attributes: body.corrections,
      title: (body.corrections as any).title ?? null
    }
    if (body.idem_key) upsertPayload.idem_key = body.idem_key

    await supa.from('training_items').upsert(upsertPayload, { onConflict: 'idem_key' })
    return new Response(JSON.stringify({ ok:true, label_event: labelEvt?.id || null, idem_key: body.idem_key || null }), { status:200 })
  } catch (e:any) {
    if (e?.issues) return new Response(JSON.stringify({ ok:false, error:'Invalid payload', issues:e.issues }), { status:400 })
    return new Response(JSON.stringify({ ok:false, error:String(e?.message || e) }), { status:400 })
  }
}
Deno.serve(handler)
