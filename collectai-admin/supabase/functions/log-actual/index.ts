export default async (req: Request) => {
  const url = Deno.env.get("SUPABASE_URL")!;
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const secret = Deno.env.get("EDGE_SHARED_SECRET") || "";
  const caller = req.headers.get("x-edge-secret") || "";

  if (secret && caller !== secret) {
    return new Response(JSON.stringify({ ok:false, error:"unauthorized" }), { status:401 });
  }

  try {
    const { id, actual_eur } = await req.json();
    if (!id || typeof actual_eur !== "number") {
      return new Response(JSON.stringify({ ok:false, error:"id:number and actual_eur:number required" }), { status:400 });
    }
    const res = await fetch(`${url}/rest/v1/prediction_events_v2?id=eq.${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "apikey": key,
        "Authorization": `Bearer ${key}`,
        "Prefer": "return=representation"
      },
      body: JSON.stringify({ actual_eur })
    });
    const body = await res.text();
    return new Response(JSON.stringify({ ok: res.ok, status: res.status, body }), {
      headers: { "Content-Type": "application/json" }, status: res.ok ? 200 : 500
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok:false, error:String(e) }), { status:500 });
  }
}
