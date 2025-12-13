import { serve } from "https://deno.land/std@0.224.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.46.1"

const url = Deno.env.get("SUPABASE_URL")!
const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!

// Separate clients for each schema
const pub = createClient(url, key, { db: { schema: "public" } })
const pc  = createClient(url, key, { db: { schema: "predictive_capture" } })

serve(async (req) => {
  try {
    const u = new URL(req.url)
    const sid = u.searchParams.get("id")
    if (!sid) return new Response(JSON.stringify({ error: "pass ?id=" }), { status: 400 })

    // allow numeric or string ids (future-proof)
    const id = /^\d+$/.test(sid) ? Number(sid) : sid

    const [a, b] = await Promise.all([
      pub.from("predict_sessions")
         .select("id,uuid_id,user_id,created_at,status,category")
         .eq("id", id).maybeSingle(),
      pc.from("sessions")
        .select("id,uuid_id,user_id,created_at,status,category")
        .eq("id", id).maybeSingle(),
    ])

    return new Response(JSON.stringify({
      public_predict_sessions: a.data ?? null,
      predictive_capture_sessions: b.data ?? null,
      errors: { public: a.error?.message ?? null, pc: b.error?.message ?? null }
    }), { status: 200 })
  } catch (e) {
    return new Response(JSON.stringify({ error: e instanceof Error ? e.message : String(e) }), { status: 500 })
  }
})
