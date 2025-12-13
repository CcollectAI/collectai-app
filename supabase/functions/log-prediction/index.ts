import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

serve(async (req) => {
  if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

  // Client should send Authorization: Bearer <anon key>
  const payload = await req.json();
  const { category, title, features, suggestion, reason } = payload || {};
  if (!category || typeof suggestion !== "number") {
    return new Response("Bad Request", { status: 400 });
  }

  const url = Deno.env.get("SUPABASE_URL")!;
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  const body = {
    category, title,
    features: features ?? {},
    prediction: suggestion,
    reason,
    gated: false,
    platform: "app",
    model_name: "api-fallback",
    model_version: "v0"
    // DB trigger on prediction_events_v2 fills input/output if omitted
  };

  const res = await fetch(`${url}/rest/v1/prediction_events_v2`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "apikey": key,
      "Authorization": `Bearer ${key}`,
      "Prefer": "return=minimal"
    },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const txt = await res.text();
    return new Response(`Insert failed: ${txt}`, { status: 500 });
  }
  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" }
  });
});
