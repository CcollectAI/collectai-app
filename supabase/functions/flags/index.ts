import 'jsr:@supabase/functions-js/edge-runtime.d.ts'
import { createClient } from 'jsr:@supabase/supabase-js@2'
export const handler = async (req: Request) => {
  const apikey = req.headers.get('apikey') ?? ''
  const auth = req.headers.get('authorization') ?? ''
  const url = Deno.env.get('SUPABASE_URL')!
  const supa = createClient(url, apikey || Deno.env.get('SUPABASE_ANON_KEY')!, { global:{ headers:{ Authorization: auth, apikey } } })
  const { data, error } = await supa.from('feature_flags').select('key,value')
  if (error) return new Response(JSON.stringify({ ok:false, error:String(error.message)}),{status:400})
  return new Response(JSON.stringify({ ok:true, flags:Object.fromEntries((data||[]).map((r:any)=>[r.key, !!r.value])) }), { status:200 })
}
Deno.serve(handler)
