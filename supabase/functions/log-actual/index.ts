import type { Context } from "https://edge.netlify.com";
export default async (req: Request, _ctx: Context) => {
  const url = Deno.env.get("SUPABASE_URL")!;
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  try {
    const body = await req.json(); // { id?: number, actual_eur: number }
    const { id, actual_eur } = body ?? {};
    if (!id || typeof actual_eur !== "number") {
      return new Response(JSON.stringify({ ok:false, error:"id and actual_eur required" }), { status:400 });
    }
    const res = await fetch(`${url}/rest/v1/prediction_events_v2?id=eq.${id}`, {
      method: "PATCH",
      headers: { "Content-Type":"application/json", "apikey": key, "Authorization": `Bearer ${key}` },
      body: JSON.stringify({ actual_eur }),
    });
    const ok = res.status>=200 && res.status<300;
    return new Response(JSON.stringify({ ok, status: res.status }), { headers: { "Content-Type": "application/json" }});
  } catch (e) {
    return new Response(JSON.stringify({ ok:false, error: String(e) }), { status:500 });
  }
}
